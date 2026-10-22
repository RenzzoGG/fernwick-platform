"""Login del panel: con contraseña (admin) o con un clic (cuenta demo)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.rate_limit import RateLimiter, rate_limit
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.security import create_access_token
from app.services.auth import authenticate, get_demo_user, record_login

logger = logging.getLogger(__name__)

# Por IP (DESIGN §5.5). El del login frena la fuerza bruta: 10 intentos por minuto.
login_limiter = RateLimiter([(10, 60)])
demo_limiter = RateLimiter([(20, 60)])

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _token_for(user: User, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, settings),
        expires_in=settings.jwt_expire_minutes * 60,
        role=user.role,
    )


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(rate_limit(login_limiter))]
)
def login(
    data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = authenticate(db, data.email, data.password)
    if user is None:
        # Sin el email: es dato personal y ayudaría a quien lea los logs a probar cuentas
        logger.info("Login fallido")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_login(db, user)
    logger.info("Login correcto: usuario %s", user.id)
    return _token_for(user, settings)


@router.post(
    "/demo", response_model=TokenResponse, dependencies=[Depends(rate_limit(demo_limiter))]
)
def demo_login(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    # Apagado: 404 igual que una ruta que no existe
    if not settings.demo_enabled:
        raise HTTPException(status_code=404)
    user = get_demo_user(db)
    if user is None:
        logger.warning("Demo activado pero sin usuario demo: corre `python -m app.cli seed-demo`")
        raise HTTPException(status_code=404)
    record_login(db, user)
    return _token_for(user, settings)


@router.get("/me", response_model=CurrentUser)
def me(user: Annotated[User, Depends(get_current_user)]) -> CurrentUser:
    return CurrentUser.model_validate(user)
