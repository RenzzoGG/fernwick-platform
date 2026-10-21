"""Punto de entrada de la API: `uvicorn app.main:app`."""

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health

settings = get_settings()

app = FastAPI(
    title="Fernwick API",
    version="0.1.0",
    # La documentación automática solo fuera de producción (no exponer el mapa de la API)
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.include_router(health.router)
