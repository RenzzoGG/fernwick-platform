"""Entorno de Alembic: cómo se conecta a la base y qué modelos compara."""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: no apagar los loggers de la app (p. ej. en pytest)
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Metadata de los modelos: `alembic revision --autogenerate` la compara con la base
target_metadata = Base.metadata


def get_url() -> str:
    # Quien llame a Alembic desde código (las pruebas) puede fijar la URL; si no, la del dueño
    # (MIGRATIONS_DATABASE_URL, o DATABASE_URL si no está). Nunca un valor escrito en alembic.ini.
    # Las migraciones crean tablas, roles y políticas: el rol de la API no tiene permiso para eso.
    return config.get_main_option("sqlalchemy.url") or get_settings().owner_database_url


def run_migrations_offline() -> None:
    """Modo offline (`alembic upgrade head --sql`): imprime el SQL sin conectarse."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo normal: se conecta y aplica las migraciones dentro de una transacción."""
    # NullPool: Alembic abre una conexión, migra y la cierra; no necesita un pool
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
