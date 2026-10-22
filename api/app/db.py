"""Conexión a PostgreSQL con SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine, pool
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# Roles de PostgreSQL con los que trabaja la API (los crea la migración 0003, DESIGN §3)
APP_ROLE = "fernwick_app"
DEMO_ROLE = "fernwick_demo"

# El engine se crea una vez por proceso y administra un pool de conexiones.
# pool_pre_ping: antes de prestar una conexión del pool comprueba que siga viva
# (p. ej. si PostgreSQL se reinició), y si no, abre una nueva.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, que se cierra al terminar."""
    with SessionLocal() as session:
        yield session


def owner_session() -> Session:
    """Sesión como dueño de las tablas (MIGRATIONS_DATABASE_URL), solo para seed-demo.

    El rol de la API no puede escribir filas demo (RLS) y el demo no puede escribir nada.
    NullPool: el comando abre una conexión, trabaja y la cierra; no necesita un pool.
    """
    owner_engine = create_engine(get_settings().owner_database_url, poolclass=pool.NullPool)
    return Session(bind=owner_engine, autoflush=False, expire_on_commit=False)
