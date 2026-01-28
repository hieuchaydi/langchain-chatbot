# config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    PARTNER_API_KEY: str
    JWT_SECRET: str
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    UPLOAD_DIR: Path = Path("data/uploads")
    DB_PATH: Path = Path("data/bot_config.db")
    DATA_DIR: Path = BASE_DIR / "data"
    SESSION_SECRET: str | None = None
    CORS_ALLOW_ORIGINS: list[str] = ["*"]

    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2.onnx"
    LLM_MODEL: str = "gemini-2.5-flash-lite"

    API_RATE_CHAT: str = "100/minute"
    API_RATE_UPLOAD: str = "10/hour"
    API_RATE_ADMIN: str = "10/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )
    

settings = Settings()


settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
