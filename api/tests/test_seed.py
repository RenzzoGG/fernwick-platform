from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.cli import DEMO_EMAIL, DEMO_QUOTE_COUNT, SERVICE_WEIGHTS, seed_demo
from app.models import Quote, QuoteNote, QuoteStatusChange, User
from app.models.base import SERVICES
from tests.test_models import make_quote

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def contar(session, model, *where) -> int:
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_seed_es_idempotente_y_no_toca_datos_reales(db_session):
    real = make_quote(name="Cliente Real")
    db_session.add(real)
    db_session.flush()

    primera = seed_demo(db_session, now=NOW)
    conteos_1 = [contar(db_session, m) for m in (User, Quote, QuoteNote, QuoteStatusChange)]
    segunda = seed_demo(db_session, now=NOW)
    conteos_2 = [contar(db_session, m) for m in (User, Quote, QuoteNote, QuoteStatusChange)]

    assert primera == segunda
    assert conteos_1 == conteos_2
    assert contar(db_session, User, func.lower(User.email) == DEMO_EMAIL) == 1
    assert contar(db_session, Quote, Quote.is_demo) == DEMO_QUOTE_COUNT
    # La cotización real sigue ahí, intacta
    assert db_session.get(Quote, real.id).name == "Cliente Real"
    assert contar(db_session, Quote, ~Quote.is_demo) == 1


def test_seed_genera_historial_coherente_y_fechas_recientes(db_session):
    seed_demo(db_session, now=NOW)
    quotes = db_session.scalars(select(Quote).where(Quote.is_demo)).all()

    for quote in quotes:
        cambios = quote.status_changes
        # El último cambio lleva al estado actual (las "new" no tienen cambios)
        assert (cambios[-1].to_status if cambios else "new") == quote.status
        # Cada cambio parte del estado al que llegó el anterior
        for anterior, siguiente in zip(cambios, cambios[1:]):
            assert anterior.to_status == siguiente.from_status
        assert all(c.is_demo for c in cambios) and all(n.is_demo for n in quote.notes)
        assert quote.created_at <= NOW and quote.preferred_date > quote.created_at.date()

    # Hay variedad para el tablero: varios estados y cotizaciones en los últimos 30 días
    assert len({q.status for q in quotes}) == 4
    assert any(q.created_at >= NOW - timedelta(days=30) for q in quotes)


def test_seed_reparte_servicios_de_forma_realista(db_session):
    seed_demo(db_session, now=NOW)
    quotes = db_session.scalars(select(Quote).where(Quote.is_demo)).all()
    por_servicio = Counter(q.service for q in quotes)

    # Proporción exacta de SERVICE_WEIGHTS: 35/25/20/12/5/3 % de 40
    assert por_servicio == {
        "standard": 14, "recurring": 10, "deep": 8, "move": 5, "office": 2, "post-renovation": 1,
    }
    # Tamaño coherente con el servicio
    for quote in quotes:
        assert (quote.home_size == "office") == (quote.service == "office")


def test_todo_servicio_tiene_peso_en_el_seed():
    assert set(SERVICE_WEIGHTS) == set(SERVICES)
