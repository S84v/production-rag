from fastapi import FastAPI

from production_rag.api.query import router as query_router
from production_rag.core.settings import get_settings
from production_rag.telemetry import configure_telemetry

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)

configure_telemetry(app)

app.include_router(query_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
