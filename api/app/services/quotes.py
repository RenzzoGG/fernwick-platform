"""Lógica de negocio de las cotizaciones.

Aislamiento demo: toda función que lee o escribe cotizaciones para el panel recibe al
usuario (`viewer`) como argumento obligatorio y filtra con `_visible_to(viewer)`. Así ninguna
ruta puede pedir filas "sin filtro": el filtro no vive en los routers, vive aquí.
"""

from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select, text
from sqlalchemy.orm import Session

from app.models import Quote, User
from app.models.quote import PHONE_DIGITS
from app.schemas.quote import PublicQuoteCreate, QuoteListParams

# Mínimo de dígitos para buscar también en el teléfono (con menos no hay trigramas que usar)
PHONE_SEARCH_MIN_DIGITS = 3

# Órdenes permitidos -> columnas. El id desempata: sin él, dos filas con la misma fecha
# podrían intercambiarse entre consultas y aparecer repetidas o saltarse al paginar.
SORTS = {
    "created_at": (Quote.created_at.asc(), Quote.id.asc()),
    "-created_at": (Quote.created_at.desc(), Quote.id.desc()),
    "preferred_date": (Quote.preferred_date.asc(), Quote.id.asc()),
    "-preferred_date": (Quote.preferred_date.desc(), Quote.id.desc()),
}


def scope_is_demo(viewer: User) -> bool:
    """Qué filas ve un usuario: el demo solo las ficticias, el admin solo las reales.

    Falla cerrado: cualquier rol que no sea "admin" se trata como demo (solo datos ficticios).
    """
    return viewer.role != "admin"


def _visible_to(viewer: User) -> ColumnElement[bool]:
    return Quote.is_demo == scope_is_demo(viewer)


def _escape_like(value: str) -> str:
    # En LIKE, % y _ son comodines y \ es el carácter de escape: se escapan para que
    # buscar "100%" encuentre el texto "100%" y no "100 seguido de cualquier cosa"
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_condition(q: str) -> ColumnElement[bool]:
    """name ILIKE '%q%' OR email ILIKE '%q%' [OR dígitos(phone) LIKE '%dígitos%'].

    Cada rama usa su índice GIN de trigramas y PostgreSQL las combina (BitmapOr). El texto
    va siempre como parámetro enlazado de SQLAlchemy, nunca concatenado al SQL.
    """
    pattern = f"%{_escape_like(q)}%"
    branches = [
        Quote.name.ilike(pattern, escape="\\"),
        Quote.email.ilike(pattern, escape="\\"),
    ]
    digits = "".join(char for char in q if char.isdigit())
    # Solo si hay dígitos suficientes: con "ana" los dígitos serían "" y LIKE '%%' encontraría todo
    if len(digits) >= PHONE_SEARCH_MIN_DIGITS:
        branches.append(PHONE_DIGITS.like(f"%{digits}%"))
    return or_(*branches)


def list_quotes(
    session: Session, viewer: User, params: QuoteListParams
) -> tuple[list[Quote], int]:
    """Una página de cotizaciones visibles para `viewer`, y el total que cumple los filtros."""
    conditions = [_visible_to(viewer)]
    if params.status is not None:
        conditions.append(Quote.status == params.status)
    if params.q is not None:
        conditions.append(_search_condition(params.q))

    total = session.scalar(select(func.count()).select_from(Quote).where(*conditions))
    items = session.scalars(
        select(Quote)
        .where(*conditions)
        .order_by(*SORTS[params.sort])
        .limit(params.page_size)
        .offset((params.page - 1) * params.page_size)
    ).all()
    return list(items), total


def create_public_quote(session: Session, data: PublicQuoteCreate) -> Quote:
    """Guarda una cotización enviada desde el formulario público."""
    quote = Quote(
        # Campos copiados uno por uno (no **data): si el esquema crece, nada llega a la base por accidente
        name=data.name,
        email=data.email,
        phone=data.phone,
        service=data.service,
        home_size=data.home_size,
        preferred_date=data.preferred_date,
        message=data.message,
        # Los fija el servidor, nunca el cliente
        status="new",
        is_demo=False,
    )
    session.add(quote)
    session.commit()
    # refresh: lee de la base los valores que asignó PostgreSQL (id, created_at)
    session.refresh(quote)
    return quote


def fake_quote_receipt(session: Session) -> tuple[int, datetime]:
    """Id y fecha para responder a un bot (honeypot) sin guardar nada.

    El id sale de la misma secuencia de la tabla: nextval consume un número igual que lo
    haría un INSERT (los huecos en los ids son normales), así la respuesta falsa es
    indistinguible de una real. No se inserta ninguna fila.
    """
    row = session.execute(
        text("SELECT nextval(pg_get_serial_sequence('quotes', 'id')), now()")
    ).one()
    # Cierra la transacción que abrió la consulta (nextval no se revierte con rollback)
    session.commit()
    return row[0], row[1]
