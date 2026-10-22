from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    literal_column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    EMAIL_CHECK,
    EMAIL_MAX,
    HOME_SIZES,
    MESSAGE_MAX,
    NAME_MAX,
    NAME_MIN,
    PHONE_MAX,
    PHONE_MIN_DIGITS,
    QUOTE_STATUSES,
    SERVICES,
    Base,
    sql_in,
)

if TYPE_CHECKING:
    from app.models.note import QuoteNote
    from app.models.status_change import QuoteStatusChange


class Quote(Base):
    """Una solicitud de cotización enviada desde la landing (o ficticia, si is_demo)."""

    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint(f"char_length(btrim(name)) >= {NAME_MIN}", name="name_longitud"),
        CheckConstraint(EMAIL_CHECK.format(column="email"), name="email_formato"),
        # Al menos 10 dígitos, ignorando espacios, guiones y paréntesis
        CheckConstraint(
            rf"char_length(regexp_replace(phone, '\D', '', 'g')) >= {PHONE_MIN_DIGITS}",
            name="phone_digitos",
        ),
        CheckConstraint(sql_in("service", SERVICES), name="service_valido"),
        CheckConstraint(sql_in("home_size", HOME_SIZES), name="home_size_valido"),
        CheckConstraint(sql_in("status", QUOTE_STATUSES), name="status_valido"),
        # Destino de las FK compuestas (quote_id, is_demo) de notas e historial
        UniqueConstraint("id", "is_demo"),
        # Búsqueda ILIKE '%texto%' con trigramas (extensión pg_trgm)
        Index("ix_quotes_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("ix_quotes_email_trgm", "email", postgresql_using="gin", postgresql_ops={"email": "gin_trgm_ops"}),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX))
    email: Mapped[str] = mapped_column(String(EMAIL_MAX))
    phone: Mapped[str] = mapped_column(String(PHONE_MAX))
    service: Mapped[str] = mapped_column(Text)
    home_size: Mapped[str] = mapped_column(Text)
    preferred_date: Mapped[date]
    message: Mapped[str | None] = mapped_column(String(MESSAGE_MAX))
    # default (Python) y server_default (SQL): el valor se conoce en el objeto antes de
    # guardarlo, y la base lo garantiza aunque alguien inserte con SQL directo
    status: Mapped[str] = mapped_column(Text, default="new", server_default="new")
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # passive_deletes: al borrar una cotización, el ORM no carga sus hijos para borrarlos uno
    # por uno; deja que lo haga el ON DELETE CASCADE de la base (una sola sentencia)
    notes: Mapped[list["QuoteNote"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="[QuoteNote.created_at, QuoteNote.id]",
    )
    status_changes: Mapped[list["QuoteStatusChange"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="[QuoteStatusChange.changed_at, QuoteStatusChange.id]",
    )


# Índices compuestos: el orden de las columnas sigue al de las consultas del panel.
# is_demo va primero porque toda consulta filtra por él.
Index("ix_quotes_is_demo_status_created_at", Quote.is_demo, Quote.status, Quote.created_at.desc())
Index("ix_quotes_is_demo_created_at", Quote.is_demo, Quote.created_at)

# Solo los dígitos del teléfono: "(212) 555-0100" -> "2125550100". La búsqueda compara contra
# esta expresión, y PostgreSQL solo usa un índice de expresión si la consulta escribe
# EXACTAMENTE la misma; por eso se define una vez y la usan el índice y services/quotes.py.
# Las constantes van como literales SQL y no como parámetros ($1, $2...): con parámetros, un
# plan genérico de una sentencia preparada ya no reconocería la expresión del índice.
PHONE_DIGITS = func.regexp_replace(
    Quote.phone, literal_column(r"'\D'"), literal_column("''"), literal_column("'g'")
)
# GIN de trigramas sobre los dígitos: sin él, el OR de la búsqueda (nombre, email o teléfono)
# obliga a recorrer toda la tabla y tampoco se aprovechan los índices de nombre y email
Index(
    "ix_quotes_phone_digits_trgm",
    PHONE_DIGITS.label("phone_digits"),
    postgresql_using="gin",
    postgresql_ops={"phone_digits": "gin_trgm_ops"},
)
