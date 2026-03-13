"""Configuration management using pydantic-settings."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Valid values: "production" or "development"
    APP_ENV: str = "production"

    # HuggingFace Config
    HUGGINGFACE_API_TOKEN: str
    HUGGINGFACE_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    HUGGINGFACE_TIMEOUT: int = 30

    # OpenAI Config (fallback when HuggingFace is rate-limited)
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Retry Config
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: float = 1.0

    # LLM Generation Config
    LLM_MAX_TOKENS: int = 256
    LLM_TEMPERATURE: float = 0.01

    # API Config
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    REQUEST_TIMEOUT_SECONDS: int = 120

    # Database
    DATABASE_URL_OVERRIDE: str | None = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 1433
    DB_NAME: str = "nlpdf_db"
    DB_USER: str = "sa"
    DB_PASSWORD: str
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"

    # JWT Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email Service
    RESEND_API_KEY: str
    EMAIL_FROM: str = "NLPDF <noreply@nlpdf.site>"

    # Cookies
    COOKIE_SECURE: bool = True
    COOKIE_DOMAIN: str | None = None

    # Cloudflare Turnstile
    CLOUDFLARE_TURNSTILE_SECRET_KEY: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _apply_dev_overrides(self) -> "Settings":
        """Relax production defaults when running in development."""
        if self.APP_ENV == "development":
            self.COOKIE_SECURE = False
        # Treat empty string as None (env var set but blank)
        if self.COOKIE_DOMAIN is not None and self.COOKIE_DOMAIN.strip() == "":
            self.COOKIE_DOMAIN = None
        return self


settings = Settings()  # type: ignore[call-arg]
