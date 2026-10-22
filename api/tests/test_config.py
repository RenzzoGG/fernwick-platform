import secrets

from app.config import Settings

APP_URL = "postgresql://fernwick_app:x@host/fernwick"


def settings(**values) -> Settings:
    # _env_file=None: solo los valores dados, sin leer el .env de quien corre las pruebas
    return Settings(_env_file=None, jwt_secret=secrets.token_urlsafe(48), **values)


def test_migraciones_usan_la_url_del_dueno_si_esta():
    config = settings(database_url=APP_URL, migrations_database_url="postgres://postgres:y@host/fernwick")
    # Normalizada al driver psycopg 3, igual que DATABASE_URL
    assert config.owner_database_url == "postgresql+psycopg://postgres:y@host/fernwick"


def test_sin_url_del_dueno_se_usa_database_url():
    config = settings(database_url=APP_URL, migrations_database_url=None)
    assert config.owner_database_url == "postgresql+psycopg://fernwick_app:x@host/fernwick"
