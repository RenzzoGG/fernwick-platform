import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.config import get_settings

# --- Apuntar TODA la suite a la base de pruebas, antes de importar la app ---
# app.db crea el engine al importarse con DATABASE_URL; por eso este bloque va primero.
_test_url = get_settings().test_database_url
if not _test_url:
    pytest.exit("Falta TEST_DATABASE_URL en api/.env (ver api/.env.example).", returncode=1)
# Salvaguarda: las pruebas borran y recrean las tablas. Nunca contra una base que no sea de pruebas.
if not (make_url(_test_url).database or "").endswith("_test"):
    pytest.exit("TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test.", returncode=1)
os.environ["DATABASE_URL"] = _test_url
# Orígenes fijos para las pruebas: no dependen de lo que tenga cada uno en su .env
os.environ["CORS_ORIGINS"] = "http://localhost:8000,http://localhost:5173"
get_settings.cache_clear()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", _test_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_db(alembic_config: Config) -> None:
    """Una vez por ejecución de pytest: base vacía y migraciones aplicadas desde cero."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sesión dentro de una transacción que se revierte al final: cada prueba deja la base limpia.

    join_transaction_mode="create_savepoint": si la prueba hace commit() o rollback(), solo
    afecta a un SAVEPOINT; la transacción externa sigue abierta y se revierte siempre.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    # TestClient llama a la app en el mismo proceso, sin levantar un servidor
    with TestClient(app) as test_client:
        yield test_client
    # Si un test reemplazó dependencias, se restauran para no afectar a los demás
    app.dependency_overrides.clear()
