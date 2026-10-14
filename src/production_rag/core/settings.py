from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings(BaseSettings):
    app_name: str = "Production RAG"
    app_version: str = "0.1.0"
    debug: bool = False

    # Comma-separated collections the public API is allowed to query.
    allowed_collections: str = "fastapi"

    # Comma-separated browser origins allowed to call the API cross-origin.
    # Empty disables CORS (the default; local development uses the Vite proxy).
    # Origins are exact (scheme://host[:port]); '*' is not supported.
    cors_allowed_origins: str = ""

    # Optional async PostgreSQL URL for a hosted database (e.g. Neon). When set
    # it takes precedence over the POSTGRES_* local defaults. The `postgres://`
    # and `postgresql://` schemes and the libpq `sslmode` parameter are
    # normalized for the asyncpg driver by db.url.build_database_url.
    database_url: str = ""

    postgres_user: str = "production_rag"
    postgres_password: str = "production_rag_dev"
    postgres_db: str = "production_rag"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Optional hosted Qdrant endpoint. When set it takes precedence over the
    # QDRANT_HOST/QDRANT_PORT local defaults; QDRANT_API_KEY is used for auth.
    qdrant_url: str = ""
    qdrant_api_key: str = ""

    # Immutable Hugging Face revision for the embedding model. Empty keeps the
    # default resolution; the container image sets this so the runtime loads
    # exactly the baked snapshot. Changing it can invalidate existing embeddings
    # and requires re-ingestion.
    embedding_model_revision: str = ""

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

    @field_validator("cors_allowed_origins")
    @classmethod
    def _reject_wildcard_origin(cls, value: str) -> str:
        if "*" in _split_origins(value):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must not contain '*' (unrestricted origins "
                "are not supported); configure exact origins instead."
            )

        return value

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return _split_origins(self.cors_allowed_origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
