from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from production_rag.api.query import router as query_router
from production_rag.api.rate_limit import RateLimiter
from production_rag.core.settings import Settings, get_settings
from production_rag.services.rag import RAGService
from production_rag.telemetry import configure_telemetry

settings = get_settings()


def configure_cors(app: FastAPI, settings: Settings | None = None) -> None:
    """Allow the configured browser origins to call the API cross-origin.

    Only the exact configured origins are allowed: there is no wildcard or
    regex matching. Credentials stay disabled because the API uses none. When no
    origins are configured the middleware is not added, preserving the local
    (same-origin / Vite proxy) setup.
    """
    origins = (settings or get_settings()).cors_allowed_origin_list

    if not origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag_service = RAGService()
    app.state.rate_limiter = RateLimiter(limit=settings.rate_limit_requests)
    yield
    await app.state.rag_service.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

configure_telemetry(app)

configure_cors(app)

app.include_router(query_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
