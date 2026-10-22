"""Row-Level Security directamente en SQL: lo que la base deja ver y escribir a cada rol.

Los datos los crea el dueño (con BYPASSRLS); después cada bloque corre con SET LOCAL ROLE,
igual que la API. Los errores esperados van dentro de un SAVEPOINT (begin_nested) para que la
transacción de la prueba siga usable.
"""

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import ProgrammingError

from app.db import APP_ROLE, DEMO_ROLE
from app.models import Quote, QuoteNote, QuoteStatusChange
from tests.helpers import como_rol, make_quote

INSUFFICIENT_PRIVILEGE = "42501"  # permiso denegado o violación de una política RLS


@pytest.fixture
def datos(db_session, admin, demo):
    real = make_quote(db_session)
    ficticia = make_quote(db_session, is_demo=True)
    for quote, autor in ((real, admin), (ficticia, demo)):
        db_session.add(QuoteNote(quote_id=quote.id, is_demo=quote.is_demo, author_id=autor.id, body="n"))
        db_session.add(QuoteStatusChange(
            quote_id=quote.id, is_demo=quote.is_demo, from_status="new", to_status="contacted",
            changed_by=autor.id,
        ))
    db_session.flush()
    return {"real": real, "ficticia": ficticia, "admin": admin, "demo": demo}


def assert_denegado(db_session, sql, params=None, mensaje="") -> None:
    with pytest.raises(ProgrammingError) as error, db_session.begin_nested():
        db_session.execute(text(sql), params or {})
    assert error.value.orig.sqlstate == INSUFFICIENT_PRIVILEGE
    assert mensaje in str(error.value.orig)


def visibles(db_session, model) -> set[bool]:
    """Los valores de is_demo que ve el rol actual en la tabla."""
    return set(db_session.scalars(select(model.is_demo)))


@pytest.mark.parametrize("model", [Quote, QuoteNote, QuoteStatusChange])
def test_cada_rol_ve_solo_su_lado(db_session, datos, model):
    with como_rol(db_session, APP_ROLE):
        assert visibles(db_session, model) == {False}
    with como_rol(db_session, DEMO_ROLE):
        assert visibles(db_session, model) == {True}
    # El dueño (BYPASSRLS) ve todo: lo usan las migraciones y seed-demo
    assert visibles(db_session, model) == {False, True}


def test_el_demo_no_puede_escribir_nada(db_session, datos):
    real, ficticia, demo = datos["real"], datos["ficticia"], datos["demo"]
    with como_rol(db_session, DEMO_ROLE):
        assert_denegado(db_session, "UPDATE quotes SET status = 'closed' WHERE id = :i", {"i": ficticia.id})
        assert_denegado(db_session, "DELETE FROM quotes WHERE id = :i", {"i": ficticia.id})
        assert_denegado(
            db_session,
            "INSERT INTO quote_notes (quote_id, is_demo, author_id, body) VALUES (:q, true, :a, 'x')",
            {"q": ficticia.id, "a": demo.id},
        )
        assert_denegado(
            db_session,
            "INSERT INTO quote_status_changes (quote_id, is_demo, from_status, to_status, changed_by) "
            "VALUES (:q, true, 'contacted', 'closed', :a)",
            {"q": ficticia.id, "a": demo.id},
        )
        assert_denegado(
            db_session,
            "INSERT INTO quotes (name, email, phone, service, home_size, preferred_date, is_demo) "
            "VALUES ('Ana Ruiz', 'ana@example.com', '212-555-0100', 'standard', '2-bed', "
            "current_date, true)",
        )
        assert_denegado(db_session, "UPDATE users SET role = 'admin' WHERE id = :i", {"i": demo.id})
    db_session.expire_all()
    assert db_session.get(Quote, ficticia.id).status == "new"
    assert db_session.get(Quote, real.id).status == "new"


def test_el_demo_no_lee_password_hash_ni_ve_a_los_admins(db_session, datos):
    with como_rol(db_session, DEMO_ROLE):
        assert_denegado(db_session, "SELECT password_hash FROM users", mensaje="table users")
        assert_denegado(db_session, "SELECT * FROM users")
        # Puede leer id y email, pero solo del usuario demo (política users_demo)
        emails = db_session.scalars(text("SELECT email FROM users")).all()
        assert emails == [datos["demo"].email]


def test_la_app_no_puede_crear_ni_tocar_filas_demo(db_session, datos):
    ficticia, admin = datos["ficticia"], datos["admin"]
    with como_rol(db_session, APP_ROLE):
        # WITH CHECK (NOT is_demo): ni un bug en el formulario puede crear una cotización demo
        assert_denegado(
            db_session,
            "INSERT INTO quotes (name, email, phone, service, home_size, preferred_date, is_demo) "
            "VALUES ('Ana Ruiz', 'ana@example.com', '212-555-0100', 'standard', '2-bed', "
            "current_date, true)",
            mensaje="row-level security",
        )
        assert_denegado(
            db_session,
            "INSERT INTO quote_notes (quote_id, is_demo, author_id, body) VALUES (:q, true, :a, 'x')",
            {"q": ficticia.id, "a": admin.id},
            mensaje="row-level security",
        )
        # USING (NOT is_demo): para la app la fila demo "no existe"; el UPDATE no la toca
        resultado = db_session.execute(
            update(Quote).where(Quote.id == ficticia.id).values(status="closed")
        )
        assert resultado.rowcount == 0
    db_session.expire_all()
    assert db_session.get(Quote, ficticia.id).status == "new"


def test_la_app_no_puede_borrar_ni_editar_columnas_ajenas(db_session, datos):
    real = datos["real"]
    with como_rol(db_session, APP_ROLE):
        assert_denegado(db_session, "DELETE FROM quotes WHERE id = :i", {"i": real.id})
        assert_denegado(db_session, "UPDATE quotes SET is_demo = true WHERE id = :i", {"i": real.id})
        assert_denegado(db_session, "UPDATE quotes SET email = 'x@example.com' WHERE id = :i", {"i": real.id})
        assert_denegado(db_session, "UPDATE users SET role = 'admin'")
        assert_denegado(db_session, "SELECT * FROM alembic_version")


def test_la_app_trabaja_con_filas_reales(db_session, datos):
    real, admin = datos["real"], datos["admin"]
    with como_rol(db_session, APP_ROLE):
        db_session.execute(update(Quote).where(Quote.id == real.id).values(status="closed"))
        db_session.add(QuoteNote(quote_id=real.id, author_id=admin.id, body="ok"))
        db_session.add(QuoteStatusChange(
            quote_id=real.id, from_status="contacted", to_status="closed", changed_by=admin.id
        ))
        # Lo que hace el formulario público
        db_session.add(Quote(
            name="Formulario Público", email="form@example.com", phone="212-555-0199",
            service="standard", home_size="2-bed", preferred_date=func.current_date(),
        ))
        db_session.flush()
        # Las IDENTITY de notas e historial no necesitan permiso sobre su secuencia
        assert db_session.scalar(select(func.count()).select_from(QuoteNote)) == 2
        assert db_session.scalar(text("SELECT nextval('quotes_id_seq')")) > 0

