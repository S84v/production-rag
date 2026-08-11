from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Production RAG"
    app_version: str = "0.1.0"
    debug: bool = False

    postgres_user: str = "production_rag"
    postgres_password: str = "production_rag_dev"
    postgres_db: str = "production_rag"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf_8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
