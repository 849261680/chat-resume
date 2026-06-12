"""
应用配置管理模块

负责加载和管理所有应用配置，包括数据库连接、JWT密钥、API密钥等。
使用Pydantic BaseSettings进行配置验证和环境变量读取。
"""

import os
from typing import List, Literal, Union, cast

from pydantic import field_validator
from pydantic_settings import BaseSettings

DEFAULT_SECRET_KEY = "your-secret-key-here"
_LOCAL_APP_ENVS = {"development", "dev", "local", "test", "testing"}


class Settings(BaseSettings):
    """用于集中管理运行环境里的所有配置项。"""

    PROJECT_NAME: str = "Chat Resume API"
    VERSION: str = "1.0.0"
    API_STR: str = "/api"
    APP_ENV: str = os.getenv(
        "APP_ENV",
        os.getenv("NODE_ENV", os.getenv("RAILWAY_ENVIRONMENT_NAME", "development")),
    )

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT",
        "text" if APP_ENV.strip().lower() == "development" else "json",
    )
    BACKEND_LOG_FILE: str = os.getenv("BACKEND_LOG_FILE", "logs/backend.log")
    AGENT_TRACE_LOG_ENABLED: bool = (
        os.getenv("AGENT_TRACE_LOG_ENABLED", "false").strip().lower() == "true"
    )
    AGENT_TRACE_CHUNK_LOG_ENABLED: bool = (
        os.getenv("AGENT_TRACE_CHUNK_LOG_ENABLED", "false").strip().lower() == "true"
    )

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chat_resume.db")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_SESSION_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_SESSION_EXPIRE_DAYS", "30")
    )
    ACCESS_TOKEN_COOKIE_NAME: str = os.getenv(
        "ACCESS_TOKEN_COOKIE_NAME", "access_token"
    )
    REFRESH_TOKEN_COOKIE_NAME: str = os.getenv(
        "REFRESH_TOKEN_COOKIE_NAME", "refresh_token"
    )
    AUTH_COOKIE_DOMAIN: str = os.getenv("AUTH_COOKIE_DOMAIN", "")
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = cast(
        Literal["lax", "strict", "none"],
        os.getenv("AUTH_COOKIE_SAMESITE", "lax"),
    )
    AUTH_COOKIE_SECURE: bool = (
        os.getenv("AUTH_COOKIE_SECURE", "").strip().lower() == "true"
        if os.getenv("AUTH_COOKIE_SECURE") is not None
        else os.getenv("APP_ENV", "development").strip().lower() != "development"
    )
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REDIRECT_URI: str = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")

    # PayPal Billing
    PAYPAL_CLIENT_ID: str = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_PLAN_ID: str = os.getenv("PAYPAL_PLAN_ID", "")
    PAYPAL_WEBHOOK_ID: str = os.getenv("PAYPAL_WEBHOOK_ID", "")
    PAYPAL_API_BASE: str = os.getenv(
        "PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com"
    )

    # CORS
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = (
        "http://localhost:3000,https://localhost:3000"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """用于把逗号分隔的 CORS 配置整理成列表。"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return []

    @field_validator("AUTH_COOKIE_SAMESITE", mode="before")
    def normalize_auth_cookie_samesite(
        cls, value: str
    ) -> Literal["lax", "strict", "none"]:
        """用于规范化 SameSite 配置并拦截非法值。"""
        normalized = str(value).strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
        return cast(Literal["lax", "strict", "none"], normalized)

    # OpenAI Agents SDK
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_AGENTS_PROVIDER: str = os.getenv("OPENAI_AGENTS_PROVIDER", "openai")
    OPENAI_AGENTS_MODEL: str = os.getenv("OPENAI_AGENTS_MODEL", "gpt-5.5")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    DEEPSEEK_THINKING_TYPE: str = os.getenv("DEEPSEEK_THINKING_TYPE", "disabled")

    # OpenRouter API
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_BASE: str = os.getenv(
        "OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL",
        "deepseek/deepseek-v4-pro",
    )
    OPENROUTER_VISION_MODEL: str = os.getenv(
        "OPENROUTER_VISION_MODEL",
        "qwen/qwen2.5-vl-72b-instruct",
    )
    OPENROUTER_VISION_FALLBACK_MODELS: str = os.getenv(
        "OPENROUTER_VISION_FALLBACK_MODELS",
        "google/gemini-2.5-flash",
    )
    OPENROUTER_JOB_MATCH_MODEL: str = os.getenv(
        "OPENROUTER_JOB_MATCH_MODEL",
        os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-pro"),
    )
    OPENROUTER_CONNECT_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_CONNECT_TIMEOUT_SECONDS", "15")
    )
    OPENROUTER_READ_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_READ_TIMEOUT_SECONDS", "90")
    )
    OPENROUTER_WRITE_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_WRITE_TIMEOUT_SECONDS", "30")
    )
    OPENROUTER_FIRST_EVENT_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_FIRST_EVENT_TIMEOUT_SECONDS", "120")
    )
    OPENROUTER_FIRST_TOKEN_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_FIRST_TOKEN_TIMEOUT_SECONDS", "0")
    )
    OPENROUTER_MAX_RETRIES: int = int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))
    OPENROUTER_RETRY_BACKOFF_SECONDS: float = float(
        os.getenv("OPENROUTER_RETRY_BACKOFF_SECONDS", "1")
    )
    OPENROUTER_CIRCUIT_BREAKER_ENABLED: bool = (
        os.getenv("OPENROUTER_CIRCUIT_BREAKER_ENABLED", "true").strip().lower()
        == "true"
    )
    OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(
        os.getenv("OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    )
    OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS: float = float(
        os.getenv("OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "30")
    )

    # 火山引擎实时语音大模型开场触发音频合成凭证
    VOLCENGINE_ACCESS_TOKEN: str = os.getenv("VOLCENGINE_ACCESS_TOKEN", "")

    # 火山引擎TTS API
    VOLCENGINE_TTS_API_KEY: str = os.getenv("VOLCENGINE_TTS_API_KEY", "")
    VOLCENGINE_TTS_APP_ID: str = os.getenv("VOLCENGINE_TTS_APP_ID", "")
    # volcano_mega = 大模型语音合成；volcano_tts = 标准语音合成
    VOLCENGINE_TTS_CLUSTER: str = os.getenv("VOLCENGINE_TTS_CLUSTER", "")

    # 火山引擎端到端实时语音大模型
    VOLCENGINE_DIALOGUE_APP_ID: str = os.getenv("VOLCENGINE_DIALOGUE_APP_ID", "")
    VOLCENGINE_DIALOGUE_ACCESS_KEY: str = os.getenv(
        "VOLCENGINE_DIALOGUE_ACCESS_KEY", ""
    )
    VOLCENGINE_DIALOGUE_RESOURCE_ID: str = os.getenv(
        "VOLCENGINE_DIALOGUE_RESOURCE_ID", "volc.speech.dialog"
    )
    VOLCENGINE_DIALOGUE_SPEAKER_ID: str = os.getenv(
        "VOLCENGINE_DIALOGUE_SPEAKER_ID", ""
    )
    VOLCENGINE_DIALOGUE_WS_URL: str = os.getenv(
        "VOLCENGINE_DIALOGUE_WS_URL",
        "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
    )

    # File upload
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    USER_MEMORY_DIR: str = os.getenv("USER_MEMORY_DIR", "data/memory/users")
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    JD_OCR_MAX_FILE_SIZE: int = int(
        os.getenv("JD_OCR_MAX_FILE_SIZE", str(10 * 1024 * 1024))
    )
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "60")
    )
    PASSWORD_RESET_EMAIL_FROM: str = os.getenv(
        "PASSWORD_RESET_EMAIL_FROM", "no-reply@chat-resume.local"
    )
    PASSWORD_RESET_SMTP_HOST: str = os.getenv("PASSWORD_RESET_SMTP_HOST", "")
    PASSWORD_RESET_SMTP_PORT: int = int(os.getenv("PASSWORD_RESET_SMTP_PORT", "587"))
    PASSWORD_RESET_SMTP_USERNAME: str = os.getenv("PASSWORD_RESET_SMTP_USERNAME", "")
    PASSWORD_RESET_SMTP_PASSWORD: str = os.getenv("PASSWORD_RESET_SMTP_PASSWORD", "")
    PASSWORD_RESET_SMTP_TLS: bool = (
        os.getenv("PASSWORD_RESET_SMTP_TLS", "true").strip().lower() == "true"
    )

    # Runtime logs
    RELEASE_IDENTIFIER: str = os.getenv(
        "RELEASE_IDENTIFIER",
        os.getenv("RAILWAY_GIT_COMMIT_SHA", ""),
    )

    # Agent session 超时配置
    AGENT_SESSION_CONFIRMATION_TIMEOUT_SECONDS: int = int(
        os.getenv("AGENT_SESSION_CONFIRMATION_TIMEOUT_SECONDS", "600")
    )

    model_config = {"case_sensitive": True, "env_file": ".env", "extra": "ignore"}


def validate_secret_key(config: Settings) -> None:
    """用于校验密钥键。"""
    app_env = config.APP_ENV.strip().lower()
    secret_key = config.SECRET_KEY.strip()
    if app_env in _LOCAL_APP_ENVS:
        return
    if not secret_key or secret_key == DEFAULT_SECRET_KEY:
        raise ValueError(
            "SECRET_KEY must be set to a non-default value outside development."
        )


settings = Settings.model_validate({})
validate_secret_key(settings)
