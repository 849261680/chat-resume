"""
主应用入口模块

FastAPI应用的初始化和配置入口点。
负责路由注册、中间件配置、错误处理和启动逻辑。
"""

import asyncio
import importlib
import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4


_BRAINTRUST_PROJECT_NAME = "chat-resume"


def _braintrust_api_key() -> str | None:
    """用于从进程环境或本地 .env 读取 Braintrust API key。"""
    api_key = os.getenv("BRAINTRUST_API_KEY")
    if api_key:
        return api_key

    env_path = Path(".env")
    if not env_path.is_file():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if key.strip() == "BRAINTRUST_API_KEY" and separator:
            return value.strip().strip("'\"") or None
    return None


def _configure_braintrust() -> None:
    """用于在配置了 API key 时启用 Braintrust 自动追踪。"""
    api_key = _braintrust_api_key()
    if not api_key:
        return

    try:
        braintrust = importlib.import_module("braintrust")
        braintrust.auto_instrument()
        braintrust.init_logger(api_key=api_key, project=_BRAINTRUST_PROJECT_NAME)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Braintrust instrumentation disabled: %s",
            type(exc).__name__,
        )


_configure_braintrust()

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import authenticate_token_with_db
from app.entrypoints.http.router import api_router
from app.infra.config import settings
from app.infra.database import SessionLocal, get_db
from app.infra.db_request_logging import (
    get_request_metrics,
    reset_request_metrics,
    start_request_metrics,
)
from app.infra.logging_setup import configure_logging
from app.infra.request_context import bind_log_context, reset_log_context

configure_logging()
logger = logging.getLogger(__name__)


def _truncate_log_value(value: str | None, limit: int = 240) -> str:
    """用于压缩日志里的长文本字段，避免单条日志过大。"""
    if not value:
        return "-"
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_STR}/openapi.json",
)

_PROTECTED_API_PREFIXES = (
    f"{settings.API_STR}/resumes",
    f"{settings.API_STR}/interviews",
    f"{settings.API_STR}/upload",
    f"{settings.API_STR}/ai",
    f"{settings.API_STR}/users",
    f"{settings.API_STR}/digital-human",
    f"{settings.API_STR}/billing",
)
_AUTH_EXEMPT_PATHS = {
    f"{settings.API_STR}/resumes/download",
    f"{settings.API_STR}/billing/paypal/webhook",
}
_SLOW_REQUEST_LOG_MS = 1000.0
_SENSITIVE_PARAM_NAMES = re.compile(
    r"(authorization|access[_-]?key|api[_-]?key|token|secret|password|cookie)",
    re.IGNORECASE,
)


@contextmanager
def _auth_db_session() -> Iterator[Session]:
    """用于让认证中间件复用 FastAPI 依赖覆盖里的数据库会话。"""
    db_provider = app.dependency_overrides.get(get_db, get_db)
    db_generator = db_provider()
    db = next(db_generator)
    try:
        yield db
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


def _route_template(request: Request) -> str:
    """用于把请求路径压缩成低基数的路由模板。"""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else request.url.path


def _safe_query_params(request: Request) -> dict[str, str | list[str]]:
    """用于记录查询参数，同时遮蔽敏感参数值。"""
    params: dict[str, str | list[str]] = {}
    for key, value in sorted(request.query_params.multi_items()):
        safe_value = _safe_param_value(key, value)
        existing = params.get(key)
        if existing is None:
            params[key] = safe_value
        elif isinstance(existing, list):
            existing.append(safe_value)
        else:
            params[key] = [existing, safe_value]
    return params


def _safe_param_value(key: str, value: str) -> str:
    """用于在日志参数里保留定位信息并隐藏敏感值。"""
    if _SENSITIVE_PARAM_NAMES.search(key):
        return "[REDACTED]"
    return _truncate_log_value(value, limit=160)


def _client_request_id(request: Request) -> str | None:
    """用于读取前端生成的请求关联 ID。"""
    value = request.headers.get("X-Client-Request-ID")
    if not value:
        return None
    return _truncate_log_value(value, limit=80)


def _request_user_id(request: Request) -> str:
    """用于从请求状态中提取当前用户 ID，没有登录则返回占位符。"""
    current_user = getattr(request.state, "current_user", None)
    user_id = getattr(current_user, "id", None)
    return str(user_id) if user_id is not None else "-"


def _release_identifier() -> str:
    """用于返回能关联到部署版本的日志标识。"""
    return settings.RELEASE_IDENTIFIER or os.getenv("RAILWAY_GIT_COMMIT_SHA", "") or "-"


def _failure_log_context(
    request: Request,
    *,
    request_id: str,
    status_code: int,
    exc: Exception,
) -> dict[str, object]:
    """用于生成未处理异常日志所需的定位上下文。"""
    return {
        "request_id": request_id,
        "client_request_id": getattr(request.state, "client_request_id", None) or "-",
        "http_method": request.method,
        "http_path": request.url.path,
        "http_route": _route_template(request),
        "http_status": status_code,
        "query_params": _safe_query_params(request),
        "user_id": _request_user_id(request),
        "release": _release_identifier(),
        "error_type": type(exc).__name__,
    }


def _is_protected_api_path(path: str) -> bool:
    """用于判断请求路径是否属于必须先鉴权的敏感 API。"""
    if path in _AUTH_EXEMPT_PATHS:
        return False
    if any(path.startswith(f"{exempt}/") for exempt in _AUTH_EXEMPT_PATHS):
        return False
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in _PROTECTED_API_PREFIXES
    )


