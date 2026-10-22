"""La búsqueda del panel usa los índices GIN de trigramas (y no recorre toda la tabla).

Con pocas filas PostgreSQL prefiere, con razón, un recorrido secuencial; por eso se cargan
filas sintéticas dentro de la transacción de la prueba (se revierten al final) y se actualizan
las estadísticas con ANALYZE antes de pedir el plan.
"""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Quote, User
from app.schemas.quote import QuoteListParams
from app.services.quotes import list_conditions

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


def plan(session: Session, q: str) -> str:
    """EXPLAIN de la consulta exacta que arma el servicio para la lista."""
    stmt = select(func.count()).select_from(Quote).where(
        *list_conditions(User(role="admin"), QuoteListParams(q=q))
    )
    connection = session.connection()
    compiled = stmt.compile(connection)
    rows = connection.exec_driver_sql("EXPLAIN " + compiled.string, compiled.params)
    return "\n".join(rows.scalars())


def test_busqueda_por_texto_usa_los_indices_de_nombre_y_email(db_session, volumen):
    texto = plan(db_session, "4b1c2a9f")
    assert "ix_quotes_name_trgm" in texto
    assert "ix_quotes_email_trgm" in texto
    # Tiene dígitos pero no parece un teléfono: no se busca en él
    assert "ix_quotes_phone_digits_trgm" not in texto
    assert "Seq Scan" not in texto


def test_busqueda_con_digitos_usa_tambien_el_indice_del_telefono(db_session, volumen):
    texto = plan(db_session, "555-0123")
    assert "ix_quotes_name_trgm" in texto
    assert "ix_quotes_email_trgm" in texto
    assert "ix_quotes_phone_digits_trgm" in texto
    assert "BitmapOr" in texto
    assert "Seq Scan" not in texto
