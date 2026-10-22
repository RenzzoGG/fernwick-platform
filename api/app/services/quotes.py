"""Lógica de negocio de las cotizaciones."""

from sqlalchemy.orm import Session

from app.models import Quote
from app.schemas.quote import PublicQuoteCreate


def create_public_quote(session: Session, data: PublicQuoteCreate) -> Quote:
    """Guarda una cotización enviada desde el formulario público."""
    quote = Quote(
        # Campos copiados uno por uno (no **data): si el esquema crece, nada llega a la base por accidente
        name=data.name,
        email=data.email,
        phone=data.phone,
        service=data.service,
        home_size=data.home_size,
        preferred_date=data.preferred_date,
        message=data.message,
        # Los fija el servidor, nunca el cliente
        status="new",
        is_demo=False,
    )
    session.add(quote)
    session.commit()
    # refresh: lee de la base los valores que asignó PostgreSQL (id, created_at)
    session.refresh(quote)
    return quote
