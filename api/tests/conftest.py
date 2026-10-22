import os
import secrets
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
# Sin confiar en encabezados de proxy, como en desarrollo (test_client_ip.py prueba los otros modos)
os.environ["CLIENT_IP_HEADER"] = "none"
# Secreto aleatorio en cada ejecución: las pruebas no dependen del .env ni guardan ningún secreto
os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["DEMO_ENABLED"] = "true"
get_settings.cache_clear()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import APP_ROLE, ROLE_KEY, engine, get_db, set_role  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.user import DEMO_EMAIL  # noqa: E402
from app.routers.auth import demo_limiter, login_limiter  # noqa: E402
from app.routers.public import quote_limiter  # noqa: E402
from app.services.auth import create_admin  # noqa: E402
from tests.helpers import CLAVE  # noqa: E402

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
def client(db_session: Session) -> Iterator[TestClient]:
    # Las rutas usan la misma sesión que la prueba: sus commit() solo cierran un SAVEPOINT,
    # todo se revierte al final y la prueba puede consultar lo que guardó la API
    def override_get_db() -> Iterator[Session]:
        # Igual que get_db: la petición corre como fernwick_app (y get_db_for_user la pasa a
        # fernwick_demo si es el demo). La conexión de las pruebas es del dueño, que salta RLS:
        # sin esto las pruebas de la API no probarían RLS.
        set_role(db_session, APP_ROLE)
        try:
            yield db_session
        finally:
            # De vuelta al dueño para que la prueba pueda revisar o preparar datos sin RLS
            db_session.info.pop(ROLE_KEY, None)
            db_session.execute(text("RESET ROLE"))

    app.dependency_overrides[get_db] = override_get_db
    # TestClient llama a la app en el mismo proceso, sin levantar un servidor
    with TestClient(app) as test_client:
        yield test_client
    # Si un test reemplazó dependencias, se restauran para no afectar a los demás
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limits() -> None:
    # El limitador vive en memoria del proceso: sin esto, una prueba agotaría el cupo de la siguiente
    quote_limiter.reset()
    login_limiter.reset()
    demo_limiter.reset()


@pytest.fixture
def admin(db_session: Session) -> User:
    return create_admin(db_session, "admin@example.com", CLAVE)


@pytest.fixture
def demo(db_session: Session) -> User:
    # Igual que lo crea seed-demo: "!" no es un hash válido, nadie entra con contraseña
    user = User(email=DEMO_EMAIL, password_hash="!", role="demo")
    db_session.add(user)
    db_session.flush()
    return user
