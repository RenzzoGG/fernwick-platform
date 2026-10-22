"""Funciones de apoyo compartidas por las pruebas (las fixtures están en conftest.py)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from itertools import count
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Quote, User
from app.security import create_access_token

CLAVE = "una clave bastante larga"

_numeros = count(1)


def bearer(user: User, **kwargs) -> dict[str, str]:
    token = create_access_token(user.id, user.role, get_settings(), **kwargs)
    return {"Authorization": f"Bearer {token}"}


def local(day: date, hour: int = 12, minute: int = 0) -> datetime:
    """Un instante del día dado en la zona del negocio (con zona: se guarda como UTC)."""
    tz = ZoneInfo(get_settings().business_timezone)
    return datetime.combine(day, time(hour, minute), tzinfo=tz)


def make_quote(session: Session, **overrides) -> Quote:
    """Crea una cotización válida (real por defecto); cada llamada usa datos distintos."""
    n = next(_numeros)
    data = {
        "name": f"Cliente {n}",
        "email": f"cliente{n}@example.com",
        "phone": f"(212) 555-{n:04d}",
        "service": "standard",
        "home_size": "2-bed",
        "preferred_date": date(2026, 12, 1) + timedelta(days=n % 30),
        "status": "new",
        "is_demo": False,
        # Fechas distintas y conocidas para probar el orden (sin depender de now())
        "created_at": datetime(2026, 10, 1, 12, tzinfo=timezone.utc) + timedelta(minutes=n),
    }
    quote = Quote(**(data | overrides))
    session.add(quote)
    session.flush()
    return quote


@contextmanager
def como_rol(session: Session, role: str) -> Iterator[None]:
    """Ejecuta el bloque con SET LOCAL ROLE `role` y luego vuelve al rol de la conexión (dueño).

    `role` es siempre una constante de las pruebas: un nombre de rol no puede ir como parámetro.
    """
    session.execute(text(f"SET LOCAL ROLE {role}"))
    try:
        yield
    finally:
        session.execute(text("RESET ROLE"))
