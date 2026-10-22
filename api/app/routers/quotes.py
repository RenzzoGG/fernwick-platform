"""Endpoints del panel de administración: cotizaciones.

Los routers solo traducen HTTP. El filtro demo/real lo aplican los servicios con el usuario
que reciben, así ninguna ruta puede saltárselo.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.errors import UNAUTHORIZED
from app.schemas.quote import QuoteListParams, QuotePage, QuoteSummary
from app.services.quotes import list_quotes

# responses a nivel de router: todas las rutas exigen token y pueden responder 401
router = APIRouter(prefix="/v1/quotes", tags=["quotes"], responses=UNAUTHORIZED)


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
