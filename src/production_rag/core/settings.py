from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Production RAG"
    app_version: str = "0.1.0"
    debug: bool = False

    # Comma-separated collections the public API is allowed to query.
    allowed_collections: str = "fastapi"

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

    # Cost-control bounds for the public API. Both must be positive.
    max_output_tokens: int = Field(default=1024, gt=0)
    max_context_characters: int = Field(default=12000, gt=0)

    # Public API rate limit: requests allowed per client per 60-second window.
    rate_limit_requests: int = Field(default=10, gt=0)
    # Read the client IP from the Cloud Run X-Forwarded-For chain. Enable only
    # for verified direct Cloud Run ingress (see README); defaults to the direct
    # TCP peer, which cannot be spoofed by request headers.
    rate_limit_trust_cloud_run_x_forwarded_for: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf_8",
        extra="ignore",
    )

    @property
    def allowed_collection_names(self) -> frozenset[str]:
        return frozenset(
            name.strip() for name in self.allowed_collections.split(",") if name.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
