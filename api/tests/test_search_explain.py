"""Plan de la búsqueda del panel: con RLS recorre la tabla (Seq Scan); sin RLS usa los índices.

Trade-off aceptado en la fase 6 (DESIGN §2.4 y §3.4): ILIKE y LIKE no son "leakproof", así que
con RLS PostgreSQL los evalúa DESPUÉS de la política y no puede usarlos como condición de un
índice. La API corre con RLS (fernwick_app / fernwick_demo), así que su búsqueda es un Seq Scan.
Las pruebas "sin RLS" (como dueño) muestran que los índices siguen sirviendo y que la causa del
Seq Scan es RLS, no la consulta.

Con pocas filas PostgreSQL prefiere, con razón, un recorrido secuencial; por eso se cargan
filas sintéticas dentro de la transacción de la prueba (se revierten al final) y se actualizan
las estadísticas con ANALYZE antes de pedir el plan.
"""

import re
from contextlib import nullcontext

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import APP_ROLE
from app.models import Quote, User
from app.schemas.quote import QuoteListParams
from app.services.quotes import list_conditions
from tests.helpers import como_rol

FILAS = 20_000


@pytest.fixture
def volumen(db_session: Session) -> None:
    # md5(i) da textos distintos y "aleatorios" en cada fila; el 10 % son demo
    db_session.execute(
        text(
            """
            INSERT INTO quotes (name, email, phone, service, home_size, preferred_date, is_demo)
            SELECT 'Cliente ' || md5(i::text),
                   'c' || md5(i::text || 'e') || '@example.com',
                   '(' || lpad((i % 1000)::text, 3, '0') || ') '
                       || lpad(((i * 7919) % 10000000)::text, 7, '0'),
                   'standard', '2-bed', current_date, i % 10 = 0
            FROM generate_series(1, :filas) AS i
            """
        ),
        {"filas": FILAS},
    )
    # Los índices GIN guardan las inserciones nuevas en una "lista pendiente" (fastupdate) que
    # luego vacía autovacuum. Recién insertadas, el planificador ve esa lista y estima el índice
    # como caro (elige Seq Scan). gin_clean_pending_list hace aquí lo que en producción haría
    # autovacuum, para medir el plan en condiciones normales.
    for index in ("ix_quotes_name_trgm", "ix_quotes_email_trgm", "ix_quotes_phone_digits_trgm"):
        db_session.execute(text("SELECT gin_clean_pending_list(CAST(:i AS regclass))"), {"i": index})
    db_session.execute(text("ANALYZE quotes"))


def plan(session: Session, q: str, role: str | None = None) -> str:
    """EXPLAIN de la consulta exacta que arma el servicio para la lista.

    role: None = como el dueño (salta RLS); APP_ROLE = como corre la API del admin.
    """
    stmt = select(func.count()).select_from(Quote).where(
        *list_conditions(User(role="admin"), QuoteListParams(q=q))
    )
    connection = session.connection()
    compiled = stmt.compile(connection)
    with como_rol(session, role) if role else nullcontext():
        rows = connection.exec_driver_sql("EXPLAIN " + compiled.string, compiled.params)
        return "\n".join(rows.scalars())


@pytest.mark.parametrize("q", ["4b1c2a9f", "555-0123"])
def test_con_rls_la_busqueda_recorre_la_tabla(db_session, volumen, q):
    texto = plan(db_session, q, APP_ROLE)
    assert "Seq Scan on quotes" in texto
    assert "_trgm" not in texto
    # La política (NOT is_demo) va primero en el filtro; la búsqueda, después
    assert re.search(r"Filter: \(\(NOT is_demo\).*~~\*", texto)


def test_la_causa_es_que_like_no_es_leakproof(db_session):
    # Solo las funciones LEAKPROOF pueden evaluarse antes que la política de RLS (y así usar
    # un índice): las de LIKE/ILIKE no lo son, y la de "=" sí.
    leakproof = dict(db_session.execute(text(
        "SELECT proname, proleakproof FROM pg_proc WHERE proname IN ('texticlike', 'textlike', 'texteq')"
    )).all())
    assert leakproof == {"texticlike": False, "textlike": False, "texteq": True}


def test_sin_rls_la_busqueda_por_texto_usa_los_indices_de_nombre_y_email(db_session, volumen):
    texto = plan(db_session, "4b1c2a9f")
    assert "ix_quotes_name_trgm" in texto
    assert "ix_quotes_email_trgm" in texto
    # Tiene dígitos pero no parece un teléfono: no se busca en él
    assert "ix_quotes_phone_digits_trgm" not in texto
    assert "Seq Scan" not in texto


def test_sin_rls_la_busqueda_con_digitos_usa_tambien_el_indice_del_telefono(db_session, volumen):
    texto = plan(db_session, "555-0123")
    assert "ix_quotes_name_trgm" in texto
    assert "ix_quotes_email_trgm" in texto
    assert "ix_quotes_phone_digits_trgm" in texto
    assert "BitmapOr" in texto
    assert "Seq Scan" not in texto
