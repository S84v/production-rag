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

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf_8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
