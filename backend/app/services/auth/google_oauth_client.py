"""用于提供google oauth client模块能力。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str

    @classmethod
    def from_settings(cls, settings: object) -> GoogleOAuthConfig:
        """用于从应用配置创建服务实例。"""
        required = {
            "GOOGLE_OAUTH_CLIENT_ID": str(
                getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
            ).strip(),
            "GOOGLE_OAUTH_CLIENT_SECRET": str(
                getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
            ).strip(),
            "GOOGLE_OAUTH_REDIRECT_URI": str(
                getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "")
            ).strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise GoogleOAuthConfigurationError(missing)
        return cls(
            client_id=required["GOOGLE_OAUTH_CLIENT_ID"],
            client_secret=required["GOOGLE_OAUTH_CLIENT_SECRET"],
            redirect_uri=required["GOOGLE_OAUTH_REDIRECT_URI"],
        )


@dataclass(frozen=True)
class GoogleOAuthTokens:
    access_token: str
    token_type: str
    expires_in: int | None = None
    id_token: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None = None
    picture: str | None = None

    @property
    def can_use_for_login(self) -> bool:
        """用于判断当前 OAuth 配置是否可用于登录。"""
        return self.email_verified


class GoogleOAuthAuthenticationError(Exception):
    def __init__(self, error_code: str):
        """用于初始化当前对象。"""
        self.error_code = error_code
        super().__init__(error_code)


class GoogleOAuthConfigurationError(Exception):
    error_code = "config_missing"

    def __init__(self, missing_names: list[str]):
        """用于初始化当前对象。"""
        self.missing_names = missing_names
        joined_names = ", ".join(missing_names)
        super().__init__(f"Missing Google OAuth configuration: {joined_names}")


class GoogleOAuthClient:
    authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    userinfo_endpoint = "https://openidconnect.googleapis.com/v1/userinfo"
    scope = "openid email profile"

    def __init__(
        self,
        config: GoogleOAuthConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ):
        """用于初始化当前对象。"""
        self.config = config
        self.http_client = http_client or httpx.AsyncClient(timeout=10.0)

    def authorization_url(self, *, state: str) -> str:
        """用于处理授权地址。"""
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.scope,
            "state": state,
        }
        return f"{self.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> GoogleOAuthTokens:
        """用于处理exchange授权码。"""
        try:
            response = await self.http_client.post(
                self.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "redirect_uri": self.config.redirect_uri,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "google oauth token exchange failed: %s",
                exc.__class__.__name__,
            )
            raise GoogleOAuthAuthenticationError("google_exchange_failed") from exc
        payload = response.json()
        access_token = self._required_string(payload, "access_token")
        token_type = self._required_string(payload, "token_type")
        return GoogleOAuthTokens(
            access_token=access_token,
            token_type=token_type,
            expires_in=payload.get("expires_in"),
            id_token=payload.get("id_token"),
            scope=payload.get("scope"),
        )

    async def fetch_identity(self, access_token: str) -> GoogleIdentity:
        """用于获取身份。"""
        try:
            response = await self.http_client.get(
                self.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "google oauth userinfo fetch failed: %s",
                exc.__class__.__name__,
            )
            raise GoogleOAuthAuthenticationError("google_exchange_failed") from exc
        payload = response.json()
        sub = self._required_string(payload, "sub")
        email = self._required_string(payload, "email")
        return GoogleIdentity(
            sub=sub,
            email=email,
            email_verified=bool(payload.get("email_verified")),
            name=payload.get("name"),
            picture=payload.get("picture"),
        )

    def _required_string(self, payload: dict[str, object], field: str) -> str:
        """用于处理必填字符串。"""
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise GoogleOAuthAuthenticationError("google_exchange_failed")
        return value
