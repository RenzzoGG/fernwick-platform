"""Endpoints públicos (sin login): el formulario de cotización de la landing."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.rate_limit import RateLimiter, rate_limit
from app.schemas.quote import PublicQuoteCreate, PublicQuoteCreated
from app.services.quotes import create_public_quote, fake_quote_receipt

logger = logging.getLogger(__name__)

# 5 por minuto y 20 por día, por IP (DESIGN §5.5)
quote_limiter = RateLimiter([(5, 60), (20, 24 * 60 * 60)])

router = APIRouter(prefix="/v1/public", tags=["public"])


@router.post(
    "/quotes",
    status_code=201,
    response_model=PublicQuoteCreated,
    # Las dependencias de `dependencies=[...]` se ejecutan pero su valor no se usa
    dependencies=[Depends(rate_limit(quote_limiter))],
)
def create_quote(
    data: PublicQuoteCreate, db: Annotated[Session, Depends(get_db)]
) -> PublicQuoteCreated:
    if data.website:
        # Honeypot lleno: es un bot. Se responde igual que un éxito (mismo formato de id y
        # fecha) para que no aprenda que fue detectado, pero no se guarda nada.
        # El log no incluye datos personales.
        logger.info("Honeypot activado: cotización descartada")
        fake_id, now = fake_quote_receipt(db)
        return PublicQuoteCreated(id=fake_id, created_at=now)

    quote = create_public_quote(db, data)
    return PublicQuoteCreated.model_validate(quote)
