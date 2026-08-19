from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://budget_app:budget_app@localhost:5432/budget_app"
    )
    cors_origins: list[str] = ["http://localhost:5173"]
    statement_upload_max_bytes: int = 10 * 1024 * 1024
    ai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
