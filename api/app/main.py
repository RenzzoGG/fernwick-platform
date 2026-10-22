"""Punto de entrada de la API: `uvicorn app.main:app`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# CORS: le dice al navegador qué páginas pueden leer las respuestas de la API.
# No es autenticación (curl lo ignora); solo evita que otras webs usen la API desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,  # no usamos cookies
)

app.include_router(health.router)
