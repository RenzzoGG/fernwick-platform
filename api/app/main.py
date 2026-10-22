"""Punto de entrada de la API: `uvicorn app.main:app`."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.config import get_settings
from app.deps import FORBIDDEN_DETAIL
from app.logging_config import configure_logging
from app.middleware import BodySizeLimitMiddleware
from app.routers import auth, health, metrics, public, quotes

logger = logging.getLogger(__name__)

# SQLSTATE de PostgreSQL para "permiso denegado", tanto por GRANT como por una política de RLS
INSUFFICIENT_PRIVILEGE = "42501"

settings = get_settings()
configure_logging(settings.environment)

# Una cotización legítima ocupa < 2 KB; 10 KB deja margen y frena cuerpos gigantes
MAX_BODY_BYTES = 10 * 1024

app = FastAPI(
    title="Fernwick API",
    version="0.1.0",
    # La documentación automática solo fuera de producción (no exponer el mapa de la API)
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Orden: el último middleware agregado es la capa más externa. CORS va por fuera para que
# también las respuestas 413 lleven sus headers (si no, el navegador las vería como error de red).
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)

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
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(quotes.router)
app.include_router(metrics.router)


@app.exception_handler(DBAPIError)
async def database_permission_denied(request: Request, exc: DBAPIError) -> JSONResponse:
    """La base negó la operación por permisos o RLS -> 403 (DESIGN §3.3).

    Solo pasa si falló la primera capa (require_role o el filtro de servicios): por eso queda
    en el log como advertencia. Cualquier otro error de la base sigue siendo un 500.
    """
    if getattr(exc.orig, "sqlstate", None) != INSUFFICIENT_PRIVILEGE:
        raise exc
    logger.warning("La base negó una operación por permisos: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=403, content={"detail": FORBIDDEN_DETAIL})
