from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Quote, QuoteNote, QuoteStatusChange, User


def make_quote(**overrides) -> Quote:
    data = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "(212) 555-0100",
        "service": "standard",
        "home_size": "2-bed",
        "preferred_date": date(2026, 11, 15),
    }
    return Quote(**(data | overrides))


def assert_rechazado(session, obj, constraint: str) -> None:
    """Comprueba que la base rechaza el objeto, y que lo hace la restricción esperada."""
    session.add(obj)
    with pytest.raises(IntegrityError) as error:
        session.flush()
    # psycopg expone el nombre de la restricción que falló (gracias a la convención de nombres)
    assert error.value.orig.diag.constraint_name == constraint
    session.rollback()


# --- Valores por defecto ---


def test_cotizacion_valida_recibe_valores_por_defecto(db_session):
    quote = make_quote()
    db_session.add(quote)
    db_session.flush()
    db_session.refresh(quote)

    assert quote.id is not None
    assert quote.status == "new"
    assert quote.is_demo is False
    assert quote.created_at is not None
    assert quote.created_at.tzinfo is not None  # timestamptz: instante con zona


# --- Restricciones CHECK y UNIQUE ---


@pytest.mark.parametrize(
    ("campo", "valor", "restriccion"),
    [
        ("status", "pending", "ck_quotes_status_valido"),
        ("service", "laundry", "ck_quotes_service_valido"),
        ("home_size", "5-bed", "ck_quotes_home_size_valido"),
        ("email", "", "ck_quotes_email_formato"),
        ("email", "sin-arroba.com", "ck_quotes_email_formato"),
        ("phone", "555-0100", "ck_quotes_phone_digitos"),
        ("name", "A", "ck_quotes_name_longitud"),
        ("name", "   ", "ck_quotes_name_longitud"),
    ],
)
def test_cotizacion_invalida_es_rechazada(db_session, campo, valor, restriccion):
    assert_rechazado(db_session, make_quote(**{campo: valor}), restriccion)


def test_email_nulo_es_rechazado(db_session):
    db_session.add(make_quote(email=None))
    with pytest.raises(IntegrityError) as error:
        db_session.flush()
    assert error.value.orig.sqlstate == "23502"  # not_null_violation


def test_rol_de_usuario_invalido(db_session):
    user = User(email="root@example.com", password_hash="x", role="superadmin")
    assert_rechazado(db_session, user, "ck_users_role_valido")


def test_email_de_usuario_unico_sin_distinguir_mayusculas(db_session):
    db_session.add(User(email="admin@example.com", password_hash="x", role="admin"))
    db_session.flush()
    duplicado = User(email="Admin@Example.com", password_hash="x", role="admin")
    assert_rechazado(db_session, duplicado, "uq_users_email_lower")


def test_nota_vacia_es_rechazada(db_session):
    quote = make_quote()
    quote.notes.append(QuoteNote(body=""))
    assert_rechazado(db_session, quote, "ck_quote_notes_body_longitud")


def test_cambio_al_mismo_estado_es_rechazado(db_session):
    quote = make_quote()
    quote.status_changes.append(QuoteStatusChange(from_status="new", to_status="new"))
    assert_rechazado(db_session, quote, "ck_quote_status_changes_estado_distinto")


# --- Relaciones y claves foráneas ---


def test_nota_hereda_quote_id_e_is_demo_de_su_cotizacion(db_session):
    quote = make_quote(is_demo=True)
    note = QuoteNote(body="Cliente contactado")
    quote.notes.append(note)
    db_session.add(quote)
    db_session.flush()

    # El ORM copió las dos columnas de la FK compuesta desde la cotización
    assert note.quote_id == quote.id
    assert note.is_demo is True
    assert note.quote is quote


def test_fk_compuesta_impide_mezclar_datos_demo_y_reales(db_session):
    real = make_quote(is_demo=False)
    db_session.add(real)
    db_session.flush()

    nota_demo = QuoteNote(quote_id=real.id, is_demo=True, body="no debería poder existir")
    assert_rechazado(db_session, nota_demo, "fk_quote_notes_quote_id_is_demo_quotes")


def test_fk_rechaza_cotizacion_inexistente(db_session):
    huerfana = QuoteStatusChange(quote_id=999_999, from_status="new", to_status="contacted")
    assert_rechazado(db_session, huerfana, "fk_quote_status_changes_quote_id_is_demo_quotes")


def test_borrar_cotizacion_borra_notas_e_historial_en_cascada(db_session):
    quote = make_quote()
    quote.notes.append(QuoteNote(body="nota"))
    quote.status_changes.append(QuoteStatusChange(from_status="new", to_status="contacted"))
    db_session.add(quote)
    db_session.flush()
    quote_id = quote.id

    db_session.delete(quote)
    db_session.flush()

    notas = db_session.scalar(select(func.count()).where(QuoteNote.quote_id == quote_id))
    cambios = db_session.scalar(select(func.count()).where(QuoteStatusChange.quote_id == quote_id))
    assert (notas, cambios) == (0, 0)


def test_borrar_usuario_conserva_sus_notas_sin_autor(db_session):
    admin = User(email="admin@example.com", password_hash="x", role="admin")
    quote = make_quote()
    note = QuoteNote(body="nota", author=admin)
    quote.notes.append(note)
    db_session.add_all([admin, quote])
    db_session.flush()

    db_session.delete(admin)
    db_session.flush()
    db_session.refresh(note)

    # ON DELETE SET NULL: la nota sigue existiendo, sin autor
    assert note.author_id is None
