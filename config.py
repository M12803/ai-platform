"""
Central configuration module using Pydantic Settings.
All values can be overridden via environment variables or a .env file.
"""
from pathlib import Path
from typing import Dict, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1  # Keep at 1 – LLMs are memory-heavy

    # ── Paths ─────────────────────────────────────────────────────────────────
    BASE_DIR: Path = BASE_DIR
    MODELS_DIR: Path = BASE_DIR / "models"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DB_PATH: str = str(BASE_DIR / "platform.db")

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="CHANGE_THIS_VERY_LONG_SECRET_KEY_IN_PRODUCTION_ENV",
        description="HMAC signing key for API tokens",
    )
    API_KEY_HEADER: str = "X-API-Key"
    VALID_API_KEYS: list[str] = Field(
        default=["local-dev-key-001"],
        description="Comma-separated list of valid API keys",
    )

    # ── Model Registry ────────────────────────────────────────────────────────
    # Maps logical operation names → model folder name inside ./models/
    OPERATION_MODEL_MAP: Dict[str, str] = {
        "summarize": "qwen-summarize",
        "translate": "qwen-translate",
        "classify": "qwen-classify",
    }

    # ── Inference Defaults ────────────────────────────────────────────────────
    DEFAULT_MAX_NEW_TOKENS: int = 512
    DEFAULT_TEMPERATURE: float = 0.2
    DEFAULT_TOP_P: float = 0.9

    # ── Per-Operation Hard Limits ──────────────────────────────────────────────
    # These cannot be exceeded regardless of user settings stored in DB.
    MAX_INPUT_CHARS: Dict[str, int] = {
        "summarize": 8000,
        "translate": 4000,
        "classify": 2000,
    }
    MAX_OUTPUT_TOKENS: Dict[str, int] = {
        "summarize": 512,
        "translate": 512,
        "classify": 64,
    }

    # ── Daily Limit Defaults (stored in DB, overridable via /limits) ──────────
    DEFAULT_DAILY_LIMIT: int = 1000

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_ROTATION_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5


settings = Settings()
