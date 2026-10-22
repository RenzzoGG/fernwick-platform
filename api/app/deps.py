"""Dependencias de FastAPI para las rutas protegidas: quién hace la petición y qué puede hacer."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.security import InvalidTokenError, decode_access_token

# Lee el header "Authorization: Bearer <token>" y agrega el botón "Authorize" en /docs.
# auto_error=False: si falta, devuelve None y respondemos nosotros con 401 (y nuestro mensaje).
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    # Mismo mensaje para todos los casos (sin token, vencido, firma mala, usuario inactivo):
    # no se le dice al atacante qué falló. WWW-Authenticate lo pide el estándar HTTP en un 401.
    return HTTPException(
        status_code=401,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """El usuario dueño del token. Se usa como `user: Annotated[User, Depends(get_current_user)]`."""
    if credentials is None:
        raise _unauthorized()
    try:
        claims = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError:
        raise _unauthorized() from None

    # Se vuelve a cargar de la base en cada petición: si se desactivó o se borró, el token
    # deja de servir de inmediato. El rol que vale es el de la base, no el del token.
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Crea una dependencia que deja pasar solo a los roles dados, p. ej. require_role("admin")."""

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            # 403 y no 401: sabemos quién es, pero no tiene permiso
            raise HTTPException(
                status_code=403, detail="You do not have permission to perform this action."
            )
        return user

    return dependency
