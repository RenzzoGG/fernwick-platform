from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db import engine

TABLAS = {"users", "quotes", "quote_notes", "quote_status_changes"}


def tablas_actuales() -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_desde_cero_crea_todo(alembic_config):
    # La fixture migrated_db ya hizo downgrade base + upgrade head al iniciar la suite
    head = ScriptDirectory.from_config(alembic_config).get_current_head()
    with engine.connect() as conn:
        version = conn.scalar(text("SELECT version_num FROM alembic_version"))
        extension = conn.scalar(text("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'"))
        indices = set(conn.scalars(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")))

    assert tablas_actuales() == TABLAS
    assert version == head
    assert extension == "pg_trgm"
    assert {
        "uq_users_email_lower",
        "ix_quotes_is_demo_status_created_at",
        "ix_quotes_is_demo_created_at",
        "ix_quotes_name_trgm",
        "ix_quotes_email_trgm",
        "ix_quote_notes_quote_id_created_at",
        "ix_quote_status_changes_quote_id_changed_at",
    } <= indices


def test_downgrade_y_upgrade_son_reversibles(alembic_config):
    command.downgrade(alembic_config, "base")
    assert tablas_actuales() == set()

    command.upgrade(alembic_config, "head")
    assert tablas_actuales() == TABLAS
