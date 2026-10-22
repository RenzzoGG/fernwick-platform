"""Base declarativa común a todos los modelos, y valores permitidos de las columnas tipo "lista"."""

from datetime import datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase

# Convención de nombres: SQLAlchemy nombra así cada restricción e índice que no tenga nombre
# explícito. Con nombres estables, una migración futura puede borrar o cambiar una restricción
# por su nombre (si PostgreSQL los inventara, cada base podría tener nombres distintos).
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Toda columna anotada como datetime se guarda como timestamptz (instante absoluto)
    type_annotation_map = {datetime: DateTime(timezone=True)}


# Valores permitidos. Son la única fuente de verdad: de aquí salen los CHECK de la base
# y, en las fases siguientes, la validación de Pydantic.
USER_ROLES = ("admin", "demo")
QUOTE_STATUSES = ("new", "contacted", "scheduled", "closed")
# Iguales a los <option value> del formulario de la landing
SERVICES = ("standard", "recurring", "deep", "move", "office", "post-renovation")
HOME_SIZES = ("studio", "2-bed", "3-bed", "4-bed", "office")

# Límites de longitud de las cotizaciones: los usan las columnas/CHECK de la base y Pydantic
NAME_MIN = 2
NAME_MAX = 100
EMAIL_MAX = 254  # máximo práctico de una dirección de email (RFC 5321)
PHONE_MAX = 30
PHONE_MIN_DIGITS = 10
MESSAGE_MAX = 500
# Notas internas del panel
NOTE_BODY_MAX = 2000

# Formato mínimo de email: algo@algo, sin espacios. Rechaza también el texto vacío.
# La validación completa (dominio, etc.) la hará Pydantic; la base solo impide basura evidente.
EMAIL_CHECK = "{column} ~ '^[^@[:space:]]+@[^@[:space:]]+$'"


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Arma la condición de un CHECK: `status IN ('new', 'contacted', ...)`."""
    options = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({options})"
