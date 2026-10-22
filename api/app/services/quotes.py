"""Lógica de negocio de las cotizaciones.

Aislamiento demo: toda función que lee o escribe cotizaciones para el panel recibe al
usuario (`viewer`) como argumento obligatorio y filtra con `_visible_to(viewer)`. Así ninguna
ruta puede pedir filas "sin filtro": el filtro no vive en los routers, vive aquí.
"""

from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import Quote, QuoteNote, QuoteStatusChange, User
from app.models.quote import PHONE_DIGITS
from app.schemas.quote import PHONE_CHARS, PublicQuoteCreate, QuoteListParams

class StatusUnchangedError(Exception):
    """Se pidió cambiar al estado que la cotización ya tiene (la API responde 409)."""


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
    # Solo si el texto parece un teléfono ("555-0123", "(212) 555"): con "ana" los dígitos
    # serían "" y LIKE '%%' encontraría todo, y con "ab12c3" se buscaría un "123" sin sentido
    if PHONE_CHARS.match(q) and len(digits) >= PHONE_SEARCH_MIN_DIGITS:
        branches.append(PHONE_DIGITS.like(f"%{digits}%"))
    return or_(*branches)


def list_conditions(viewer: User, params: QuoteListParams) -> list[ColumnElement[bool]]:
    """Condiciones del WHERE de la lista. El alcance del usuario va siempre, primero."""
    conditions = [_visible_to(viewer)]
    if params.status is not None:
        conditions.append(Quote.status == params.status)
    if params.q is not None:
        conditions.append(_search_condition(params.q))
    return conditions


def list_quotes(
    session: Session, viewer: User, params: QuoteListParams
) -> tuple[list[Quote], int]:
    """Una página de cotizaciones visibles para `viewer`, y el total que cumple los filtros."""
    conditions = list_conditions(viewer, params)
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


def get_quote(session: Session, viewer: User, quote_id: int) -> Quote | None:
    """La cotización con sus notas e historial, o None si no existe o no es visible.

    Para el que pregunta, "no existe" y "no es tuya" son lo mismo: así el demo no puede
    averiguar qué ids reales hay. Notas e historial comparten el is_demo de su cotización
    (lo garantiza la FK compuesta), así que no necesitan otro filtro.
    """
    return session.scalar(
        select(Quote)
        .where(Quote.id == quote_id, _visible_to(viewer))
        # populate_existing: si la cotización ya estaba en la sesión (p. ej. justo después de
        # cambiar su estado), se reemplazan sus datos y colecciones por los de la base
        .execution_options(populate_existing=True)
        # selectinload: una consulta por colección (WHERE quote_id IN ...) en vez de una por
        # fila al recorrerlas (el problema "N+1"); también trae a los autores.
        # load_only: de los autores solo id y email (lo que se muestra). El rol demo no tiene
        # permiso sobre las demás columnas de users (password_hash, role...): pedirlas daría error.
        .options(
            selectinload(Quote.notes).selectinload(QuoteNote.author).load_only(User.id, User.email),
            selectinload(Quote.status_changes)
            .selectinload(QuoteStatusChange.changed_by_user)
            .load_only(User.id, User.email),
        )
    )


def change_status(session: Session, actor: User, quote_id: int, new_status: str) -> Quote | None:
    """Cambia el estado y registra el cambio en el historial, en UNA transacción.

    Devuelve la cotización actualizada, o None si no existe o no es visible para `actor`.
    Lanza StatusUnchangedError si ya tenía ese estado (no se guarda nada).
    """
    quote = session.scalar(
        select(Quote)
        .where(Quote.id == quote_id, _visible_to(actor))
        # FOR UPDATE bloquea la fila hasta el commit: si dos admins cambian el estado a la vez,
        # el segundo espera aquí y luego lee el estado que dejó el primero
        .with_for_update()
        # Tras esperar el bloqueo hay que usar lo que dice la base, no lo que la sesión
        # tuviera en memoria de antes
        .execution_options(populate_existing=True)
    )
    if quote is None:
        return None
    if quote.status == new_status:
        session.rollback()  # termina la transacción y libera el bloqueo
        raise StatusUnchangedError

    try:
        quote.status_changes.append(
            QuoteStatusChange(
                from_status=quote.status,
                to_status=new_status,
                changed_by=actor.id,
                is_demo=quote.is_demo,  # el historial hereda el is_demo de su cotización
            )
        )
        quote.status = new_status
        # Un solo commit para el UPDATE de quotes y el INSERT del historial: o se guardan
        # los dos o ninguno
        session.commit()
    except Exception:
        session.rollback()
        raise
    return get_quote(session, actor, quote_id)


def add_note(session: Session, author: User, quote_id: int, body: str) -> QuoteNote | None:
    """Agrega una nota interna. None si la cotización no existe o no es visible para `author`."""
    quote = session.scalar(select(Quote).where(Quote.id == quote_id, _visible_to(author)))
    if quote is None:
        return None
    # La nota hereda el is_demo de su cotización (la FK compuesta lo exige)
    note = QuoteNote(quote_id=quote.id, is_demo=quote.is_demo, author_id=author.id, body=body)
    session.add(note)
    session.commit()
    session.refresh(note)  # id y created_at los asigna PostgreSQL
    return note
