"""Endpoints del panel de administración: cotizaciones.

Los routers solo traducen HTTP. El filtro demo/real lo aplican los servicios con el usuario
que reciben, así ninguna ruta puede saltárselo.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import User
from app.schemas.errors import FORBIDDEN, QUOTE_NOT_FOUND, STATUS_CONFLICT, UNAUTHORIZED
from app.schemas.quote import (
    QuoteDetail,
    QuoteListParams,
    QuotePage,
    QuoteSummary,
    StatusUpdate,
)
from app.services.quotes import StatusUnchangedError, change_status, get_quote, list_quotes

# responses a nivel de router: todas las rutas exigen token y pueden responder 401
router = APIRouter(prefix="/v1/quotes", tags=["quotes"], responses=UNAUTHORIZED)

# Ids válidos de una columna bigint: uno mayor haría fallar a PostgreSQL (500) en vez de dar 422
BIGINT_MAX = 2**63 - 1
QuoteId = Annotated[int, Path(ge=1, le=BIGINT_MAX)]
# Escrituras: solo admin. La dependencia corre antes que la ruta, así el demo recibe 403
# aunque el id no exista (no aprende nada sobre qué ids hay)
AdminUser = Annotated[User, Depends(require_role("admin"))]


def _not_found() -> HTTPException:
    # Mismo 404 si no existe o si no es visible para el usuario (demo pidiendo una real)
    return HTTPException(status_code=404, detail="Quote not found.")


@router.get("", response_model=QuotePage)
def get_quotes(
    # Query(): FastAPI arma el modelo con los parámetros de la URL y lo valida (422 si no sirve)
    params: Annotated[QuoteListParams, Query()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> QuotePage:
    items, total = list_quotes(db, user, params)
    return QuotePage(
        items=[QuoteSummary.model_validate(quote) for quote in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{quote_id}", response_model=QuoteDetail, responses=QUOTE_NOT_FOUND)
def get_quote_detail(
    quote_id: QuoteId,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> QuoteDetail:
    quote = get_quote(db, user, quote_id)
    if quote is None:
        raise _not_found()
    return QuoteDetail.from_quote(quote)


@router.patch(
    "/{quote_id}/status",
    response_model=QuoteDetail,
    responses={**FORBIDDEN, **QUOTE_NOT_FOUND, **STATUS_CONFLICT},
)
def update_quote_status(
    quote_id: QuoteId,
    data: StatusUpdate,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> QuoteDetail:
    try:
        quote = change_status(db, user, quote_id, data.status)
    except StatusUnchangedError:
        raise HTTPException(status_code=409, detail="Quote already has this status.") from None
    if quote is None:
        raise _not_found()
    return QuoteDetail.from_quote(quote)
