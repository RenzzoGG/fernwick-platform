"""Esquemas Pydantic de las cotizaciones (lo que entra y sale por la API)."""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import get_settings
from app.models import Quote, QuoteNote, QuoteStatusChange
from app.models.base import (
    EMAIL_MAX,
    HOME_SIZES,
    MESSAGE_MAX,
    NAME_MAX,
    NAME_MIN,
    NOTE_BODY_MAX,
    PHONE_MAX,
    PHONE_MIN_DIGITS,
    QUOTE_STATUSES,
    SERVICES,
)

# Hasta cuántos días en el futuro se acepta la fecha preferida
MAX_DAYS_AHEAD = 365
# Teléfono: solo dígitos, espacios y los símbolos habituales: +1 (212) 555-0100, 212.555.0100
PHONE_CHARS = re.compile(r"^[0-9+().\- ]+$")

# Lista del panel: tamaño de página máximo y página máxima (evita OFFSET gigantes)
PAGE_SIZE_MAX = 100
PAGE_MAX = 10_000
SEARCH_MIN = 2
SEARCH_MAX = 100

QuoteStatus = Literal[*QUOTE_STATUSES]
# Lista cerrada de órdenes permitidos: "-" = descendente. Cualquier otro valor da 422.
QuoteSort = Literal["created_at", "-created_at", "preferred_date", "-preferred_date"]


def _a_utc(value: datetime) -> datetime:
    # PostgreSQL devuelve la hora en la zona de la sesión; se responde siempre en UTC ("Z")
    return value.astimezone(timezone.utc)


# Tipo para toda fecha-hora de las respuestas: Annotated agrega el validador al tipo
UtcDatetime = Annotated[datetime, AfterValidator(_a_utc)]


def business_today() -> date:
    """La fecha de hoy en la zona del negocio (no la del servidor, que en Railway es UTC)."""
    return datetime.now(ZoneInfo(get_settings().business_timezone)).date()


class PublicQuoteCreate(BaseModel):
    """Lo que envía el formulario de la landing."""

    # extra="forbid": cualquier campo no declarado (status, is_demo, id, created_at...) da 422.
    # str_strip_whitespace: recorta espacios al inicio y al final antes de validar longitudes.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    email: EmailStr
    phone: str = Field(max_length=PHONE_MAX)
    # Literal[*TUPLA]: solo se aceptan los valores de base.py (los mismos de los CHECK)
    service: Literal[*SERVICES]
    home_size: Literal[*HOME_SIZES]
    preferred_date: date
    message: str | None = Field(default=None, max_length=MESSAGE_MAX)
    # Honeypot: campo oculto en la landing. Una persona lo deja vacío; muchos bots lo llenan.
    website: str | None = None

    @field_validator("email")
    @classmethod
    def email_longitud(cls, value: str) -> str:
        if len(value) > EMAIL_MAX:
            raise ValueError(f"Email must be at most {EMAIL_MAX} characters")
        return value

    @field_validator("phone")
    @classmethod
    def phone_valido(cls, value: str) -> str:
        if not PHONE_CHARS.match(value):
            raise ValueError("Phone may only contain digits, spaces and + ( ) - .")
        if sum(char.isdigit() for char in value) < PHONE_MIN_DIGITS:
            raise ValueError(f"Phone must have at least {PHONE_MIN_DIGITS} digits")
        return value

    @field_validator("preferred_date")
    @classmethod
    def fecha_valida(cls, value: date) -> date:
        today = business_today()
        if value < today:
            raise ValueError("Preferred date cannot be in the past")
        if value > today + timedelta(days=MAX_DAYS_AHEAD):
            raise ValueError(f"Preferred date must be within the next {MAX_DAYS_AHEAD} days")
        return value

    @field_validator("message")
    @classmethod
    def mensaje_vacio_es_none(cls, value: str | None) -> str | None:
        # Un textarea vacío llega como "": se guarda como NULL (no hay mensaje)
        return value or None


class PublicQuoteCreated(BaseModel):
    """Respuesta del formulario: solo lo justo, el visitante ya conoce sus datos."""

    # from_attributes: permite construirlo directamente desde el objeto Quote de SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: UtcDatetime


# --- Panel de administración ---


class QuoteListParams(BaseModel):
    """Parámetros de GET /v1/quotes (van en la URL: ?status=new&q=ana&page=2)."""

    # extra="forbid": un parámetro desconocido (p. ej. ?order_by=password_hash) da 422
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: QuoteStatus | None = None
    q: str | None = Field(default=None, min_length=SEARCH_MIN, max_length=SEARCH_MAX)
    page: int = Field(default=1, ge=1, le=PAGE_MAX)
    page_size: int = Field(default=20, ge=1, le=PAGE_SIZE_MAX)
    sort: QuoteSort = "-created_at"

    @field_validator("q", mode="before")
    @classmethod
    def busqueda_vacia_es_none(cls, value: str | None) -> str | None:
        # El panel puede mandar ?q= con la caja de búsqueda vacía: equivale a no buscar
        if isinstance(value, str) and not value.strip():
            return None
        return value


class QuoteSummary(BaseModel):
    """Una fila de la lista del panel."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str
    service: str
    home_size: str
    preferred_date: date
    status: str
    created_at: UtcDatetime


class QuotePage(BaseModel):
    items: list[QuoteSummary]
    total: int  # filas que cumplen los filtros, en todas las páginas
    page: int
    page_size: int


class NoteOut(BaseModel):
    id: int
    body: str
    author_email: str | None  # None si el autor fue eliminado
    created_at: UtcDatetime

    @classmethod
    def from_note(cls, note: QuoteNote) -> "NoteOut":
        return cls(
            id=note.id,
            body=note.body,
            author_email=note.author.email if note.author else None,
            created_at=note.created_at,
        )


class StatusChangeOut(BaseModel):
    from_status: str
    to_status: str
    changed_by_email: str | None
    changed_at: UtcDatetime

    @classmethod
    def from_change(cls, change: QuoteStatusChange) -> "StatusChangeOut":
        return cls(
            from_status=change.from_status,
            to_status=change.to_status,
            changed_by_email=change.changed_by_user.email if change.changed_by_user else None,
            changed_at=change.changed_at,
        )


class QuoteDetail(QuoteSummary):
    """Detalle de una cotización: los datos de la lista más mensaje, notas e historial."""

    message: str | None
    updated_at: UtcDatetime
    notes: list[NoteOut]
    status_history: list[StatusChangeOut]

    @classmethod
    def from_quote(cls, quote: Quote) -> "QuoteDetail":
        summary = QuoteSummary.model_validate(quote)
        return cls(
            **summary.model_dump(),
            message=quote.message,
            updated_at=quote.updated_at,
            notes=[NoteOut.from_note(note) for note in quote.notes],
            status_history=[StatusChangeOut.from_change(c) for c in quote.status_changes],
        )


class StatusUpdate(BaseModel):
    """Cuerpo de PATCH /v1/quotes/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: QuoteStatus


class NoteCreate(BaseModel):
    """Cuerpo de POST /v1/quotes/{id}/notes."""

    # Se recortan los espacios: una nota de puros espacios queda vacía y da 422
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=NOTE_BODY_MAX)
