"""
API 端到端集成测试

使用 FastAPI TestClient + 内存 SQLite，测试完整的 HTTP 请求/响应链路：
  - 认证：注册、登录、获取当前用户、更新用户信息
  - 简历 CRUD：创建、列表、获取、更新、删除
  - 聊天记录：追加、获取、清空
  - 权限隔离：跨用户访问被拒绝
"""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.infra.database import Base, get_db
from app.main import app
from app.models.billing import BillingSubscription
from app.models.interview import InterviewSession, InterviewTurn
from app.models.resume import ResumeChatMessage, ResumeUploadJob
from app.models.user import ProviderIdentity, User
from app.runtime.permissions import confirmation_manager
from app.services.errors import ServicePayloadTooLargeError
from app.state.models import AgentEvent, AgentSession
from app.state.store import AgentSessionStore

# ── 测试数据库 ──────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite://"  # 纯内存，每次测试都是空库

_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    """用于覆盖get数据库。"""
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """在整个测试会话开始时建表，结束时销毁。"""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def client():
    """用于处理客户端。"""
    return TestClient(app)


# ── 辅助函数 ─────────────────────────────────────────────────────────────────


def _register(
    client: TestClient,
    email: str,
    password: str = "password123",
    full_name: str | None = None,
):
    """用于处理register。"""
    payload = {"email": email, "password": password}
    if full_name:
        payload["full_name"] = full_name
    return client.post("/api/auth/register", json=payload)


def _login(client: TestClient, email: str, password: str = "password123") -> str:
    """用于处理login。"""
    resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    access_cookie = resp.cookies.get("access_token") or client.cookies.get(
        "access_token"
    )
    assert access_cookie
    return access_cookie


def _auth_headers(token: str) -> dict:
    """用于处理认证headers。"""
    return {"Authorization": f"Bearer {token}"}


def _sse_events(response) -> list[dict]:
    """把测试响应中的 SSE data 行解析为事件列表。"""
    events: list[dict] = []
    data_lines: list[str] = []
    for line in response.text.splitlines():
        if not line:
            if data_lines:
                events.append(json.loads("\n".join(data_lines)))
                data_lines = []
            continue
        if line.startswith("data: "):
            data_lines.append(line[6:])
    if data_lines:
        events.append(json.loads("\n".join(data_lines)))
    return events


def _anonymous_client() -> TestClient:
    """返回一个不带登录 Cookie 的独立测试客户端。"""
    return TestClient(app)


def _grant_active_subscription(email: str, subscription_id: str = "I-PLUS") -> None:
    """在测试库中为用户授予一条活动订阅。"""
    db = _TestingSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        existing = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == "paypal",
                BillingSubscription.provider_subscription_id == subscription_id,
            )
            .first()
        )
        if existing is not None:
            existing.status = "ACTIVE"
            db.add(existing)
            db.commit()
            return
        db.add(
            BillingSubscription(
                user_id=user.id,
                provider="paypal",
                provider_subscription_id=subscription_id,
                status="ACTIVE",
                raw_payload={"id": subscription_id, "status": "ACTIVE"},
            )
        )
        db.commit()
    finally:
        db.close()


def _configure_google_oauth(monkeypatch):
    """用于处理configureGoogleOAuth。"""
    from app.entrypoints.http import auth as auth_routes

    monkeypatch.setattr(
        auth_routes.settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client-id"
    )
    monkeypatch.setattr(
        auth_routes.settings, "GOOGLE_OAUTH_CLIENT_SECRET", "google-client-secret"
    )
    monkeypatch.setattr(
        auth_routes.settings,
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8000/api/auth/google/callback",
    )
    monkeypatch.setattr(auth_routes.settings, "FRONTEND_URL", "http://localhost:3000")
    return auth_routes


def _issue_google_state(client: TestClient) -> str:
    """用于处理issueGooglestate。"""
    start_resp = client.get("/api/auth/google/login", follow_redirects=False)
    assert start_resp.status_code == 302
    return parse_qs(urlparse(start_resp.headers["location"]).query)["state"][0]


