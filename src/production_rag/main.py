from contextlib import asynccontextmanager

from fastapi import FastAPI

from production_rag.api.query import router as query_router
from production_rag.core.settings import get_settings
from production_rag.services.rag import RAGService
from production_rag.telemetry import configure_telemetry

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag_service = RAGService()
    yield
    await app.state.rag_service.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

configure_telemetry(app)

app.include_router(query_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
