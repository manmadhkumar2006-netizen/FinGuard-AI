from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "FinGuard AI"
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None

    # Resolve this explicitly so `backend/.env` is used even when Uvicorn is
    # started from the repository root or a process manager's working directory.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")


settings = Settings()
