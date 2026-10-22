"""Esquemas Pydantic de las cotizaciones (lo que entra y sale por la API)."""

import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import get_settings
from app.models.base import (
    EMAIL_MAX,
    HOME_SIZES,
    MESSAGE_MAX,
    NAME_MAX,
    NAME_MIN,
    PHONE_MAX,
    PHONE_MIN_DIGITS,
    SERVICES,
)

# Hasta cuántos días en el futuro se acepta la fecha preferida
MAX_DAYS_AHEAD = 365
# Teléfono: solo dígitos, espacios y los símbolos habituales: +1 (212) 555-0100, 212.555.0100
PHONE_CHARS = re.compile(r"^[0-9+().\- ]+$")


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
    created_at: datetime
