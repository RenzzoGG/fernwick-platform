"""Conexión a PostgreSQL con SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# El engine se crea una vez por proceso y administra un pool de conexiones.
# pool_pre_ping: antes de prestar una conexión del pool comprueba que siga viva
# (p. ej. si PostgreSQL se reinició), y si no, abre una nueva.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, que se cierra al terminar."""
    with SessionLocal() as session:
        yield session
