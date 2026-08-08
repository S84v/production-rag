from fastapi import FastAPI

from production_rag.core.settings import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
