"""Lógica de negocio de las cotizaciones."""

from datetime import datetime

from sqlalchemy import text
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


def fake_quote_receipt(session: Session) -> tuple[int, datetime]:
    """Id y fecha para responder a un bot (honeypot) sin guardar nada.

    El id sale de la misma secuencia de la tabla: nextval consume un número igual que lo
    haría un INSERT (los huecos en los ids son normales), así la respuesta falsa es
    indistinguible de una real. No se inserta ninguna fila.
    """
    row = session.execute(
        text("SELECT nextval(pg_get_serial_sequence('quotes', 'id')), now()")
    ).one()
    # Cierra la transacción que abrió la consulta (nextval no se revierte con rollback)
    session.commit()
    return row[0], row[1]