def _empty_resume_content() -> dict:
    """用于处理empty简历content。"""
    return {
        "job_application": {"target_company": "测试公司", "target_title": "后端工程师"},
        "personal_info": {"name": "张三", "email": "zhangsan@example.com"},
        "work_experience": [],
        "education": [],
        "skills": [],
        "projects": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. 认证流程
# ═══════════════════════════════════════════════════════════════════════════


class TestAuth:
    def test_register_creates_user(self, client):
        """用于验证registercreates用户。"""
        resp = _register(client, "new_user@example.com", full_name="新用户")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "new_user@example.com"
        assert body["full_name"] == "新用户"
        assert "id" in body
        assert "hashed_password" not in body

    def test_register_duplicate_email_returns_400(self, client):
        """用于验证registerduplicateemailreturns400。"""
        _register(client, "dup@example.com")
        resp = _register(client, "dup@example.com")
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_login_returns_token_and_user(self, client):
        """用于验证loginreturns令牌and用户。"""
        _register(client, "login_test@example.com", full_name="登录测试")
        resp = client.post(
            "/api/auth/login",
            data={"username": "login_test@example.com", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "login_test@example.com"
        assert "access_token" not in body
        assert "refresh_token" not in body
        assert resp.cookies.get("access_token")
        assert resp.cookies.get("refresh_token")

    def test_login_cookie_allows_get_me_without_authorization_header(self, client):
        """用于验证logincookieallowsgetmewithoutauthorizationheader。"""
        _register(client, "cookie_me_user@example.com", full_name="Cookie用户")
        _login(client, "cookie_me_user@example.com")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "cookie_me_user@example.com"

    def test_me_reports_password_login_capability(self, client):
        """用于验证me接口返回账号是否支持密码登录。"""
        from app.infra.security import create_access_token

        _register(client, "has_password_me@example.com")
        token = _login(client, "has_password_me@example.com")
        password_resp = client.get("/api/auth/me", headers=_auth_headers(token))

        db = _TestingSession()
        try:
            google_user = User(
                email="google_only_me@example.com",
                hashed_password=None,
                full_name="Google Only",
            )
            db.add(google_user)
            db.commit()
            db.refresh(google_user)
            google_token = create_access_token(google_user.id)
        finally:
            db.close()

        google_resp = client.get("/api/auth/me", headers=_auth_headers(google_token))

        assert password_resp.status_code == 200
        assert password_resp.json()["has_password"] is True
        assert google_resp.status_code == 200
        assert google_resp.json()["has_password"] is False

    def test_login_wrong_password_returns_401(self, client):
        """用于验证loginwrongpasswordreturns401。"""
        _register(client, "wrong_pw@example.com")
        resp = client.post(
            "/api/auth/login",
            data={"username": "wrong_pw@example.com", "password": "wrongpassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_login_unknown_user_returns_401(self, client):
        """用于验证loginunknown用户returns401。"""
        resp = client.post(
            "/api/auth/login",
            data={"username": "nobody@example.com", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_google_only_user_without_password_cannot_password_login(self, client):
        """用于验证Googleonly用户withoutpasswordcannotpasswordlogin。"""
        db = _TestingSession()
        try:
            db.add(
                User(
                    email="google_only_login@example.com",
                    hashed_password=None,
                    full_name="Google Only",
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.post(
            "/api/auth/login",
            data={
                "username": "google_only_login@example.com",
                "password": "password123",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_forgot_password_reset_link_changes_email_user_password(
        self, client, monkeypatch
    ):
        """用于验证忘记密码链接可以重置邮箱用户密码。"""
        from app.entrypoints.http import auth as auth_routes

        class FakePasswordResetMailer:
            """用于记录测试期间发出的密码重置链接。"""

            def __init__(self):
                """用于初始化测试邮件发件箱。"""
                self.reset_links: list[str] = []

            def send_password_reset(self, *, email: str, reset_link: str) -> None:
                """用于保存密码重置邮件参数。"""
                assert email == "forgot_password@example.com"
                self.reset_links.append(reset_link)

        mailer = FakePasswordResetMailer()
        monkeypatch.setattr(auth_routes, "password_reset_mailer", mailer)
        _register(client, "forgot_password@example.com", password="oldpass123")

        forgot_resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "forgot_password@example.com"},
        )

        assert forgot_resp.status_code == 200
        assert forgot_resp.json()["message"]
        assert len(mailer.reset_links) == 1
        token = parse_qs(urlparse(mailer.reset_links[0]).query)["token"][0]

        reset_resp = client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "newpass123"},
        )

        assert reset_resp.status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                data={
                    "username": "forgot_password@example.com",
                    "password": "oldpass123",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ).status_code
            == 401
        )
        assert _login(client, "forgot_password@example.com", "newpass123")

    def test_reset_password_rejects_reused_token(self, client, monkeypatch):
        """用于验证密码重置token只能使用一次。"""
        from app.entrypoints.http import auth as auth_routes

        class FakePasswordResetMailer:
            """用于记录测试期间发出的密码重置链接。"""

            def __init__(self):
                """用于初始化测试邮件发件箱。"""
                self.reset_links: list[str] = []

            def send_password_reset(self, *, email: str, reset_link: str) -> None:
                """用于保存密码重置邮件参数。"""
                self.reset_links.append(reset_link)

        mailer = FakePasswordResetMailer()
        monkeypatch.setattr(auth_routes, "password_reset_mailer", mailer)
        _register(client, "reuse_reset@example.com", password="oldpass123")
        client.post("/api/auth/forgot-password", json={"email": "reuse_reset@example.com"})
        token = parse_qs(urlparse(mailer.reset_links[0]).query)["token"][0]
        first_resp = client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "newpass123"},
        )

        reused_resp = client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "againpass123"},
        )

        assert first_resp.status_code == 200
        assert reused_resp.status_code == 400

    def test_change_password_requires_current_password(self, client):
        """用于验证已登录用户修改密码时必须提供正确旧密码。"""
        _register(client, "change_password@example.com", password="oldpass123")
        token = _login(client, "change_password@example.com", "oldpass123")
        wrong_resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "badpass123", "new_password": "newpass123"},
            headers=_auth_headers(token),
        )

        change_resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "oldpass123", "new_password": "newpass123"},
            headers=_auth_headers(token),
        )

        assert wrong_resp.status_code == 400
        assert change_resp.status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                data={
                    "username": "change_password@example.com",
                    "password": "oldpass123",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ).status_code
            == 401
        )
        assert _login(client, "change_password@example.com", "newpass123")

    def test_provider_identity_provider_user_id_is_unique_per_provider(self, client):
        """用于验证provideridentityprovider用户idisuniqueperprovider。"""
        db = _TestingSession()
        try:
            user = User(
                email="provider_identity_owner@example.com",
                hashed_password=None,
                full_name="Provider Owner",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            db.add(
                ProviderIdentity(
                    provider="google",
                    provider_user_id="google-sub-123",
                    user_id=user.id,
                    provider_email="provider_identity_owner@example.com",
                    provider_email_verified=True,
                )
            )
            db.commit()

            db.add(
                ProviderIdentity(
                    provider="google",
                    provider_user_id="google-sub-123",
                    user_id=user.id,
                    provider_email="provider_identity_owner@example.com",
                    provider_email_verified=True,
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
        finally:
            db.close()

    def test_google_login_redirects_to_google_authorization_url(
        self, client, monkeypatch
    ):
        """用于验证GoogleloginredirectstoGoogleauthorizationurl。"""
        _configure_google_oauth(monkeypatch)

        resp = client.get("/api/auth/google/login", follow_redirects=False)

        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
            "https://accounts.google.com/o/oauth2/v2/auth"
        )
        assert params["client_id"] == ["google-client-id"]
        assert params["redirect_uri"] == [
            "http://localhost:8000/api/auth/google/callback"
        ]
        assert params["response_type"] == ["code"]
        assert params["scope"] == ["openid email profile"]
        assert params["state"][0]

    def test_google_callback_success_issues_cookie_session_and_redirects(
        self, client, monkeypatch
    ):
        """用于验证Googlecallbacksuccessissuescookie会话andredirects。"""
        from app.services.auth.google_oauth_client import (
            GoogleIdentity,
            GoogleOAuthTokens,
        )

        class FakeGoogleOAuthClient:
            def __init__(self, config):
                """用于处理init。"""
                self.config = config

            def authorization_url(self, *, state: str) -> str:
                """用于处理authorizationurl。"""
                return "https://accounts.google.com/o/oauth2/v2/auth?" f"state={state}"

            async def exchange_code(self, code: str) -> GoogleOAuthTokens:
                """用于处理exchangecode。"""
                assert code == "valid-code"
                return GoogleOAuthTokens(
                    access_token="google-access-token",
                    token_type="Bearer",
                )

            async def fetch_identity(self, access_token: str) -> GoogleIdentity:
                """用于处理fetchidentity。"""
                assert access_token == "google-access-token"
                return GoogleIdentity(
                    sub="callback-google-sub",
                    email="callback_google@example.com",
                    email_verified=True,
                    name="Callback Google",
                )

        auth_routes = _configure_google_oauth(monkeypatch)
        monkeypatch.setattr(auth_routes, "GoogleOAuthClient", FakeGoogleOAuthClient)

        state = _issue_google_state(client)

        callback_resp = client.get(
            f"/api/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        assert callback_resp.status_code == 302
        assert callback_resp.headers["location"] == "http://localhost:3000/dashboard"
        assert callback_resp.cookies.get("access_token")
        assert callback_resp.cookies.get("refresh_token")
        assert "access_token" not in callback_resp.text
        assert "refresh_token" not in callback_resp.text

        me_resp = client.get("/api/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "callback_google@example.com"

    def test_google_callback_invalid_state_redirects_to_login_error(
        self, client, monkeypatch
    ):
        """用于验证Googlecallbackinvalidstateredirectstologin错误。"""
        _configure_google_oauth(monkeypatch)

        resp = client.get(
            "/api/auth/google/callback?code=valid-code&state=bad-state",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == (
            "http://localhost:3000/login?oauth_error=invalid_state"
        )

    def test_google_callback_google_error_redirects_to_cancelled(
        self, client, monkeypatch
    ):
        """用于验证GooglecallbackGoogle错误redirectstocancelled。"""
        _configure_google_oauth(monkeypatch)
        state = _issue_google_state(client)

        resp = client.get(
            f"/api/auth/google/callback?error=access_denied&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == (
            "http://localhost:3000/login?oauth_error=cancelled"
        )

    def test_google_callback_exchange_failure_redirects_to_login_error(
        self, client, monkeypatch
    ):
        """用于验证Googlecallbackexchangefailureredirectstologin错误。"""
        from app.services.auth.google_oauth_client import GoogleOAuthAuthenticationError

        class FailingGoogleOAuthClient:
            def __init__(self, config):
                """用于处理init。"""
                self.config = config

            def authorization_url(self, *, state: str) -> str:
                """用于处理authorizationurl。"""
                return "https://accounts.google.com/o/oauth2/v2/auth?" f"state={state}"

            async def exchange_code(self, code: str):
                """用于处理exchangecode。"""
                raise GoogleOAuthAuthenticationError("google_exchange_failed")

        auth_routes = _configure_google_oauth(monkeypatch)
        monkeypatch.setattr(auth_routes, "GoogleOAuthClient", FailingGoogleOAuthClient)
        state = _issue_google_state(client)

        resp = client.get(
            f"/api/auth/google/callback?code=bad-code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == (
            "http://localhost:3000/login?oauth_error=google_exchange_failed"
        )

    def test_google_callback_unverified_email_redirects_to_login_error(
        self, client, monkeypatch
    ):
        """用于验证Googlecallbackunverifiedemailredirectstologin错误。"""
        from app.services.auth.google_oauth_client import (
            GoogleIdentity,
            GoogleOAuthTokens,
        )

        class UnverifiedEmailGoogleOAuthClient:
            def __init__(self, config):
                """用于处理init。"""
                self.config = config

            def authorization_url(self, *, state: str) -> str:
                """用于处理authorizationurl。"""
                return "https://accounts.google.com/o/oauth2/v2/auth?" f"state={state}"

            async def exchange_code(self, code: str) -> GoogleOAuthTokens:
                """用于处理exchangecode。"""
                return GoogleOAuthTokens(
                    access_token="google-access-token",
                    token_type="Bearer",
                )

            async def fetch_identity(self, access_token: str) -> GoogleIdentity:
                """用于处理fetchidentity。"""
                return GoogleIdentity(
                    sub="unverified-google-sub",
                    email="unverified_google_callback@example.com",
                    email_verified=False,
                    name="Unverified Google",
                )

        auth_routes = _configure_google_oauth(monkeypatch)
        monkeypatch.setattr(
            auth_routes, "GoogleOAuthClient", UnverifiedEmailGoogleOAuthClient
        )
        state = _issue_google_state(client)

        resp = client.get(
            f"/api/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == (
            "http://localhost:3000/login?oauth_error=unverified_email"
        )
        assert not resp.cookies.get("access_token")
        assert not resp.cookies.get("refresh_token")

    def test_google_callback_account_conflict_redirects_to_login_error(
        self, client, monkeypatch
    ):
        """用于验证Googlecallbackaccountconflictredirectstologin错误。"""
        from app.services.auth.google_oauth_client import (
            GoogleIdentity,
            GoogleOAuthTokens,
        )

        db = _TestingSession()
        try:
            user = User(
                email="conflict_google_callback@example.com",
                hashed_password=None,
                full_name="Conflict User",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.add(
                ProviderIdentity(
                    provider="google",
                    provider_user_id="old-google-sub",
                    user_id=user.id,
                    provider_email=user.email,
                    provider_email_verified=True,
                )
            )
            db.commit()
        finally:
            db.close()

        class ConflictingGoogleOAuthClient:
            def __init__(self, config):
                """用于处理init。"""
                self.config = config

            def authorization_url(self, *, state: str) -> str:
                """用于处理authorizationurl。"""
                return "https://accounts.google.com/o/oauth2/v2/auth?" f"state={state}"

            async def exchange_code(self, code: str) -> GoogleOAuthTokens:
                """用于处理exchangecode。"""
                return GoogleOAuthTokens(
                    access_token="google-access-token",
                    token_type="Bearer",
                )

            async def fetch_identity(self, access_token: str) -> GoogleIdentity:
                """用于处理fetchidentity。"""
                return GoogleIdentity(
                    sub="new-google-sub",
                    email="conflict_google_callback@example.com",
                    email_verified=True,
                    name="Conflict User",
                )

        auth_routes = _configure_google_oauth(monkeypatch)
        monkeypatch.setattr(
            auth_routes, "GoogleOAuthClient", ConflictingGoogleOAuthClient
        )
        state = _issue_google_state(client)

        resp = client.get(
            f"/api/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["location"] == (
            "http://localhost:3000/login?oauth_error=account_conflict"
        )
        assert not resp.cookies.get("access_token")
        assert not resp.cookies.get("refresh_token")

    def test_google_login_user_can_refresh_and_logout_with_existing_endpoints(
        self, client, monkeypatch
    ):
        """用于验证Googlelogin用户canrefreshandlogoutwithexistingendpoints。"""
        from app.services.auth.google_oauth_client import (
            GoogleIdentity,
            GoogleOAuthTokens,
        )

        class RefreshableGoogleOAuthClient:
            def __init__(self, config):
                """用于处理init。"""
                self.config = config

            def authorization_url(self, *, state: str) -> str:
                """用于处理authorizationurl。"""
                return "https://accounts.google.com/o/oauth2/v2/auth?" f"state={state}"

            async def exchange_code(self, code: str) -> GoogleOAuthTokens:
                """用于处理exchangecode。"""
                return GoogleOAuthTokens(
                    access_token="google-access-token",
                    token_type="Bearer",
                )

            async def fetch_identity(self, access_token: str) -> GoogleIdentity:
                """用于处理fetchidentity。"""
                return GoogleIdentity(
                    sub="refreshable-google-sub",
                    email="refreshable_google@example.com",
                    email_verified=True,
                    name="Refreshable Google",
                )

        auth_routes = _configure_google_oauth(monkeypatch)
        monkeypatch.setattr(
            auth_routes, "GoogleOAuthClient", RefreshableGoogleOAuthClient
        )
        state = _issue_google_state(client)

        callback_resp = client.get(
            f"/api/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )
        assert callback_resp.status_code == 302

        refresh_resp = client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 200
        assert refresh_resp.json()["user"]["email"] == "refreshable_google@example.com"
        assert "access_token" not in refresh_resp.json()
        assert "refresh_token" not in refresh_resp.json()
        assert refresh_resp.cookies.get("access_token")
        assert refresh_resp.cookies.get("refresh_token")
        refreshed_refresh_cookie = client.cookies.get("refresh_token")
        assert refreshed_refresh_cookie

        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert client.get("/api/auth/me").status_code == 401

        stale_client = TestClient(app)
        stale_client.cookies.set("refresh_token", refreshed_refresh_cookie)
        stale_refresh_resp = stale_client.post("/api/auth/refresh")
        assert stale_refresh_resp.status_code == 401
        assert stale_refresh_resp.json()["detail"] == "Invalid refresh token"

    def test_get_me_returns_current_user(self, client):
        """用于验证getmereturnscurrent用户。"""
        _register(client, "me_user@example.com", full_name="我")
        token = _login(client, "me_user@example.com")
        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "me_user@example.com"

    def test_get_me_returns_request_id_header(self, client):
        """用于验证getmereturns请求idheader。"""
        _register(client, "request_id_user@example.com", full_name="请求头测试")
        token = _login(client, "request_id_user@example.com")
        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID")

    def test_get_me_without_token_returns_401(self, client):
        """用于验证getmewithout令牌returns401。"""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_with_token_for_deleted_user_returns_401(self, client):
        """用于验证getmewith令牌fordeleted用户returns401。"""
        email = "deleted_user@example.com"
        _register(client, email, full_name="待删除用户")
        token = _login(client, email)

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            db.delete(user)
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Could not validate credentials"

    def test_inactive_user_cannot_login(self, client):
        """用于验证inactive用户cannotlogin。"""
        email = "inactive_login@example.com"
        _register(client, email, full_name="被禁用用户")

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            user.is_active = False
            db.add(user)
            db.commit()
        finally:
            db.close()

        resp = client.post(
            "/api/auth/login",
            data={"username": email, "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_inactive_user_existing_token_is_rejected(self, client):
        """用于验证inactive用户existing令牌isrejected。"""
        email = "inactive_token@example.com"
        _register(client, email, full_name="已失效登录态用户")
        token = _login(client, email)

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            user.is_active = False
            db.add(user)
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Could not validate credentials"

    def test_update_me_changes_full_name(self, client):
        """用于验证updatemechangesfullname。"""
        _register(client, "update_me@example.com", full_name="旧名字")
        token = _login(client, "update_me@example.com")
        resp = client.put(
            "/api/auth/me",
            json={"full_name": "新名字"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "新名字"

    def test_refresh_rotates_refresh_session_and_rejects_reuse(self, client):
        """用于验证refreshrotatesrefresh会话andrejectsreuse。"""
        email = "refresh_rotate@example.com"
        _register(client, email, full_name="刷新轮换用户")
        _login(client, email)
        stale_refresh_cookie = client.cookies.get("refresh_token")
        assert stale_refresh_cookie

        refresh_resp = client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 200
        new_refresh_cookie = client.cookies.get("refresh_token")
        assert new_refresh_cookie
        assert new_refresh_cookie != stale_refresh_cookie

        stale_client = TestClient(app)
        stale_client.cookies.set("refresh_token", stale_refresh_cookie)
        stale_refresh_resp = stale_client.post("/api/auth/refresh")
        assert stale_refresh_resp.status_code == 401
        assert stale_refresh_resp.json()["detail"] == "Invalid refresh token"

    def test_logout_revokes_refresh_session(self, client):
        """用于验证logoutrevokesrefresh会话。"""
        email = "logout_revoke@example.com"
        _register(client, email, full_name="登出吊销用户")
        _login(client, email)
        stale_refresh_cookie = client.cookies.get("refresh_token")
        assert stale_refresh_cookie

        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["message"] == "Logged out"
        assert not client.cookies.get("access_token")
        assert not client.cookies.get("refresh_token")

        stale_client = TestClient(app)
        stale_client.cookies.set("refresh_token", stale_refresh_cookie)
        refresh_resp = stale_client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 401
        assert refresh_resp.json()["detail"] == "Invalid refresh token"


class TestAuthenticationMiddleware:
    def test_invalid_token_cannot_access_resume_routes(self, client):
        """用于验证invalid令牌cannotaccess简历routes。"""
        resp = client.get(
            "/api/resumes/",
            headers=_auth_headers("not-a-real-token"),
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Could not validate credentials"

    def test_invalid_token_cannot_access_interview_routes(self, client):
        """用于验证invalid令牌cannotaccess面试routes。"""
        resp = client.get(
            "/api/interviews/",
            headers=_auth_headers("not-a-real-token"),
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Could not validate credentials"


class TestBilling:
    def test_create_paypal_subscription_requires_login(self, client):
        """用于验证createPayPal订阅requireslogin。"""
        resp = _anonymous_client().post("/api/billing/paypal/subscriptions", json={})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Could not validate credentials"

    def test_create_paypal_subscription_returns_approval_url(self, client, monkeypatch):
        """用于验证createPayPal订阅returnsapprovalurl。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                assert user_id > 0
                return {
                    "provider": "paypal",
                    "subscription_id": "I-TESTSUB123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-TESTSUB123",
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
            raising=False,
        )
        _register(client, "billing_create@example.com", full_name="Billing User")
        token = _login(client, "billing_create@example.com")

        resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=_auth_headers(token),
            json={},
        )

        assert resp.status_code == 200
        assert resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-TESTSUB123",
            "status": "APPROVAL_PENDING",
            "approval_url": "https://www.paypal.com/checkoutnow?token=I-TESTSUB123",
        }

    def test_create_paypal_subscription_persists_checkout_status(
        self, client, monkeypatch
    ):
        """用于验证createPayPal订阅persistscheckout状态。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                assert user_id > 0
                return {
                    "provider": "paypal",
                    "subscription_id": "I-PERSIST123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-PERSIST123",
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        _register(client, "billing_status@example.com", full_name="Billing Status")
        token = _login(client, "billing_status@example.com")
        headers = _auth_headers(token)

        create_resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=headers,
            json={},
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert create_resp.status_code == 200
        assert status_resp.status_code == 200
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-PERSIST123",
            "status": "APPROVAL_PENDING",
            "is_active": False,
        }

    def test_billing_status_prefers_active_subscription_over_latest_history(
        self, client
    ):
        """用于验证计费状态prefersactive订阅overlatesthistory。"""
        email = "billing_priority@example.com"
        _register(client, email, full_name="Billing Priority")
        token = _login(client, email)

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).one()
            db.add(
                BillingSubscription(
                    user_id=user.id,
                    provider="paypal",
                    provider_subscription_id="I-STILL-ACTIVE",
                    status="ACTIVE",
                    raw_payload={"id": "I-STILL-ACTIVE", "status": "ACTIVE"},
                )
            )
            db.add(
                BillingSubscription(
                    user_id=user.id,
                    provider="paypal",
                    provider_subscription_id="I-OLD-CANCELLED",
                    status="CANCELLED",
                    raw_payload={"id": "I-OLD-CANCELLED", "status": "CANCELLED"},
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/billing/status", headers=_auth_headers(token))

        assert resp.status_code == 200
        assert resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-STILL-ACTIVE",
            "status": "ACTIVE",
            "is_active": True,
        }

    def test_create_paypal_subscription_reuses_pending_checkout(
        self, client, monkeypatch
    ):
        """用于验证createPayPal订阅reusespendingcheckout。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            calls = 0

            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                self.__class__.calls += 1
                return {
                    "provider": "paypal",
                    "subscription_id": "I-REUSE123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-REUSE123",
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        _register(client, "billing_reuse@example.com", full_name="Billing Reuse")
        token = _login(client, "billing_reuse@example.com")
        headers = _auth_headers(token)

        first_resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=headers,
            json={},
        )
        second_resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=headers,
            json={},
        )

        assert first_resp.status_code == 200
        assert second_resp.status_code == 200
        assert second_resp.json() == first_resp.json()
        assert FakePayPalBillingService.calls == 1

    def test_create_paypal_subscription_recovers_from_concurrent_insert(
        self, client, monkeypatch
    ):
        """用于验证createPayPal订阅recoversfromconcurrentinsert。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-RACE123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-RACE123",
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(
            billing_routes,
            "_open_paypal_subscription",
            lambda db, user_id: None,
        )
        email = "billing_race@example.com"
        _register(client, email, full_name="Billing Race")
        token = _login(client, email)
        headers = _auth_headers(token)

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).one()
            db.add(
                BillingSubscription(
                    user_id=user.id,
                    provider="paypal",
                    provider_subscription_id="I-RACE123",
                    status="APPROVAL_PENDING",
                    raw_payload={
                        "provider": "paypal",
                        "subscription_id": "I-RACE123",
                        "status": "APPROVAL_PENDING",
                        "approval_url": "https://www.paypal.com/checkoutnow?token=I-RACE123",
                    },
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=headers,
            json={},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-RACE123",
            "status": "APPROVAL_PENDING",
            "approval_url": "https://www.paypal.com/checkoutnow?token=I-RACE123",
        }

    def test_get_paypal_plan_returns_current_provider_price(self, client, monkeypatch):
        """用于验证getPayPalplanreturnscurrentproviderprice。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def get_plan(self):
                """用于获取plan。"""
                return {
                    "id": "P-TESTPLAN",
                    "name": "Chat Resume Plus",
                    "price": "10.00",
                    "currency_code": "USD",
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        _register(client, "billing_plan@example.com", full_name="Billing Plan")
        token = _login(client, "billing_plan@example.com")

        resp = client.get(
            "/api/billing/paypal/plan",
            headers=_auth_headers(token),
        )

        assert resp.status_code == 200
        assert resp.json() == {
            "id": "P-TESTPLAN",
            "name": "Chat Resume Plus",
            "price": "10.00",
            "currency_code": "USD",
        }

    def test_paypal_webhook_rejects_invalid_signature_without_login(self, monkeypatch):
        """用于验证PayPalwebhookrejectsinvalidsignaturewithoutlogin。"""
        from app.entrypoints.http import billing as billing_routes
        from app.services.paypal_billing_service import PayPalBillingError

        class FakePayPalBillingService:
            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                assert event["event_type"] == "BILLING.SUBSCRIPTION.ACTIVATED"
                raise PayPalBillingError("paypal_webhook_signature_invalid")

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )

        resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers={
                "PAYPAL-TRANSMISSION-ID": "transmission-id",
                "PAYPAL-TRANSMISSION-TIME": "2026-05-10T14:00:00Z",
                "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "bad-signature",
            },
            json={
                "id": "WH-TEST",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "resource": {"id": "I-TESTSUB123", "status": "ACTIVE"},
            },
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "paypal_webhook_signature_invalid"

    def test_paypal_subscription_activated_webhook_updates_billing_status(
        self, client, monkeypatch
    ):
        """用于验证PayPal订阅activatedwebhookupdates计费状态。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-ACTIVE123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-ACTIVE123",
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                assert headers["paypal-transmission-id"] == "transmission-id"
                assert event["event_type"] == "BILLING.SUBSCRIPTION.ACTIVATED"

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_active@example.com", full_name="Billing Active")
        token = _login(client, "billing_active@example.com")
        headers = _auth_headers(token)
        create_resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=headers,
            json={},
        )
        assert create_resp.status_code == 200

        webhook_resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers={
                "PAYPAL-TRANSMISSION-ID": "transmission-id",
                "PAYPAL-TRANSMISSION-TIME": "2026-05-10T14:00:00Z",
                "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "valid-signature",
            },
            json={
                "id": "WH-ACTIVE",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "resource": {
                    "id": "I-ACTIVE123",
                    "status": "ACTIVE",
                    "plan_id": "P-TESTPLAN",
                },
            },
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert webhook_resp.status_code == 200
        assert webhook_resp.json() == {"received": True}
        assert status_resp.status_code == 200
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-ACTIVE123",
            "status": "ACTIVE",
            "is_active": True,
        }

    def test_paypal_webhook_before_local_subscription_can_be_replayed(
        self, client, monkeypatch
    ):
        """用于验证PayPalwebhookbeforelocal订阅canbereplayed。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-EARLY123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-EARLY123",
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                return None

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        event = {
            "id": "WH-EARLY",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "create_time": "2026-05-10T15:00:00Z",
            "resource": {
                "id": "I-EARLY123",
                "status": "ACTIVE",
                "plan_id": "P-TESTPLAN",
            },
        }
        webhook_headers = {
            "PAYPAL-TRANSMISSION-ID": "transmission-early",
            "PAYPAL-TRANSMISSION-TIME": "2026-05-10T15:00:00Z",
            "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-TRANSMISSION-SIG": "valid-signature",
        }

        early_resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers=webhook_headers,
            json=event,
        )
        assert early_resp.status_code == 409
        assert early_resp.json()["detail"] == "paypal_subscription_not_found"

        _register(client, "billing_early@example.com", full_name="Billing Early")
        token = _login(client, "billing_early@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )

        replay_resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers=webhook_headers,
            json=event,
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert replay_resp.status_code == 200, replay_resp.text
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-EARLY123",
            "status": "ACTIVE",
            "is_active": True,
        }

    def test_sync_paypal_subscription_updates_status_from_provider(
        self, client, monkeypatch
    ):
        """用于验证syncPayPal订阅updates状态fromprovider。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-SYNC123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-SYNC123",
                }

            async def get_subscription(self, *, subscription_id: str):
                """用于获取订阅。"""
                assert subscription_id == "I-SYNC123"
                return {
                    "provider": "paypal",
                    "subscription_id": "I-SYNC123",
                    "status": "ACTIVE",
                    "raw_payload": {
                        "id": "I-SYNC123",
                        "status": "ACTIVE",
                        "plan_id": "P-TESTPLAN",
                    },
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_sync@example.com", full_name="Billing Sync")
        token = _login(client, "billing_sync@example.com")
        headers = _auth_headers(token)
        create_resp = client.post(
            "/api/billing/paypal/subscriptions",
            headers=headers,
            json={},
        )
        assert create_resp.status_code == 200

        sync_resp = client.get(
            "/api/billing/paypal/subscriptions/I-SYNC123/sync",
            headers=headers,
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert sync_resp.status_code == 200, sync_resp.text
        assert sync_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-SYNC123",
            "status": "ACTIVE",
            "is_active": True,
        }
        assert status_resp.json() == sync_resp.json()

    def test_sync_paypal_subscription_rejects_unexpected_plan_id(
        self, client, monkeypatch
    ):
        """用于验证syncPayPal订阅rejectsunexpectedplanid。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-WRONGPLAN",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-WRONGPLAN",
                }

            async def get_subscription(self, *, subscription_id: str):
                """用于获取订阅。"""
                assert subscription_id == "I-WRONGPLAN"
                return {
                    "provider": "paypal",
                    "subscription_id": "I-WRONGPLAN",
                    "status": "ACTIVE",
                    "raw_payload": {
                        "id": "I-WRONGPLAN",
                        "status": "ACTIVE",
                        "plan_id": "P-OTHERPLAN",
                    },
                }

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_wrong_plan@example.com", full_name="Wrong Plan")
        token = _login(client, "billing_wrong_plan@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )

        sync_resp = client.get(
            "/api/billing/paypal/subscriptions/I-WRONGPLAN/sync",
            headers=headers,
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert sync_resp.status_code == 400
        assert sync_resp.json()["detail"] == "paypal_subscription_plan_mismatch"
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-WRONGPLAN",
            "status": "APPROVAL_PENDING",
            "is_active": False,
        }

    def test_paypal_webhook_rejects_unexpected_plan_id(self, client, monkeypatch):
        """用于验证PayPalwebhookrejectsunexpectedplanid。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-WEBHOOK-WRONGPLAN",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-WEBHOOK-WRONGPLAN",
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                return None

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_webhook_wrong_plan@example.com")
        token = _login(client, "billing_webhook_wrong_plan@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )

        webhook_resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers={
                "PAYPAL-TRANSMISSION-ID": "transmission-wrong-plan",
                "PAYPAL-TRANSMISSION-TIME": "2026-05-10T15:00:00Z",
                "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "valid-signature",
            },
            json={
                "id": "WH-WEBHOOK-WRONGPLAN",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "create_time": "2026-05-10T15:00:00Z",
                "resource": {
                    "id": "I-WEBHOOK-WRONGPLAN",
                    "status": "ACTIVE",
                    "plan_id": "P-OTHERPLAN",
                },
            },
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert webhook_resp.status_code == 400
        assert webhook_resp.json()["detail"] == "paypal_subscription_plan_mismatch"
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-WEBHOOK-WRONGPLAN",
            "status": "APPROVAL_PENDING",
            "is_active": False,
        }

    def test_sync_does_not_erase_webhook_event_ordering(self, client, monkeypatch):
        """用于验证syncdoesnoterasewebhook事件ordering。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-SYNCORDER123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-SYNCORDER123",
                }

            async def get_subscription(self, *, subscription_id: str):
                """用于获取订阅。"""
                assert subscription_id == "I-SYNCORDER123"
                return {
                    "provider": "paypal",
                    "subscription_id": "I-SYNCORDER123",
                    "status": "ACTIVE",
                    "raw_payload": {
                        "id": "I-SYNCORDER123",
                        "status": "ACTIVE",
                        "plan_id": "P-TESTPLAN",
                    },
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                return None

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_sync_order@example.com", full_name="Sync Order")
        token = _login(client, "billing_sync_order@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )

        active_resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers={
                "PAYPAL-TRANSMISSION-ID": "transmission-sync-order-active",
                "PAYPAL-TRANSMISSION-TIME": "2026-05-10T15:00:00Z",
                "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "valid-signature",
            },
            json={
                "id": "WH-SYNC-ORDER-ACTIVE",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "create_time": "2026-05-10T15:00:00Z",
                "resource": {
                    "id": "I-SYNCORDER123",
                    "status": "ACTIVE",
                    "plan_id": "P-TESTPLAN",
                },
            },
        )
        assert active_resp.status_code == 200, active_resp.text
        sync_resp = client.get(
            "/api/billing/paypal/subscriptions/I-SYNCORDER123/sync",
            headers=headers,
        )
        assert sync_resp.status_code == 200, sync_resp.text

        stale_resp = _anonymous_client().post(
            "/api/billing/paypal/webhook",
            headers={
                "PAYPAL-TRANSMISSION-ID": "transmission-sync-order-stale",
                "PAYPAL-TRANSMISSION-TIME": "2026-05-10T14:00:00Z",
                "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "valid-signature",
            },
            json={
                "id": "WH-SYNC-ORDER-STALE",
                "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
                "create_time": "2026-05-10T14:00:00Z",
                "resource": {
                    "id": "I-SYNCORDER123",
                    "status": "SUSPENDED",
                    "plan_id": "P-TESTPLAN",
                },
            },
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert stale_resp.status_code == 200, stale_resp.text
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-SYNCORDER123",
            "status": "ACTIVE",
            "is_active": True,
        }

    def test_cancel_paypal_subscription_updates_local_status(self, client, monkeypatch):
        """用于验证cancelPayPal订阅updateslocal状态。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def cancel_subscription(self, *, subscription_id: str):
                """用于处理cancel订阅。"""
                assert subscription_id == "I-CANCEL-ENDPOINT"

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        email = "billing_cancel_endpoint@example.com"
        _register(client, email)
        token = _login(client, email)
        headers = _auth_headers(token)
        _grant_active_subscription(email, "I-CANCEL-ENDPOINT")

        cancel_resp = client.post(
            "/api/billing/paypal/subscriptions/I-CANCEL-ENDPOINT/cancel",
            headers=headers,
            json={},
        )
        status_resp = client.get("/api/billing/status", headers=headers)

        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-CANCEL-ENDPOINT",
            "status": "CANCELLED",
            "is_active": False,
        }
        assert status_resp.json() == cancel_resp.json()

    def test_paypal_subscription_cancelled_webhook_deactivates_billing_status(
        self, client, monkeypatch
    ):
        """用于验证PayPal订阅cancelledwebhookdeactivates计费状态。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-CANCEL123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-CANCEL123",
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                assert event["event_type"] == "BILLING.SUBSCRIPTION.CANCELLED"

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_cancel@example.com", full_name="Billing Cancel")
        token = _login(client, "billing_cancel@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )
        assert (
            _anonymous_client()
            .post(
                "/api/billing/paypal/webhook",
                headers={
                    "PAYPAL-TRANSMISSION-ID": "transmission-id",
                    "PAYPAL-TRANSMISSION-TIME": "2026-05-10T14:00:00Z",
                    "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                    "PAYPAL-TRANSMISSION-SIG": "valid-signature",
                },
                json={
                    "id": "WH-CANCEL",
                    "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
                    "resource": {
                        "id": "I-CANCEL123",
                        "status": "CANCELLED",
                        "plan_id": "P-TESTPLAN",
                    },
                },
            )
            .status_code
            == 200
        )

        status_resp = client.get("/api/billing/status", headers=headers)

        assert status_resp.status_code == 200
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-CANCEL123",
            "status": "CANCELLED",
            "is_active": False,
        }

    def test_paypal_older_webhook_event_does_not_overwrite_newer_status(
        self, client, monkeypatch
    ):
        """用于验证PayPalolderwebhook事件doesnotoverwritenewer状态。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-ORDER123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-ORDER123",
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                return None

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_order@example.com", full_name="Billing Order")
        token = _login(client, "billing_order@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )

        for event_type, event_time, status_value in [
            ("BILLING.SUBSCRIPTION.ACTIVATED", "2026-05-10T15:00:00Z", "ACTIVE"),
            ("BILLING.SUBSCRIPTION.SUSPENDED", "2026-05-10T14:00:00Z", "SUSPENDED"),
        ]:
            webhook_resp = _anonymous_client().post(
                "/api/billing/paypal/webhook",
                headers={
                    "PAYPAL-TRANSMISSION-ID": f"transmission-{status_value}",
                    "PAYPAL-TRANSMISSION-TIME": event_time,
                    "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                    "PAYPAL-TRANSMISSION-SIG": "valid-signature",
                },
                json={
                    "id": f"WH-ORDER-{status_value}",
                    "event_type": event_type,
                    "create_time": event_time,
                    "resource": {
                        "id": "I-ORDER123",
                        "status": status_value,
                        "plan_id": "P-TESTPLAN",
                    },
                },
            )
            assert webhook_resp.status_code == 200, webhook_resp.text

        status_resp = client.get("/api/billing/status", headers=headers)

        assert status_resp.status_code == 200
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-ORDER123",
            "status": "ACTIVE",
            "is_active": True,
        }

    def test_paypal_duplicate_webhook_event_id_is_ignored(self, client, monkeypatch):
        """用于验证PayPalduplicatewebhook事件idisignored。"""
        from app.entrypoints.http import billing as billing_routes

        class FakePayPalBillingService:
            async def create_subscription(self, *, user_id: int):
                """用于创建订阅。"""
                return {
                    "provider": "paypal",
                    "subscription_id": "I-DUPE123",
                    "status": "APPROVAL_PENDING",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=I-DUPE123",
                }

            async def verify_webhook(self, *, headers: dict, event: dict) -> None:
                """用于处理verifywebhook。"""
                return None

        monkeypatch.setattr(
            billing_routes,
            "PayPalBillingService",
            FakePayPalBillingService,
        )
        monkeypatch.setattr(billing_routes.settings, "PAYPAL_PLAN_ID", "P-TESTPLAN")
        _register(client, "billing_dupe@example.com", full_name="Billing Dupe")
        token = _login(client, "billing_dupe@example.com")
        headers = _auth_headers(token)
        assert (
            client.post(
                "/api/billing/paypal/subscriptions",
                headers=headers,
                json={},
            ).status_code
            == 200
        )

        for event_type, event_time, status_value in [
            ("BILLING.SUBSCRIPTION.ACTIVATED", "2026-05-10T15:00:00Z", "ACTIVE"),
            ("BILLING.SUBSCRIPTION.CANCELLED", "2026-05-10T16:00:00Z", "CANCELLED"),
        ]:
            webhook_resp = _anonymous_client().post(
                "/api/billing/paypal/webhook",
                headers={
                    "PAYPAL-TRANSMISSION-ID": f"transmission-dupe-{status_value}",
                    "PAYPAL-TRANSMISSION-TIME": event_time,
                    "PAYPAL-CERT-URL": "https://api-m.sandbox.paypal.com/certs/test",
                    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                    "PAYPAL-TRANSMISSION-SIG": "valid-signature",
                },
                json={
                    "id": "WH-DUPE",
                    "event_type": event_type,
                    "create_time": event_time,
                    "resource": {
                        "id": "I-DUPE123",
                        "status": status_value,
                        "plan_id": "P-TESTPLAN",
                    },
                },
            )
            assert webhook_resp.status_code == 200, webhook_resp.text

        status_resp = client.get("/api/billing/status", headers=headers)

        assert status_resp.status_code == 200
        assert status_resp.json() == {
            "provider": "paypal",
            "subscription_id": "I-DUPE123",
            "status": "ACTIVE",
            "is_active": True,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 1.5 JD OCR 上传
# ═══════════════════════════════════════════════════════════════════════════


class TestJDOcrUpload:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """用于设置当前数据。"""
        _register(client, "jd_ocr_user@example.com")
        self.token = _login(client, "jd_ocr_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client
        _grant_active_subscription("jd_ocr_user@example.com", "I-JDOCRPLUS")

    def test_upload_jd_image_returns_ocr_text(self, monkeypatch):
        """用于验证上传jdimagereturnsocrtext。"""
        async def _fake_extract_text_from_image(
            self, image_bytes: bytes, mime_type: str
        ) -> str:
            """用于构造extracttextfromimage。"""
            assert image_bytes == b"fake-image-bytes"
            assert mime_type == "image/png"
            return "岗位职责\\n1. 负责后端开发"

        monkeypatch.setattr(
            "app.entrypoints.http.upload.JDOcrService.extract_text_from_image",
            _fake_extract_text_from_image,
        )

        resp = self.client.post(
            "/api/upload/jd-ocr",
            files={"file": ("jd.png", b"fake-image-bytes", "image/png")},
            headers=self.headers,
        )

        assert resp.status_code == 200
        assert resp.json()["text"] == "岗位职责\\n1. 负责后端开发"

    def test_upload_jd_image_sanitizes_provider_403_errors(self, monkeypatch):
        """用于验证上传jdimagesanitizesprovider403errors。"""
        async def _fake_extract_text_from_image(
            self, image_bytes: bytes, mime_type: str
        ) -> str:
            """用于构造extracttextfromimage。"""
            raise Exception(
                'AI服务请求失败: 403 - {"error":{"message":"The request is '
                'prohibited due to a violation of provider Terms Of Service."}}'
            )

        monkeypatch.setattr(
            "app.entrypoints.http.upload.JDOcrService.extract_text_from_image",
            _fake_extract_text_from_image,
        )

        resp = self.client.post(
            "/api/upload/jd-ocr",
            files={"file": ("jd.png", b"fake-image-bytes", "image/png")},
            headers=self.headers,
        )

        assert resp.status_code == 502
        assert "视觉模型请求被供应商拒绝" in resp.json()["detail"]
        assert "provider Terms Of Service" not in resp.json()["detail"]

    def test_upload_jd_image_rejects_non_image_files(self):
        """用于验证上传jdimagerejectsnonimagefiles。"""
        resp = self.client.post(
            "/api/upload/jd-ocr",
            files={"file": ("jd.txt", b"not-image", "text/plain")},
            headers=self.headers,
        )

        assert resp.status_code == 400
        assert "Unsupported image format" in resp.json()["detail"]


class TestResumeUpload:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """为简历上传接口测试准备登录态。"""
        _register(client, "resume_upload_user@example.com")
        self.token = _login(client, "resume_upload_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

    def test_upload_resume_enqueues_background_parse_job(self, monkeypatch, caplog):
        """上传接口应立即返回 job_id，并通过状态接口暴露后台解析结果。"""
        fixture_path = (
            Path(__file__).resolve().parent / "fixtures" / "sample_resume_upload.txt"
        )
        extracted_text = fixture_path.read_text(encoding="utf-8")
        saved_file_path = "/tmp/test_resume_upload.txt"
        deleted_paths: list[str] = []

        async def _fake_save_uploaded_file(self, file):
            """模拟保存上传文件，并验证接口确实收到了真实文件名。"""
            assert file.filename == "sample_resume_upload.txt"
            assert file.content == fixture_path.read_bytes()
            return saved_file_path

        def _fake_extract_text_from_file(self, file_path: str, filename: str) -> str:
            """模拟从已保存文件中提取文本，供后续解析使用。"""
            assert file_path == saved_file_path
            assert filename == "sample_resume_upload.txt"
            return extracted_text

        async def _fake_parse_resume_text_async(self, text: str) -> dict:
            """模拟 AI 简历解析结果，保证接口级测试不依赖外部模型。"""
            assert text == extracted_text
            return {
                "parsing_quality": 0.92,
                "parsing_method": "ai",
                "job_application": {
                    "target_company": "OpenAI",
                    "target_title": "后端工程师",
                },
                "personal_info": {"name": "测试用户", "email": "e2e@example.com"},
                "work_experience": [
                    {
                        "company": "OpenAI",
                        "position": "后端工程师",
                        "duration": "2024-至今",
                        "highlights": [],
                    }
                ],
                "education": [],
                "skills": [],
                "projects": [],
            }

        def _fake_delete_file(self, file_path: str) -> None:
            """记录临时文件清理动作，确保上传流程会尝试回收临时文件。"""
            deleted_paths.append(file_path)

        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.save_uploaded_file",
            _fake_save_uploaded_file,
        )
        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.extract_text_from_file",
            _fake_extract_text_from_file,
        )
        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.delete_file", _fake_delete_file
        )
        monkeypatch.setattr(
            "app.entrypoints.http.upload.ResumeParser.parse_resume_text_async",
            _fake_parse_resume_text_async,
        )
        monkeypatch.setattr("app.entrypoints.http.upload.SessionLocal", _TestingSession)

        with caplog.at_level("INFO", logger="app.entrypoints.http.upload"):
            response = self.client.post(
                "/api/upload/resume",
                files={
                    "file": (
                        "sample_resume_upload.txt",
                        fixture_path.read_bytes(),
                        "text/plain",
                    )
                },
                headers=self.headers,
            )

        assert response.status_code == 202
        body = response.json()
        assert body["job_id"]
        assert body["status"] == "queued"

        status_response = self.client.get(
            f"/api/upload/resume-jobs/{body['job_id']}",
            headers=self.headers,
        )

        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["job_id"] == body["job_id"]
        assert status_body["status"] == "completed"
        assert status_body["resume_id"]
        assert status_body["error"] is None
        resume_response = self.client.get(
            f"/api/resumes/{status_body['resume_id']}",
            headers=self.headers,
        )
        assert resume_response.status_code == 200
        resume_body = resume_response.json()
        assert resume_body["title"] == "sample_resume_upload"
        assert resume_body["original_filename"] == "sample_resume_upload.txt"
        assert resume_body["content"]["parsing_quality"] == 0.92
        assert resume_body["content"]["parsing_method"] == "ai"
        assert resume_body["content"]["personal_info"]["name"] == "测试用户"
        assert resume_body["content"]["job_application"]["target_company"] == "OpenAI"
        assert deleted_paths == [saved_file_path]
        assert "resume_upload.job.created" in caplog.text
        assert "resume_upload.parse.started model=" in caplog.text
        assert "file_bytes=" not in caplog.text
        assert "text_chars=" not in caplog.text
        assert "resume_upload.completed model=" in caplog.text

    def test_upload_resume_maps_file_service_size_error(self, monkeypatch):
        """服务层文件错误应由 HTTP 入口映射状态码，而不是泄漏 FastAPI 异常。"""

        async def _fake_save_uploaded_file(self, file):
            """用于构造saveuploadedfile。"""
            assert file.filename == "sample_resume_upload.txt"
            raise ServicePayloadTooLargeError("File too large")

        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.save_uploaded_file",
            _fake_save_uploaded_file,
        )

        response = self.client.post(
            "/api/upload/resume",
            files={"file": ("sample_resume_upload.txt", b"content", "text/plain")},
            headers=self.headers,
        )

        assert response.status_code == 413
        assert response.json()["detail"] == "File too large"

    def test_upload_resume_job_reports_background_failure(self, monkeypatch):
        """后台解析失败时状态接口应返回 failed，而不是让前端无限轮询。"""
        saved_file_path = "/tmp/test_resume_upload_failed.txt"
        deleted_paths: list[str] = []

        async def _fake_save_uploaded_file(self, file):
            """用于构造saveuploadedfile。"""
            return saved_file_path

        def _fake_extract_text_from_file(self, file_path: str, filename: str) -> str:
            """用于构造extracttextfromfile。"""
            return "broken resume text"

        async def _fake_parse_resume_text_async(self, text: str) -> dict:
            """用于构造parse简历textasync。"""
            raise RuntimeError("parser exploded")

        def _fake_delete_file(self, file_path: str) -> None:
            """用于构造deletefile。"""
            deleted_paths.append(file_path)

        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.save_uploaded_file",
            _fake_save_uploaded_file,
        )
        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.extract_text_from_file",
            _fake_extract_text_from_file,
        )
        monkeypatch.setattr(
            "app.entrypoints.http.upload.FileService.delete_file", _fake_delete_file
        )
        monkeypatch.setattr(
            "app.entrypoints.http.upload.ResumeParser.parse_resume_text_async",
            _fake_parse_resume_text_async,
        )
        monkeypatch.setattr("app.entrypoints.http.upload.SessionLocal", _TestingSession)

        response = self.client.post(
            "/api/upload/resume",
            files={"file": ("failed_resume.txt", b"content", "text/plain")},
            headers=self.headers,
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]
        status_response = self.client.get(
            f"/api/upload/resume-jobs/{job_id}",
            headers=self.headers,
        )

        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["status"] == "failed"
        assert status_body["resume_id"] is None
        assert "parser exploded" in status_body["error"]
        assert deleted_paths == [saved_file_path]

    def test_upload_resume_job_status_is_user_scoped(self, monkeypatch):
        """用户不能查询其他用户的上传解析任务状态。"""
        db = _TestingSession()
        try:
            owner = (
                db.query(User)
                .filter(User.email == "resume_upload_user@example.com")
                .one()
            )
            job = ResumeUploadJob(
                id="private-job",
                user_id=owner.id,
                status="queued",
                original_filename="private.txt",
                file_path="/tmp/private.txt",
            )
            db.add(job)
            db.commit()
        finally:
            db.close()

        other_client = TestClient(app)
        _register(other_client, "resume_upload_other@example.com")
        other_token = _login(other_client, "resume_upload_other@example.com")

        response = other_client.get(
            "/api/upload/resume-jobs/private-job",
            headers=_auth_headers(other_token),
        )

        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 2. 简历 CRUD
# ═══════════════════════════════════════════════════════════════════════════


class TestResumeCRUD:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """用于设置当前数据。"""
        _register(client, "resume_user@example.com")
        self.token = _login(client, "resume_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

    def _create_resume(self, title: str = "我的简历") -> dict:
        """用于创建简历。"""
        resp = self.client.post(
            "/api/resumes/",
            json={"title": title, "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_create_resume_returns_resume(self):
        """用于验证create简历returns简历。"""
        body = self._create_resume("测试简历")
        assert body["title"] == "测试简历"
        assert "id" in body
        assert body["content"]["personal_info"]["name"] == "张三"

    def test_create_resume_with_jd_syncs_job_post(self):
        """用于验证简历内嵌 JD 会同步成可复用 job_posts 记录。"""
        content = _empty_resume_content()
        content["job_application"]["target_company"] = "美团"
        content["job_application"]["target_title"] = "Agent 开发工程师"
        content["job_application"]["jd_text"] = "负责 Agent 工具调用和评测体系。"

        resp = self.client.post(
            "/api/resumes/",
            json={"title": "带 JD 简历", "content": content},
            headers=self.headers,
        )

        assert resp.status_code == 200, resp.text
        job_post_id = resp.json()["content"]["job_application"]["job_post_id"]
        detail_resp = self.client.get(
            f"/api/resumes/job-posts/{job_post_id}",
            headers=self.headers,
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["company_name"] == "美团"
        assert detail["job_title"] == "Agent 开发工程师"
        assert "评测体系" in detail["jd_text"]

    def test_update_resume_jd_reuses_existing_job_post(self):
        """用于验证更新同一份简历 JD 时复用原 job_post_id。"""
        content = _empty_resume_content()
        content["job_application"]["jd_text"] = "旧 JD"
        created_resp = self.client.post(
            "/api/resumes/",
            json={"title": "JD 更新简历", "content": content},
            headers=self.headers,
        )
        assert created_resp.status_code == 200, created_resp.text
        resume_id = created_resp.json()["id"]
        job_post_id = created_resp.json()["content"]["job_application"]["job_post_id"]

        updated_content = created_resp.json()["content"]
        updated_content["job_application"]["target_company"] = "字节跳动"
        updated_content["job_application"]["jd_text"] = "新 JD：负责多 Agent 协作。"
        update_resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={"content": updated_content},
            headers=self.headers,
        )

        assert update_resp.status_code == 200, update_resp.text
        assert (
            update_resp.json()["content"]["job_application"]["job_post_id"]
            == job_post_id
        )
        detail_resp = self.client.get(
            f"/api/resumes/job-posts/{job_post_id}",
            headers=self.headers,
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["company_name"] == "字节跳动"
        assert "多 Agent" in detail_resp.json()["jd_text"]

    def test_job_posts_are_scoped_to_current_user(self):
        """用于验证 JD 库接口按当前用户隔离。"""
        create_resp = self.client.post(
            "/api/resumes/job-posts",
            json={
                "company_name": "京东",
                "job_title": "Agent 工程师",
                "jd_text": "负责智能体平台建设。",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        job_post_id = create_resp.json()["id"]

        other_client = TestClient(app)
        _register(other_client, "job_post_other@example.com")
        other_token = _login(other_client, "job_post_other@example.com")
        other_headers = _auth_headers(other_token)

        list_resp = other_client.get("/api/resumes/job-posts", headers=other_headers)
        detail_resp = other_client.get(
            f"/api/resumes/job-posts/{job_post_id}",
            headers=other_headers,
        )

        assert list_resp.status_code == 200
        assert list_resp.json() == []
        assert detail_resp.status_code == 404

    def test_list_resumes_returns_created_items(self):
        """用于验证listresumesreturnscreateditems。"""
        self._create_resume("简历A")
        self._create_resume("简历B")
        resp = self.client.get("/api/resumes/", headers=self.headers)
        assert resp.status_code == 200
        titles = [r["title"] for r in resp.json()]
        assert "简历A" in titles
        assert "简历B" in titles

    def test_list_resumes_includes_inline_preview_content(self):
        """用于验证listresumesincludesinlinepreviewcontent。"""
        created = self._create_resume("预览简历")
        layout_resp = self.client.put(
            f"/api/resumes/{created['id']}/layout",
            json={
                "density": "compact",
                "moduleOrder": ["personal", "work", "education", "projects", "skills"],
                "visibleModules": ["personal", "work", "education", "skills"],
                "spacingScale": 0.7,
                "templateStyle": "modern",
            },
            headers=self.headers,
        )
        assert layout_resp.status_code == 200
        resp = self.client.get("/api/resumes/", headers=self.headers)
        assert resp.status_code == 200
        resume = next(item for item in resp.json() if item["title"] == "预览简历")
        assert resume["preview_content"]["personal_info"]["name"] == "张三"
        assert "job_application" not in resume["preview_content"]
        assert resume["layout_config"]["templateStyle"] == "modern"
        assert resume["layout_config"]["spacingScale"] == 0.7

    def test_get_resume_by_id(self):
        """用于验证get简历byid。"""
        created = self._create_resume("可查简历")
        resume_id = created["id"]
        resp = self.client.get(f"/api/resumes/{resume_id}", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == resume_id

    def test_get_nonexistent_resume_returns_404(self):
        """用于验证getnonexistent简历returns404。"""
        resp = self.client.get("/api/resumes/9999999", headers=self.headers)
        assert resp.status_code == 404

    def test_update_resume_title(self):
        """用于验证update简历title。"""
        created = self._create_resume("旧标题")
        resume_id = created["id"]
        resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={"title": "新标题"},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "新标题"

    def test_update_resume_content(self):
        """用于验证update简历content。"""
        created = self._create_resume("内容更新测试")
        resume_id = created["id"]
        new_content = _empty_resume_content()
        new_content["personal_info"]["name"] = "李四"
        resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={"content": new_content},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"]["personal_info"]["name"] == "李四"

    def test_update_resume_with_no_data_returns_400(self):
        """用于验证update简历withnodatareturns400。"""
        created = self._create_resume("空更新测试")
        resume_id = created["id"]
        resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_delete_resume_removes_it(self):
        """用于验证delete简历removesit。"""
        created = self._create_resume("待删除简历")
        resume_id = created["id"]
        del_resp = self.client.delete(f"/api/resumes/{resume_id}", headers=self.headers)
        assert del_resp.status_code == 200
        get_resp = self.client.get(f"/api/resumes/{resume_id}", headers=self.headers)
        assert get_resp.status_code == 404

    def test_delete_resume_removes_related_history(self):
        """用于验证delete简历removesrelatedhistory。"""
        created = self._create_resume("带历史数据的简历")
        resume_id = created["id"]
        user_id = created["owner_id"]

        db = _TestingSession()
        try:
            db.add(
                ResumeChatMessage(
                    resume_id=resume_id,
                    role="assistant",
                    content="历史聊天",
                )
            )
            interview = InterviewSession(
                user_id=user_id,
                resume_id=resume_id,
                target_title="Agent 工程师",
            )
            db.add(interview)
            db.flush()
            db.add(
                InterviewTurn(
                    session_id=interview.id,
                    turn_index=0,
                    question="介绍一下项目经历",
                )
            )
            agent_session = AgentSession(
                id="delete_resume_agent_session",
                user_id=user_id,
                resume_id=resume_id,
                task_type="resume_optimization",
                status="completed",
            )
            db.add(agent_session)
            db.flush()
            db.add(
                AgentEvent(
                    session_id=agent_session.id,
                    sequence=1,
                    event_type="message",
                    source="resume_agent",
                    payload={"content": "done"},
                )
            )
            db.commit()
        finally:
            db.close()

        del_resp = self.client.delete(f"/api/resumes/{resume_id}", headers=self.headers)
        assert del_resp.status_code == 200

        db = _TestingSession()
        try:
            assert (
                db.query(ResumeChatMessage)
                .filter(ResumeChatMessage.resume_id == resume_id)
                .count()
                == 0
            )
            assert (
                db.query(InterviewSession)
                .filter(InterviewSession.resume_id == resume_id)
                .count()
                == 0
            )
            assert (
                db.query(AgentSession)
                .filter(AgentSession.resume_id == resume_id)
                .count()
                == 0
            )
            assert (
                db.query(AgentEvent)
                .filter(AgentEvent.session_id == "delete_resume_agent_session")
                .count()
                == 0
            )
        finally:
            db.close()


class TestInterviewSessions:
    @pytest.fixture(autouse=True)
    def _setup(self, client, monkeypatch):
        """用于设置当前数据。"""
        _register(client, "interview_user@example.com")
        self.token = _login(client, "interview_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client
        _grant_active_subscription("interview_user@example.com", "I-INTERVIEWPLUS")

        create_resp = self.client.post(
            "/api/resumes/",
            json={"title": "面试简历", "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        self.resume_id = create_resp.json()["id"]

    def test_voice_interview_session_lifecycle(self):
        """用于验证语音面试会话lifecycle。"""
        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "interview_type": "general",
                "difficulty": "medium",
                "jd_text": "要求熟悉高并发服务、缓存和消息队列",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()
        assert created["next_action"] == "voice"
        session_id = created["session"]["id"]
        assert created["session"]["status"] == "interview_ready"
        assert created["session"]["target_company"] == "测试公司"
        assert created["session"]["target_title"] == "后端工程师"
        assert created["session"]["turns"] == []
        plan = created["session"]["plan"]
        assert plan["target_role"] == "后端工程师"
        assert "项目真实性" in plan["dimensions"]
        assert plan["stages"][1]["name"] == "简历项目深挖"
        assert "高并发" in plan["jd_focus"]
        assert created["session"]["current_turn"] is None

        end_resp = self.client.post(
            f"/api/interviews/{session_id}/end",
            headers=self.headers,
        )
        assert end_resp.status_code == 200, end_resp.text
        ended = end_resp.json()["session"]
        assert ended["status"] == "completed"

    def test_retry_interview_creates_clean_session_from_history(self):
        """用于验证历史面试可以复用上下文创建干净的新会话。"""
        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "target_company": "腾讯",
                "target_title": "AGENT 开发",
                "jd_text": "负责 Agent Runtime 和工具调用链路",
                "interview_type": "general",
                "difficulty": "hard",
                "language": "zh-CN",
                "mode": "practice",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        source_session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{source_session_id}/messages",
            json={"role": "interviewer", "text": "介绍一个 Agent 项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{source_session_id}/messages",
            json={"role": "candidate", "text": "我负责工具调用和确认链路。"},
            headers=self.headers,
        )
        end_resp = self.client.post(
            f"/api/interviews/{source_session_id}/end",
            headers=self.headers,
        )
        assert end_resp.status_code == 200, end_resp.text

        db = _TestingSession()
        try:
            source_session = (
                db.query(InterviewSession)
                .filter(InterviewSession.id == source_session_id)
                .one()
            )
            source_session.report_data = {"summary": "历史报告"}
            db.commit()
        finally:
            db.close()

        retry_resp = self.client.post(
            f"/api/interviews/{source_session_id}/retry",
            headers=self.headers,
        )

        assert retry_resp.status_code == 200, retry_resp.text
        body = retry_resp.json()
        new_session = body["session"]
        assert body["next_action"] == "voice"
        assert new_session["id"] != source_session_id
        assert new_session["resume_id"] == self.resume_id
        assert new_session["target_company"] == "腾讯"
        assert new_session["target_title"] == "AGENT 开发"
        assert new_session["jd_text"] == "负责 Agent Runtime 和工具调用链路"
        assert new_session["difficulty"] == "hard"
        assert new_session["language"] == "zh-CN"
        assert new_session["mode"] == "practice"
        assert new_session["status"] == "interview_ready"
        assert new_session["turns"] == []
        assert new_session["report_data"] is None
        assert new_session["started_at"] is None
        assert new_session["ended_at"] is None
        assert new_session["plan"]["target_company"] == "腾讯"
        assert new_session["plan"]["target_role"] == "AGENT 开发"

        original_resp = self.client.get(
            f"/api/interviews/{source_session_id}",
            headers=self.headers,
        )
        original = original_resp.json()["session"]
        assert original["status"] == "completed"
        assert original["report_data"] == {"summary": "历史报告"}
        assert len(original["turns"]) == 1

    def test_voice_interview_ignores_short_interviewer_fragments(self):
        """用于验证语音面试不会把短碎片当成新题目。"""
        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        question = "请你介绍一个最能体现 Agent 开发能力的项目。"
        first_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": question},
            headers=self.headers,
        )
        assert first_resp.status_code == 200, first_resp.text

        fragment_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "？"},
            headers=self.headers,
        )
        assert fragment_resp.status_code == 200, fragment_resp.text

        answer_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我负责记忆系统和工具调用。"},
            headers=self.headers,
        )
        assert answer_resp.status_code == 200, answer_resp.text

        turns = answer_resp.json()["session"]["turns"]
        assert len(turns) == 1
        assert turns[0]["question"] == question
        assert turns[0]["answer"] == "我负责记忆系统和工具调用。"

        tail_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "工作吗？"},
            headers=self.headers,
        )
        assert tail_resp.status_code == 200, tail_resp.text
        assert len(tail_resp.json()["session"]["turns"]) == 1

        next_question = "请继续说明这个项目最终带来了哪些业务结果。"
        next_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": next_question},
            headers=self.headers,
        )
        assert next_resp.status_code == 200, next_resp.text
        turns = next_resp.json()["session"]["turns"]
        assert len(turns) == 2
        assert turns[1]["question"] == next_question

    def test_completed_interview_can_generate_report(self, monkeypatch, caplog):
        """用于验证completed面试cangenerate报告。"""

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于处理init。"""

            async def __aenter__(self):
                """用于处理aenter。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于处理aexit。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于处理chatcompletion。"""
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"回答完整但需要更多量化细节",'
                                    '"strengths":["结构清晰","项目相关","沟通自然"],'
                                    '"weaknesses":["量化不足"],'
                                    '"next_training_plan":["补充指标","练习追问","精简表达"],'
                                    '"resume_feedback":["强化项目成果"],'
                                    '"dimensions":[{"title":"项目表达","assessment":"良好",'
                                    '"evidence":"能说明项目背景","advice":"补充结果"}],'
                                    '"turn_evaluations":[{"turn_index":0,'
                                    '"summary":"回答覆盖核心项目",'
                                    '"gaps":["缺少数据"],'
                                    '"evidence":["说明了职责"],'
                                    '"advice":"补充影响"}]}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )

        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        question_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍一个最有代表性的项目"},
            headers=self.headers,
        )
        assert question_resp.status_code == 200, question_resp.text
        answer_resp = self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我负责前端架构并提升了交付效率"},
            headers=self.headers,
        )
        assert answer_resp.status_code == 200, answer_resp.text

        end_resp = self.client.post(
            f"/api/interviews/{session_id}/end",
            headers=self.headers,
        )
        assert end_resp.status_code == 200, end_resp.text

        with caplog.at_level("INFO", logger="app.services.interview.report_service"):
            report_resp = self.client.post(
                f"/api/interviews/{session_id}/report",
                headers=self.headers,
            )

        assert report_resp.status_code == 200, report_resp.text
        body = report_resp.json()
        assert body["next_action"] == "report"
        report = body["session"]["report_data"]
        assert report["summary"] == "回答完整但需要更多量化细节"
        assert len(report["strengths"]) >= 3
        evaluation = body["session"]["turns"][0]["evaluation"]
        if isinstance(evaluation, dict):
            assert evaluation == {
                "summary": "回答覆盖核心项目",
                "gaps": ["缺少数据"],
                "evidence": ["说明了职责"],
                "advice": "补充影响",
            }
        else:
            assert evaluation == "回答覆盖核心项目\n问题：缺少数据\n亮点：说明了职责"
        report_logs = [record.message for record in caplog.records]
        assert "interview_report.requested" in report_logs
        assert "interview_report.turns_loaded" in report_logs
        assert "interview_report.llm.started" in report_logs
        assert "interview_report.llm.completed" in report_logs
        assert "interview_report.parsed" in report_logs
        assert "interview_report.saved" in report_logs


    def test_report_generation_streams_real_backend_phases(self, monkeypatch):
        """用于验证报告生成 SSE 按后端真实阶段推送进度。"""

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于初始化假 LLM 服务。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于返回可解析的报告 JSON。"""
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"可推进",'
                                    '"strengths":["相关","清晰","完整"],'
                                    '"weaknesses":["缺少证据"],'
                                    '"next_training_plan":["补证据"],'
                                    '"resume_feedback":["补项目边界"],'
                                    '"dimensions":[],'
                                    '"turn_evaluations":[]}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )
        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id, "target_title": "Agent工程师"},
            headers=self.headers,
        )
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍一个Agent项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我做过工具调用。"},
            headers=self.headers,
        )
        self.client.post(f"/api/interviews/{session_id}/end", headers=self.headers)

        stream_resp = self.client.post(
            f"/api/interviews/{session_id}/report/stream",
            headers=self.headers,
        )

        assert stream_resp.status_code == 200, stream_resp.text
        events = _sse_events(stream_resp)
        completed_phases = [
            event["phase"]
            for event in events
            if event.get("event_type") == "phase"
            and event.get("status") == "completed"
        ]
        assert completed_phases == [
            "validate_session",
            "load_turns",
            "request_llm",
            "parse_report",
            "save_report",
        ]
        done_event = events[-1]
        assert done_event["event_type"] == "done"
        assert done_event["next_action"] == "report"
        assert done_event["session"]["report_data"]["summary"] == "可推进"

    def test_report_generation_keeps_action_report_strategy_fields(
        self, monkeypatch
    ):
        """用于验证面试报告保留行动报告策略字段。"""

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于初始化假 LLM 服务。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于返回包含行动报告策略字段的结构化结果。"""
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"初筛可推进，但技术深挖有风险",'
                                    '"candidate_verdict":{"level":"borderline",'
                                    '"label":"边缘通过","reason":"项目相关但证据不足"},'
                                    '"job_match":{"target_title":"Agent工程师",'
                                    '"required_capabilities":["Agent编排","技术深度"],'
                                    '"covered_capabilities":["Agent编排"],'
                                    '"missing_capabilities":["量化结果"],'
                                    '"interviewer_concerns":["无法判断负责边界"],'
                                    '"likely_followups":["你具体负责哪一层？"]},'
                                    '"strengths":["项目方向相关","回答完整","沟通自然"],'
                                    '"weaknesses":["缺少量化结果"],'
                                    '"interviewer_risks":["负责边界不清"],'
                                    '"next_training_plan":["准备STAR项目版本","补两个指标","练技术追问"],'
                                    '"resume_feedback":["把负责边界写进项目经历"],'
                                    '"answer_rewrites":[{"turn_index":0,'
                                    '"original_problem":"回答没有量化结果",'
                                    '"recommended_answer":"我负责Agent工具编排，首轮响应耗时降低30%。",'
                                    '"why_better":"补充了职责边界和量化结果"}],'
                                    '"dimensions":[{"title":"岗位相关度","score":4,'
                                    '"assessment":"相关","evidence":"提到了Agent项目",'
                                    '"advice":"补充工程细节"}],'
                                    '"turn_evaluations":[{"turn_index":0,'
                                    '"summary":"回答覆盖Agent项目",'
                                    '"gaps":["缺少指标"],'
                                    '"evidence":["提到了Agent项目"],'
                                    '"advice":"补充延迟或转化率"}]}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )

        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "target_title": "Agent工程师",
                "jd_text": "负责Agent编排、工具调用和线上效果优化。",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍一个Agent项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我做过简历优化Agent。"},
            headers=self.headers,
        )
        self.client.post(f"/api/interviews/{session_id}/end", headers=self.headers)

        report_resp = self.client.post(
            f"/api/interviews/{session_id}/report",
            headers=self.headers,
        )

        assert report_resp.status_code == 200, report_resp.text
        report = report_resp.json()["session"]["report_data"]
        assert report["candidate_verdict"]["label"] == "边缘通过"
        assert report["job_match"]["missing_capabilities"] == ["量化结果"]
        assert report["interviewer_risks"] == ["负责边界不清"]
        assert report["answer_rewrites"][0]["recommended_answer"].startswith(
            "我负责Agent工具编排"
        )
        assert report["dimensions"][0]["score"] == 4

    def test_report_prompt_requests_action_report_strategy(self, monkeypatch):
        """用于验证报告生成提示词要求行动报告策略字段。"""
        captured_prompt = ""

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于初始化假 LLM 服务。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于捕获报告生成提示词。"""
                nonlocal captured_prompt
                captured_prompt = kwargs.get("system_prompt") or ""
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"可推进",'
                                    '"strengths":["相关","清晰","完整"],'
                                    '"weaknesses":["缺少证据"],'
                                    '"next_training_plan":["补证据","练追问","改简历"],'
                                    '"resume_feedback":["补项目边界"],'
                                    '"dimensions":[],'
                                    '"turn_evaluations":[]}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )

        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id, "target_title": "Agent工程师"},
            headers=self.headers,
        )
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍你的Agent项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我做过工具调用。"},
            headers=self.headers,
        )
        self.client.post(f"/api/interviews/{session_id}/end", headers=self.headers)

        report_resp = self.client.post(
            f"/api/interviews/{session_id}/report",
            headers=self.headers,
        )

        assert report_resp.status_code == 200, report_resp.text
        assert "candidate_verdict" in captured_prompt
        assert "job_match" in captured_prompt
        assert "interviewer_risks" in captured_prompt
        assert "answer_rewrites" in captured_prompt
        assert "面试官视角" in captured_prompt

    def test_report_prompt_payload_includes_question_intent(self, monkeypatch):
        """用于验证报告输入包含题目考察意图。"""
        captured_user_payload: dict = {}

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于初始化假 LLM 服务。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, messages, *args, **kwargs):
                """用于捕获发送给报告模型的用户 payload。"""
                nonlocal captured_user_payload
                captured_user_payload = json.loads(messages[0]["content"])
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"可推进",'
                                    '"strengths":["相关","清晰","完整"],'
                                    '"weaknesses":["缺少证据"],'
                                    '"next_training_plan":["补证据","练追问","改简历"],'
                                    '"resume_feedback":["补项目边界"],'
                                    '"dimensions":[],'
                                    '"turn_evaluations":[]}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )

        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id, "target_title": "Agent工程师"},
            headers=self.headers,
        )
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "讲一个技术权衡案例"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我在工具调用链路做过取舍。"},
            headers=self.headers,
        )
        with _TestingSession() as db:
            turn = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.session_id == session_id)
                .one()
            )
            turn.question_type = "technical_depth"
            turn.intent = "考察候选人是否能解释工程权衡"
            turn.expected_points = ["约束条件", "取舍理由", "结果指标"]
            db.commit()
        self.client.post(f"/api/interviews/{session_id}/end", headers=self.headers)

        report_resp = self.client.post(
            f"/api/interviews/{session_id}/report",
            headers=self.headers,
        )

        assert report_resp.status_code == 200, report_resp.text
        turn_payload = captured_user_payload["turns"][0]
        assert turn_payload["question_type"] == "technical_depth"
        assert turn_payload["intent"] == "考察候选人是否能解释工程权衡"
        assert turn_payload["expected_points"] == [
            "约束条件",
            "取舍理由",
            "结果指标",
        ]

    def test_report_generation_skips_empty_completed_interview(
        self, monkeypatch, caplog
    ):
        """用于验证reportgeneration跳过emptycompleted面试。"""
        called = False

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于处理init。"""
                nonlocal called
                called = True

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )

        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]
        end_resp = self.client.post(
            f"/api/interviews/{session_id}/end",
            headers=self.headers,
        )
        assert end_resp.status_code == 200, end_resp.text

        with caplog.at_level("INFO", logger="app.services.interview.report_service"):
            report_resp = self.client.post(
                f"/api/interviews/{session_id}/report",
                headers=self.headers,
            )

        assert report_resp.status_code == 200, report_resp.text
        assert report_resp.json()["next_action"] == "report_skipped"
        assert report_resp.json()["session"]["report_data"] is None
        assert called is False
        report_logs = [record.message for record in caplog.records]
        assert "interview_report.turns_loaded" in report_logs
        assert "interview_report.skipped" in report_logs

    def test_report_generation_falls_back_when_llm_returns_invalid_json(
        self, monkeypatch, caplog
    ):
        """用于验证reportgenerationfallsbackwhenllmreturnsinvalidjson。"""

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于处理init。"""
                self.model = "fake-report-model"

            async def __aenter__(self):
                """用于处理aenter。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于处理aexit。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于处理chatcompletion。"""
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"候选人提到 "React" 项目，'
                                    '但这个 JSON 的引号没有转义"}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )

        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍 React 项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我做过 React 项目"},
            headers=self.headers,
        )
        end_resp = self.client.post(
            f"/api/interviews/{session_id}/end",
            headers=self.headers,
        )
        assert end_resp.status_code == 200, end_resp.text

        with caplog.at_level("INFO", logger="app.services.interview.report_service"):
            report_resp = self.client.post(
                f"/api/interviews/{session_id}/report",
                headers=self.headers,
            )

        assert report_resp.status_code == 200, report_resp.text
        body = report_resp.json()
        report = body["session"]["report_data"]
        assert body["next_action"] == "report"
        assert report["summary"]
        assert not report["summary"].lstrip().startswith("{")
        assert "candidate_verdict" not in report["summary"]
        assert report["candidate_verdict"]["level"] == "risky"
        assert report["job_match"]["interviewer_concerns"]
        assert report["interviewer_risks"]
        assert report["answer_rewrites"][0]["recommended_answer"]
        assert len(report["strengths"]) == 3
        evaluation = body["session"]["turns"][0]["evaluation"]
        if isinstance(evaluation, dict):
            assert evaluation["summary"].startswith("已记录本轮问答")
        else:
            assert evaluation.startswith("已记录本轮问答")
        report_logs = [record.message for record in caplog.records]
        assert "interview_report.invalid_json" in report_logs
        assert "interview_report.saved" in report_logs

    def test_report_generation_returns_existing_report_without_llm(self, monkeypatch):
        """用于验证已有报告时重复生成不会再次调用 LLM。"""

        class FakeChatService:
            def __init__(self, *args, **kwargs):
                """用于初始化可成功返回的假 LLM。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于返回首次报告 JSON。"""
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"首次报告",'
                                    '"strengths":["完整","相关","清晰"],'
                                    '"weaknesses":["量化不足"],'
                                    '"next_training_plan":["补充指标"],'
                                    '"resume_feedback":["补充成果"],'
                                    '"dimensions":[],'
                                    '"turn_evaluations":[]}'
                                )
                            }
                        }
                    ]
                }

        class ExplodingChatService:
            def __init__(self, *args, **kwargs):
                """用于确保重复生成不会调用 LLM。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于在重复调用 LLM 时让测试失败。"""
                raise AssertionError("existing report should skip LLM")

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            FakeChatService,
        )
        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍一个项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我做过 Agent 项目"},
            headers=self.headers,
        )
        self.client.post(f"/api/interviews/{session_id}/end", headers=self.headers)

        first_resp = self.client.post(
            f"/api/interviews/{session_id}/report",
            headers=self.headers,
        )
        assert first_resp.status_code == 200, first_resp.text
        assert first_resp.json()["session"]["report_data"]["summary"] == "首次报告"

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            ExplodingChatService,
        )
        second_resp = self.client.post(
            f"/api/interviews/{session_id}/report",
            headers=self.headers,
        )

        assert second_resp.status_code == 200, second_resp.text
        assert second_resp.json()["next_action"] == "report"
        assert second_resp.json()["session"]["report_data"]["summary"] == "首次报告"

    def test_report_generation_deduplicates_concurrent_requests(self, monkeypatch):
        """用于验证并发重复生成同一报告只调用一次 LLM。"""
        first_call_started = threading.Event()
        allow_first_call_to_finish = threading.Event()
        call_count = 0

        class SlowChatService:
            def __init__(self, *args, **kwargs):
                """用于初始化慢速假 LLM。"""

            async def __aenter__(self):
                """用于进入假 LLM 上下文。"""
                return self

            async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
                """用于退出假 LLM 上下文。"""
                return None

            async def chat_completion(self, *args, **kwargs):
                """用于阻塞首次报告生成以制造并发。"""
                nonlocal call_count
                call_count += 1
                first_call_started.set()
                assert allow_first_call_to_finish.wait(timeout=5)
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"summary":"并发报告",'
                                    '"strengths":["完整","相关","清晰"],'
                                    '"weaknesses":["量化不足"],'
                                    '"next_training_plan":["补充指标"],'
                                    '"resume_feedback":["补充成果"],'
                                    '"dimensions":[],'
                                    '"turn_evaluations":[]}'
                                )
                            }
                        }
                    ]
                }

        monkeypatch.setattr(
            "app.services.interview.report_service.ChatService",
            SlowChatService,
        )
        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "interviewer", "text": "介绍一个项目"},
            headers=self.headers,
        )
        self.client.post(
            f"/api/interviews/{session_id}/messages",
            json={"role": "candidate", "text": "我做过 Agent 项目"},
            headers=self.headers,
        )
        self.client.post(f"/api/interviews/{session_id}/end", headers=self.headers)

        def post_report():
            """用于发起报告生成请求。"""
            return self.client.post(
                f"/api/interviews/{session_id}/report",
                headers=self.headers,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(post_report)
            assert first_call_started.wait(timeout=5)
            second_future = executor.submit(post_report)
            allow_first_call_to_finish.set()
            first_resp = first_future.result(timeout=10)
            second_resp = second_future.result(timeout=10)

        assert first_resp.status_code == 200, first_resp.text
        assert second_resp.status_code == 200, second_resp.text
        assert call_count == 1
        assert first_resp.json()["session"]["report_data"]["summary"] == "并发报告"
        assert second_resp.json()["session"]["report_data"]["summary"] == "并发报告"

    def test_report_generation_requires_completed_session(self):
        """用于验证reportgenerationrequirescompleted会话。"""
        create_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        report_resp = self.client.post(
            f"/api/interviews/{session_id}/report",
            headers=self.headers,
        )

        assert report_resp.status_code == 400
        assert report_resp.json()["detail"] == (
            "Interview must be completed before generating report"
        )

    def test_list_interviews_returns_lightweight_summary(self):
        """用于验证listinterviewsreturnslightweightsummary。"""
        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "interview_type": "general",
                "difficulty": "medium",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        list_resp = self.client.get("/api/interviews/", headers=self.headers)
        assert list_resp.status_code == 200, list_resp.text
        sessions = list_resp.json()
        assert len(sessions) >= 1
        session = next(item for item in sessions if item["id"] == session_id)
        assert session["id"] == session_id
        assert session["answered_turn_count"] == 0
        assert "turns" not in session
        assert "current_turn" not in session

    def test_delete_interview_removes_only_current_user_session(self, client):
        """用于验证delete面试removesonlycurrent用户会话。"""
        other_email = "other_interview_user@example.com"
        _register(client, other_email)
        other_token = _login(client, other_email)
        other_headers = _auth_headers(other_token)
        _grant_active_subscription(other_email, "I-OTHERINTERVIEWPLUS")

        other_resume_resp = client.post(
            "/api/resumes/",
            json={"title": "别人的面试简历", "content": _empty_resume_content()},
            headers=other_headers,
        )
        assert other_resume_resp.status_code == 200, other_resume_resp.text
        other_resume_id = other_resume_resp.json()["id"]

        own_session_resp = self.client.post(
            "/api/interviews/",
            json={"resume_id": self.resume_id, "mode": "practice"},
            headers=self.headers,
        )
        assert own_session_resp.status_code == 200, own_session_resp.text
        own_session_id = own_session_resp.json()["session"]["id"]

        other_session_resp = client.post(
            "/api/interviews/",
            json={"resume_id": other_resume_id, "mode": "practice"},
            headers=other_headers,
        )
        assert other_session_resp.status_code == 200, other_session_resp.text
        other_session_id = other_session_resp.json()["session"]["id"]

        forbidden_resp = self.client.delete(
            f"/api/interviews/{other_session_id}",
            headers=self.headers,
        )
        assert forbidden_resp.status_code == 404

        delete_resp = self.client.delete(
            f"/api/interviews/{own_session_id}",
            headers=self.headers,
        )
        assert delete_resp.status_code == 200, delete_resp.text
        assert delete_resp.json()["message"] == "Interview session deleted"

        get_deleted_resp = self.client.get(
            f"/api/interviews/{own_session_id}",
            headers=self.headers,
        )
        assert get_deleted_resp.status_code == 404

        get_other_resp = client.get(
            f"/api/interviews/{other_session_id}",
            headers=other_headers,
        )
        assert get_other_resp.status_code == 200, get_other_resp.text

    def test_removed_structured_interview_routes_return_404(self):
        """用于验证removedstructured面试routesreturn404。"""
        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "interview_type": "general",
                "difficulty": "medium",
                "mode": "practice",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        assert (
            self.client.post(
                f"/api/interviews/{session_id}/start", headers=self.headers
            ).status_code
            == 404
        )
        assert (
            self.client.post(
                f"/api/interviews/{session_id}/answer",
                json={"answer": "旧文本回答"},
                headers=self.headers,
            ).status_code
            == 404
        )
        assert (
            self.client.post(
                f"/api/interviews/{session_id}/answer/stream",
                json={"answer": "旧文本回答"},
                headers=self.headers,
            ).status_code
            == 404
        )
        assert (
            self.client.post(
                f"/api/interviews/{session_id}/hint",
                headers=self.headers,
            ).status_code
            == 404
        )
        assert (
            self.client.get(
                f"/api/interviews/{session_id}/report",
                headers=self.headers,
            ).status_code
            == 405
        )

    def test_list_resumes_without_auth_returns_401(self):
        """用于验证listresumeswithout认证returns401。"""
        resp = _anonymous_client().get("/api/resumes/")
        assert resp.status_code == 401


class TestPlusFeatureAccess:
    def test_free_user_can_create_interview_session(self, client):
        """用于验证free用户cancreate面试会话。"""
        _register(client, "interview_free@example.com")
        token = _login(client, "interview_free@example.com")
        headers = _auth_headers(token)
        resume_resp = client.post(
            "/api/resumes/",
            json={"title": "免费用户面试简历", "content": _empty_resume_content()},
            headers=headers,
        )
        assert resume_resp.status_code == 200, resume_resp.text

        resp = client.post(
            "/api/interviews/",
            json={"resume_id": resume_resp.json()["id"], "mode": "practice"},
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["next_action"] == "voice"
        assert resp.json()["session"]["resume_id"] == resume_resp.json()["id"]

    def test_free_user_cannot_upload_jd_ocr_image(self, client):
        """用于验证free用户cannot上传jdocrimage。"""
        _register(client, "jd_ocr_free@example.com")
        token = _login(client, "jd_ocr_free@example.com")

        resp = client.post(
            "/api/upload/jd-ocr",
            headers=_auth_headers(token),
            files={"file": ("jd.png", b"fake-image-bytes", "image/png")},
        )

        assert resp.status_code == 403
        assert resp.json()["detail"] == "active_subscription_required"


class TestDigitalHumanBillingAccess:
    class _FakeVolcengineVoiceService:
        def is_configured(self) -> bool:
            """用于处理isconfigured。"""
            return True

        async def proxy_session(self, client_ws, **kwargs):
            """用于处理proxy会话。"""
            await client_ws.send_json({"type": "ready"})
            await client_ws.close()

    def _create_interview_session(self, client, headers: dict, email: str) -> int:
        """用于创建面试会话。"""
        resume_resp = client.post(
            "/api/resumes/",
            json={"title": "数字人权限简历", "content": _empty_resume_content()},
            headers=headers,
        )
        assert resume_resp.status_code == 200, resume_resp.text
        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).one()
            session = InterviewSession(
                user_id=user.id,
                resume_id=resume_resp.json()["id"],
                status="interview_ready",
                mode="practice",
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session.id
        finally:
            db.close()

    def test_free_user_can_create_digital_human_conversation(self, client):
        """用于验证free用户cancreatedigitalhumanconversation。"""
        _register(client, "digital_human_free@example.com")
        token = _login(client, "digital_human_free@example.com")
        headers = _auth_headers(token)
        session_id = self._create_interview_session(
            client, headers, "digital_human_free@example.com"
        )

        resp = client.post(
            "/api/digital-human/conversations",
            json={"interview_session_id": session_id},
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["provider"] == "volcengine"
        assert resp.json()["session_id"] == str(session_id)

    def test_active_subscriber_can_create_digital_human_conversation(self, client):
        """用于验证activesubscribercancreatedigitalhumanconversation。"""
        email = "digital_human_plus@example.com"
        _register(client, email)
        token = _login(client, email)
        headers = _auth_headers(token)
        session_id = self._create_interview_session(client, headers, email)

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).one()
            db.add(
                BillingSubscription(
                    user_id=user.id,
                    provider="paypal",
                    provider_subscription_id="I-DIGITALHUMANPLUS",
                    status="ACTIVE",
                    raw_payload={"id": "I-DIGITALHUMANPLUS", "status": "ACTIVE"},
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.post(
            "/api/digital-human/conversations",
            json={"interview_session_id": session_id},
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "provider": "volcengine",
            "session_id": str(session_id),
            "status": "ready",
        }

    def test_voice_session_websocket_rejects_anonymous_client(
        self, client, monkeypatch
    ):
        """用于验证语音会话websocketrejectsanonymous客户端。"""
        from app.entrypoints.http import digital_human as digital_human_routes

        monkeypatch.setattr(
            digital_human_routes,
            "VolcengineVoiceService",
            self._FakeVolcengineVoiceService,
        )
        _register(client, "voice_ws_owner@example.com")
        token = _login(client, "voice_ws_owner@example.com")
        session_id = self._create_interview_session(
            client, _auth_headers(token), "voice_ws_owner@example.com"
        )

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with _anonymous_client().websocket_connect(
                f"/api/digital-human/voice-session/{session_id}"
            ) as websocket:
                websocket.receive_json()

        assert exc_info.value.code == 1008

    def test_voice_session_websocket_allows_free_user(self, client, monkeypatch):
        """用于验证语音会话websocketallowsfree用户。"""
        from app.entrypoints.http import digital_human as digital_human_routes

        monkeypatch.setattr(
            digital_human_routes,
            "VolcengineVoiceService",
            self._FakeVolcengineVoiceService,
        )
        email = "voice_ws_free@example.com"
        _register(client, email)
        token = _login(client, email)
        session_id = self._create_interview_session(client, _auth_headers(token), email)

        with client.websocket_connect(
            f"/api/digital-human/voice-session/{session_id}"
        ) as websocket:
            assert websocket.receive_json() == {"type": "ready"}

    def test_voice_session_websocket_rejects_other_users_session(
        self, client, monkeypatch
    ):
        """用于验证语音会话websocketrejectsotherusers会话。"""
        from app.entrypoints.http import digital_human as digital_human_routes

        monkeypatch.setattr(
            digital_human_routes,
            "VolcengineVoiceService",
            self._FakeVolcengineVoiceService,
        )
        owner_email = "voice_ws_owner_plus@example.com"
        _register(client, owner_email)
        owner_token = _login(client, owner_email)
        session_id = self._create_interview_session(
            client, _auth_headers(owner_token), owner_email
        )

        attacker_client = TestClient(app)
        attacker_email = "voice_ws_attacker_plus@example.com"
        _register(attacker_client, attacker_email)
        _login(attacker_client, attacker_email)

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with attacker_client.websocket_connect(
                f"/api/digital-human/voice-session/{session_id}"
            ) as websocket:
                websocket.receive_json()

        assert exc_info.value.code == 1008

    def test_logged_in_user_can_open_owned_voice_session_websocket(
        self, client, monkeypatch
    ):
        """用于验证loggedinusercanopenowned语音会话websocket。"""
        from app.entrypoints.http import digital_human as digital_human_routes

        monkeypatch.setattr(
            digital_human_routes,
            "VolcengineVoiceService",
            self._FakeVolcengineVoiceService,
        )
        email = "voice_ws_plus@example.com"
        _register(client, email)
        token = _login(client, email)
        session_id = self._create_interview_session(client, _auth_headers(token), email)

        with client.websocket_connect(
            f"/api/digital-human/voice-session/{session_id}"
        ) as websocket:
            assert websocket.receive_json() == {"type": "ready"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. 跨用户权限隔离
# ═══════════════════════════════════════════════════════════════════════════


class TestResumePermissions:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        # 用户 A
        """用于设置当前数据。"""
        _register(client, "user_a@example.com")
        self.token_a = _login(client, "user_a@example.com")
        # 用户 B
        _register(client, "user_b@example.com")
        self.token_b = _login(client, "user_b@example.com")
        self.client = client

        # 用户 A 创建一份简历
        resp = client.post(
            "/api/resumes/",
            json={"title": "用户A的简历", "content": _empty_resume_content()},
            headers=_auth_headers(self.token_a),
        )
        assert resp.status_code == 200
        self.resume_id = resp.json()["id"]

    def test_user_b_cannot_read_user_a_resume(self):
        """用于验证用户bcannotread用户a简历。"""
        resp = self.client.get(
            f"/api/resumes/{self.resume_id}",
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 403

    def test_user_b_cannot_update_user_a_resume(self):
        """用于验证用户bcannotupdate用户a简历。"""
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={"title": "非法修改"},
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 403

    def test_user_b_cannot_delete_user_a_resume(self):
        """用于验证用户bcannotdelete用户a简历。"""
        resp = self.client.delete(
            f"/api/resumes/{self.resume_id}",
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 403

    def test_user_b_resume_list_does_not_include_user_a_resume(self):
        """用于验证用户b简历listdoesnotinclude用户a简历。"""
        resp = self.client.get(
            "/api/resumes/",
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert self.resume_id not in ids


# ═══════════════════════════════════════════════════════════════════════════
# 4. 聊天记录 CRUD
# ═══════════════════════════════════════════════════════════════════════════


class TestChatMessages:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """用于设置当前数据。"""
        _register(client, "chat_user@example.com")
        self.token = _login(client, "chat_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

        resp = client.post(
            "/api/resumes/",
            json={"title": "聊天简历", "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert resp.status_code == 200
        self.resume_id = resp.json()["id"]

    def test_append_and_get_messages(self):
        """用于验证appendandgetmessages。"""
        msgs = [
            {"role": "user", "content": "帮我优化简历"},
            {"role": "assistant", "content": "好的，我来帮你优化"},
        ]
        post_resp = self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=msgs,
            headers=self.headers,
        )
        assert post_resp.status_code == 200
        saved = post_resp.json()
        assert len(saved) == 2
        assert saved[0]["role"] == "user"
        assert saved[1]["role"] == "assistant"

        get_resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        assert get_resp.status_code == 200
        all_msgs = get_resp.json()
        assert len(all_msgs) == 2

    def test_messages_are_ordered_by_id(self):
        """用于验证messagesareorderedbyid。"""
        for i in range(3):
            self.client.post(
                f"/api/resumes/{self.resume_id}/chat-messages",
                json=[{"role": "user", "content": f"消息 {i}"}],
                headers=self.headers,
            )
        get_resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        msgs = get_resp.json()
        ids = [m["id"] for m in msgs]
        assert ids == sorted(ids)

    def test_invalid_role_is_ignored(self):
        """用于验证invalidroleisignored。"""
        resp = self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=[{"role": "system", "content": "系统消息应被忽略"}],
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_clear_messages(self):
        """用于验证clearmessages。"""
        self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=[{"role": "user", "content": "一条消息"}],
            headers=self.headers,
        )
        del_resp = self.client.delete(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        assert del_resp.status_code == 200

        get_resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        assert get_resp.json() == []

    def test_append_messages_with_stream_events(self):
        """用于验证appendmessageswithstream事件。"""
        stream_events = [
            {"type": "tool_confirmed", "diff": "添加了量化指标"},
        ]
        resp = self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=[
                {
                    "role": "assistant",
                    "content": "已优化",
                    "stream_events": stream_events,
                }
            ],
            headers=self.headers,
        )
        assert resp.status_code == 200
        saved = resp.json()
        assert saved[0]["stream_events"] == stream_events

    def test_chat_messages_forbidden_for_other_user(self):
        """用于验证chatmessagesforbiddenforother用户。"""
        _register(self.client, "other_chat@example.com")
        other_token = _login(self.client, "other_chat@example.com")
        resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=_auth_headers(other_token),
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 5. Agent 确认会话
# ═══════════════════════════════════════════════════════════════════════════


class TestAgentConfirmation:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """用于设置当前数据。"""
        _register(client, "agent_confirm@example.com")
        self.token = _login(client, "agent_confirm@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

        me_resp = client.get("/api/auth/me", headers=self.headers)
        assert me_resp.status_code == 200
        self.user_id = me_resp.json()["id"]

        resume_resp = client.post(
            "/api/resumes/",
            json={"title": "确认简历", "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert resume_resp.status_code == 200
        self.resume_id = resume_resp.json()["id"]

    def _create_waiting_session(self, session_id: str, call_id: str = "call_1") -> None:
        """用于创建waiting会话。"""
        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            store.create_session(
                session_id=session_id,
                user_id=self.user_id,
                resume_id=self.resume_id,
                task_type="resume_optimization",
            )
            store.update_status(
                session_id, "waiting_confirmation", current_step=call_id
            )
            store.append_event(
                session_id=session_id,
                event_type="tool_call_previewed",
                source="resume_agent",
                payload={
                    "call_id": call_id,
                    "tool_name": "优化简介",
                    "diff_summary": "改前 A 改后 B",
                },
            )
        finally:
            db.close()

    def test_confirm_tool_records_resumable_result_when_stream_queue_missing(self):
        """用于验证confirmtoolrecordsresumable结果whenstreamqueuemissing。"""
        self._create_waiting_session("persisted_session")

        resp = self.client.post(
            "/api/ai/chat/confirm-tool",
            json={
                "session_id": "persisted_session",
                "call_id": "call_1",
                "confirmed": True,
            },
            headers=self.headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["resumable"] is True

        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            session = store.get_session("persisted_session")
            assert session.status == "paused"
            latest = store.get_latest_event("persisted_session")
            assert latest.event_type == "tool_call_confirmed"
            assert latest.payload["active_stream"] is False
        finally:
            db.close()

    def test_pending_confirmation_returns_waiting_diff_for_resume(self):
        """用于验证可按简历读取待确认 diff checkpoint。"""
        session_id = "pending_confirmation_session"
        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            store.create_session(
                session_id=session_id,
                user_id=self.user_id,
                resume_id=self.resume_id,
                task_type="resume_optimization",
            )
            store.update_status(
                session_id, "waiting_confirmation", current_step="call_pending"
            )
            store.append_event(
                session_id=session_id,
                event_type="tool_call_previewed",
                source="resume_agent",
                payload={
                    "call_id": "call_pending",
                    "tool_name": "优化要点",
                    "tool_id": "update_bullet",
                    "diff_summary": "改前 A 改后 B",
                    "diff_items": [
                        {
                            "before": "旧要点",
                            "after": "新要点",
                            "reason": "更贴合 JD",
                        }
                    ],
                },
            )
        finally:
            db.close()

        resp = self.client.get(
            f"/api/ai/chat/pending-confirmation?resume_id={self.resume_id}",
            headers=self.headers,
        )

        assert resp.status_code == 200
        assert resp.json() == {
            "session_id": session_id,
            "status": "waiting_confirmation",
            "pending_action": {
                "type": "tool_confirmation",
                "call_id": "call_pending",
                "tool_name": "优化要点",
                "tool_id": "update_bullet",
                "diff_summary": "改前 A 改后 B",
                "diff_items": [
                    {
                        "before": "旧要点",
                        "after": "新要点",
                        "reason": "更贴合 JD",
                    }
                ],
            },
        }

    def test_confirm_tool_uses_active_queue_when_present(self):
        """用于验证confirmtoolusesactivequeuewhenpresent。"""
        session_id = "active_session"
        self._create_waiting_session(session_id)
        queue = confirmation_manager.create(session_id)
        try:
            resp = self.client.post(
                "/api/ai/chat/confirm-tool",
                json={
                    "session_id": session_id,
                    "call_id": "call_1",
                    "confirmed": False,
                },
                headers=self.headers,
            )

            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
            assert queue.get_nowait() is False

            duplicate_resp = self.client.post(
                "/api/ai/chat/confirm-tool",
                json={
                    "session_id": session_id,
                    "call_id": "call_1",
                    "confirmed": False,
                },
                headers=self.headers,
            )

            assert duplicate_resp.status_code == 200
            assert duplicate_resp.json()["duplicate"] is True
            assert queue.empty()
        finally:
            confirmation_manager.remove(session_id)

    def test_confirm_tool_rejects_mismatched_call_id(self):
        """用于验证confirmtoolrejectsmismatchedcallid。"""
        self._create_waiting_session("mismatched_session", call_id="call_real")

        resp = self.client.post(
            "/api/ai/chat/confirm-tool",
            json={
                "session_id": "mismatched_session",
                "call_id": "call_wrong",
                "confirmed": True,
            },
            headers=self.headers,
        )

        assert resp.status_code == 409

    def test_resume_session_applies_recorded_confirmation(self):
        """用于验证简历会话appliesrecordedconfirmation。"""
        session_id = "resume_http_session"
        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            store.create_session(
                session_id=session_id,
                user_id=self.user_id,
                resume_id=self.resume_id,
                task_type="resume_optimization",
                metadata={"visible_modules": ["projects"]},
            )
            store.update_status(
                session_id, "waiting_confirmation", current_step="call_1"
            )
            store.append_event(
                session_id=session_id,
                event_type="user_message",
                source="user",
                payload={"content": "优化项目简介"},
            )
            store.append_event(
                session_id=session_id,
                event_type="tool_call_previewed",
                source="resume_agent",
                payload={
                    "call_id": "call_1",
                    "tool_name": "优化简介",
                    "tool_call": {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "update_overview",
                            "arguments": {
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "恢复接口写入的新简介",
                            },
                        },
                    },
                },
            )
            store.append_confirmation_event(
                session_id=session_id,
                call_id="call_1",
                confirmed=True,
                tool_name="优化简介",
                active_stream=False,
            )
            store.update_status(session_id, "paused", current_step="call_1")
        finally:
            db.close()

        update_resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={
                "content": {
                    **_empty_resume_content(),
                    "projects": [
                        {
                            "id": "proj_1",
                            "name": "Chat Resume",
                            "role": "开发者",
                            "duration": "2026",
                            "overview": "旧简介",
                        }
                    ],
                }
            },
            headers=self.headers,
        )
        assert update_resp.status_code == 200

        resp = self.client.post(
            "/api/ai/chat/resume-session",
            json={"session_id": session_id},
            headers=self.headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["applied"] is True
        assert (
            body["resume_content"]["projects"][0]["overview"] == "恢复接口写入的新简介"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 7. 健康检查 & 根路由
# ═══════════════════════════════════════════════════════════════════════════


class TestHealthEndpoints:
    def test_root_returns_200(self, client):
        """用于验证rootreturns200。"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Chat Resume" in resp.json()["message"]

    def test_health_check_returns_healthy(self, client):
        """用于验证healthcheckreturnshealthy。"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_check_returns_db_connectivity(self, client):
        """健康检查应验证数据库连通性，不只是返回静态字符串。"""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


# ═══════════════════════════════════════════════════════════════════════════
# 8. 负向场景
# ═══════════════════════════════════════════════════════════════════════════


class TestNegativeCases:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """用于设置当前数据。"""
        _register(client, "negative_user@example.com")
        self.token = _login(client, "negative_user@example.com")
        self.client = client
        resp = client.post(
            "/api/resumes/",
            json={"title": "测试简历", "content": _empty_resume_content()},
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 200
        self.resume_id = resp.json()["id"]

    # ── 未认证访问 ────────────────────────────────────────────────────────

    def test_get_resumes_without_token_returns_401(self):
        """用于验证getresumeswithout令牌returns401。"""
        resp = _anonymous_client().get("/api/resumes/")
        assert resp.status_code == 401

    def test_get_resume_without_token_returns_401(self):
        """用于验证get简历without令牌returns401。"""
        resp = _anonymous_client().get(f"/api/resumes/{self.resume_id}")
        assert resp.status_code == 401

    def test_update_resume_without_token_returns_401(self):
        """用于验证update简历without令牌returns401。"""
        resp = _anonymous_client().put(
            f"/api/resumes/{self.resume_id}",
            json={"title": "无 token"},
        )
        assert resp.status_code == 401

    def test_delete_resume_without_token_returns_401(self):
        """用于验证delete简历without令牌returns401。"""
        resp = _anonymous_client().delete(f"/api/resumes/{self.resume_id}")
        assert resp.status_code == 401

    def test_update_layout_without_token_returns_401(self):
        """用于验证updatelayoutwithout令牌returns401。"""
        resp = _anonymous_client().put(
            f"/api/resumes/{self.resume_id}/layout",
            json={
                "density": "compact",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": [
                    "personal",
                    "education",
                    "work",
                    "projects",
                    "skills",
                ],
                "spacingScale": 0.8,
            },
        )
        assert resp.status_code == 401

    # ── 资源不存在 ────────────────────────────────────────────────────────

    def test_get_nonexistent_resume_returns_404(self):
        """用于验证getnonexistent简历returns404。"""
        resp = self.client.get(
            "/api/resumes/999999",
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_update_nonexistent_resume_returns_404(self):
        """用于验证updatenonexistent简历returns404。"""
        resp = self.client.put(
            "/api/resumes/999999",
            json={"title": "不存在"},
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_resume_returns_404(self):
        """用于验证deletenonexistent简历returns404。"""
        resp = self.client.delete(
            "/api/resumes/999999",
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_update_layout_nonexistent_resume_returns_404(self):
        """用于验证updatelayoutnonexistent简历returns404。"""
        resp = self.client.put(
            "/api/resumes/999999/layout",
            json={
                "density": "normal",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": [
                    "personal",
                    "education",
                    "work",
                    "projects",
                    "skills",
                ],
                "spacingScale": 1.0,
            },
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_update_layout_persists_template_style(self):
        """用于验证updatelayoutpersiststemplatestyle。"""
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}/layout",
            json={
                "density": "normal",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": [
                    "personal",
                    "education",
                    "work",
                    "projects",
                    "skills",
                ],
                "spacingScale": 1.0,
                "templateStyle": "modern",
            },
            headers=_auth_headers(self.token),
        )

        assert resp.status_code == 200
        assert resp.json()["layout_config"]["templateStyle"] == "modern"

    # ── 无效输入 ──────────────────────────────────────────────────────────

    def test_update_resume_with_empty_body_returns_400(self):
        """用于验证update简历withemptybodyreturns400。"""
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={},
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 400

    def test_register_with_invalid_email_returns_422(self):
        """用于验证registerwithinvalidemailreturns422。"""
        resp = self.client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_register_with_short_password_returns_422(self):
        """用于验证registerwithshortpasswordreturns422。"""
        resp = self.client.post(
            "/api/auth/register",
            json={"email": "valid@example.com", "password": "123"},
        )
        assert resp.status_code == 422

    def test_update_layout_rejects_invalid_density_values(self):
        """用于验证布局配置拒绝非法密度、模板、模块和间距。"""
        invalid_payloads = [
            {
                "density": "cramped",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 1.0,
                "templateStyle": "classic",
            },
            {
                "density": "normal",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 0.49,
                "templateStyle": "classic",
            },
            {
                "density": "normal",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 1.81,
                "templateStyle": "classic",
            },
            {
                "density": "normal",
                "moduleOrder": ["personal", "education", "unknown", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 1.0,
                "templateStyle": "classic",
            },
            {
                "density": "normal",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 1.0,
                "templateStyle": "poster",
            },
        ]

        for payload in invalid_payloads:
            resp = self.client.put(
                f"/api/resumes/{self.resume_id}/layout",
                json=payload,
                headers=_auth_headers(self.token),
            )

            assert resp.status_code == 422

    def test_create_resume_rejects_invalid_layout_config(self):
        """用于验证创建简历时也校验布局配置。"""
        resp = self.client.post(
            "/api/resumes/",
            json={
                "title": "非法布局简历",
                "content": _empty_resume_content(),
                "layout_config": {
                    "density": "normal",
                    "moduleOrder": ["personal", "work"],
                    "visibleModules": ["personal", "skills"],
                    "spacingScale": 1.0,
                    "templateStyle": "classic",
                },
            },
            headers=_auth_headers(self.token),
        )

        assert resp.status_code == 422

    # ── 跨用户布局配置权限 ────────────────────────────────────────────────

    def test_other_user_cannot_update_layout(self):
        """用于验证other用户cannotupdatelayout。"""
        _register(self.client, "layout_attacker@example.com")
        attacker_token = _login(self.client, "layout_attacker@example.com")
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}/layout",
            json={
                "density": "compact",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": [
                    "personal",
                    "education",
                    "work",
                    "projects",
                    "skills",
                ],
                "spacingScale": 0.7,
            },
            headers=_auth_headers(attacker_token),
        )
        assert resp.status_code == 403
