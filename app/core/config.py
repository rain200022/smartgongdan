import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Gongdan API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://smartgongdan:smartgongdan@localhost:5432/smartgongdan"
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    ai_provider: Literal["local", "openai_compatible"] = "local"
    ai_model: str = "local-rules-v1"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str | None = None
    ai_timeout_seconds: float = Field(default=30.0, gt=0)
    embedding_provider: Literal["local"] = "local"
    embedding_model: str = "local-hash-v1"
    embedding_dimensions: Literal[128] = 128
    auth_cookie_name: str = "smartgongdan_session"
    auth_cookie_secure: bool = False
    auth_session_hours: int = Field(default=8, ge=1, le=720)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
