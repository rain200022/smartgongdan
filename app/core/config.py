from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Gongdan API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://smartgongdan:smartgongdan@localhost:5432/smartgongdan"
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