def _extract_request_token(request: Request) -> str:
    """用于从请求头或 Cookie 中提取访问令牌。"""
    authorization = request.headers.get("Authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    cookie_token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    raise HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.middleware("http")
async def authenticate_protected_api_requests(request: Request, call_next):
    """用于在进入敏感 API 前统一完成服务端身份鉴权。"""
    path = request.url.path
    if request.method == "OPTIONS" or not _is_protected_api_path(path):
        return await call_next(request)

    try:
        token = _extract_request_token(request)
        with _auth_db_session() as db:
            claims, current_user = authenticate_token_with_db(token, db)
        request.state.current_user_claims = claims
        request.state.current_user = current_user
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    return await call_next(request)


# 添加中间件来记录请求
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """用于记录请求日志和慢数据库访问上下文。"""
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    client_request_id = _client_request_id(request)
    request.state.request_id = request_id
    request.state.client_request_id = client_request_id
    context_tokens = bind_log_context(
        request_id=request_id,
        client_request_id=client_request_id,
    )
    request_started_at = perf_counter()
    metrics_token = start_request_metrics()
    response = None
    try:
        try:
            response = await call_next(request)
        except Exception as exc:
            failure_context = _failure_log_context(
                request,
                request_id=request_id,
                status_code=500,
                exc=exc,
            )
            logger.exception("request.failed", extra=failure_context)
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
            )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_elapsed_ms = (perf_counter() - request_started_at) * 1000
        metrics = get_request_metrics()
        status_code = response.status_code if response is not None else 500
        should_log_request = (
            status_code >= 400 or request_elapsed_ms >= _SLOW_REQUEST_LOG_MS
        )
        if should_log_request and metrics is None:
            logger.info(
                "request.finished",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "request_ms": round(request_elapsed_ms, 2),
                    "client_request_id": client_request_id or "-",
                },
            )
        elif should_log_request and metrics is not None:
            logger.info(
                "request.finished",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "request_ms": round(request_elapsed_ms, 2),
                    "client_request_id": client_request_id or "-",
                    "db_checkout_count": metrics.checkout_count,
                    "db_checkout_ms": round(metrics.checkout_ms_total, 2),
                    "db_query_count": metrics.query_count,
                    "db_query_ms": round(metrics.query_ms_total, 2),
                    "db_longest_query_ms": round(metrics.longest_query_ms, 2),
                    "db_longest_query_sql": _truncate_log_value(
                        metrics.longest_query_statement
                    ),
                },
            )
        reset_request_metrics(metrics_token)
        reset_log_context(context_tokens)


# 数据库迁移由 Railway 的 startCommand 处理
logger.debug("app.starting")

# 从环境变量获取CORS配置
cors_origins = settings.BACKEND_CORS_ORIGINS
logger.debug("cors.config.loaded", extra={"cors_origin_count": len(cors_origins)})

# Cookie 鉴权要求显式 origin，避免浏览器在跨域时丢掉凭证。
configured_origins = [
    origin
    for origin in cors_origins
    if origin and origin != "http://localhost:3000,https://localhost:3000"
]
dev_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
]
origin_candidates = configured_origins or [settings.FRONTEND_URL, *dev_origins]
if settings.APP_ENV.strip().lower() == "development":
    origin_candidates = [*origin_candidates, settings.FRONTEND_URL, *dev_origins]
effective_origins = list(
    dict.fromkeys(origin for origin in origin_candidates if origin)
)
logger.debug(
    "cors.config.effective",
    extra={"cors_origin_count": len(effective_origins)},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=effective_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

app.include_router(api_router, prefix=settings.API_STR)


@app.get("/")
async def root():
    """用于返回 API 根路径响应。"""
    return {"message": "Chat Resume API"}


@app.get("/health")
async def health_check(response: Response):
    """用于返回服务健康检查结果。"""
    from app.infra.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        response.status_code = 503
        return {"status": "unhealthy", "detail": "database unavailable"}
    finally:
        db.close()


@app.get("/api/test")
async def test_endpoint():
    """用于返回测试接口响应。"""
    return {"message": "API is working", "cors": "enabled"}


_sweeper_task: asyncio.Task | None = None
_SWEEPER_INTERVAL_SECONDS = 60


async def _sweeper_loop(timeout_seconds: int) -> None:
    """用于定期扫描超时 paused session 的后台循环。"""
    from app.runtime.session_sweeper import sweep_timed_out_sessions

    while True:
        await asyncio.sleep(_SWEEPER_INTERVAL_SECONDS)
        try:
            count = await sweep_timed_out_sessions(SessionLocal, timeout_seconds)
            if count:
                logger.info("session_sweeper.periodic", extra={"cleaned": count})
        except Exception:
            logger.exception("session_sweeper.periodic.error")


@app.on_event("startup")
async def log_application_ready():
    """用于处理日志应用就绪状态。"""
    logger.info("app.ready")


@app.on_event("startup")
async def startup_session_sweeper():
    """用于启动时清理残留 paused session 并启动后台定时扫描任务。"""
    global _sweeper_task
    from app.runtime.session_sweeper import sweep_timed_out_sessions

    timeout = settings.AGENT_SESSION_CONFIRMATION_TIMEOUT_SECONDS
    try:
        count = await sweep_timed_out_sessions(SessionLocal, timeout)
        if count:
            logger.info("session_sweeper.startup", extra={"cleaned": count})
    except Exception:
        logger.exception("session_sweeper.startup.error")

    _sweeper_task = asyncio.create_task(_sweeper_loop(timeout))


@app.on_event("shutdown")
async def shutdown_session_sweeper():
    """用于关闭时取消后台扫描任务。"""
    global _sweeper_task
    if _sweeper_task is not None:
        _sweeper_task.cancel()


# 移除手动OPTIONS处理，让CORS中间件自动处理
