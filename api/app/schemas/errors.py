"""Respuestas de error documentadas en /docs.

FastAPI solo documenta por sí mismo el 200/201 y el 422; los demás códigos que devuelve una
ruta (401, 403, 404...) aparecen como "Undocumented" en /docs. Estos diccionarios se pasan en
`responses=` de cada ruta para que el contrato completo quede escrito en el OpenAPI.
"""

from typing import Any

from pydantic import BaseModel

from app.middleware import TOO_LARGE_DETAIL


class ErrorDetail(BaseModel):
    """Formato estándar de error de FastAPI: {"detail": "..."}."""

    detail: str


def _error(description: str, detail: str) -> dict[str, Any]:
    return {
        "model": ErrorDetail,
        "description": description,
        "content": {"application/json": {"example": {"detail": detail}}},
    }


UNAUTHORIZED = {
    401: _error(
        "Falta el token, es inválido o venció, o el usuario está desactivado.",
        "Could not validate credentials.",
    )
}
LOGIN_FAILED = {
    401: _error(
        "Email o contraseña incorrectos, usuario inactivo o no admin (siempre el mismo mensaje).",
        "Incorrect email or password.",
    )
}
FORBIDDEN = {
    403: _error(
        "El usuario no tiene permiso (p. ej. la cuenta demo intenta escribir).",
        "You do not have permission to perform this action.",
    )
}
QUOTE_NOT_FOUND = {
    404: _error(
        "La cotización no existe o no es visible para este usuario.", "Quote not found."
    )
}
STATUS_CONFLICT = {
    409: _error("La cotización ya tiene ese estado.", "Quote already has this status.")
}
TOO_MANY_REQUESTS = {
    429: _error(
        "Demasiadas solicitudes desde esta IP. El header Retry-After dice cuántos segundos esperar.",
        "Too many requests. Please try again later.",
    )
}
PAYLOAD_TOO_LARGE = {413: _error("El cuerpo supera los 10 KB.", TOO_LARGE_DETAIL)}
DEMO_NOT_FOUND = {
    404: _error(
        "La cuenta demo está desactivada (DEMO_ENABLED=false) o falta el usuario demo.",
        "Not Found",
    )
}
