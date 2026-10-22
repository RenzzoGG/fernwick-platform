"""Endpoint de salud: lo usan Railway (healthcheck) y nosotros para diagnosticar."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    responses={
        200: {"content": {"application/json": {"example": {"status": "ok", "db": "ok"}}}},
        503: {
            "description": "La base de datos no responde.",
            "content": {"application/json": {"example": {"status": "error", "db": "unavailable"}}},
        },
    },
)
def health(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    try:
        # La consulta más barata posible: solo confirma que hay conexión
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # El detalle va al log; al cliente no se le muestra (podría revelar host o usuario)
        logger.exception("Health check: la base de datos no responde")
        return JSONResponse(status_code=503, content={"status": "error", "db": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok", "db": "ok"})
