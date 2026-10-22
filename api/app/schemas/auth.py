"""Esquemas Pydantic de la autenticación."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.base import EMAIL_MAX, USER_ROLES
from app.services.auth import PASSWORD_MAX

Role = Literal[*USER_ROLES]


class LoginRequest(BaseModel):
    # Sin str_strip_whitespace a nivel de modelo: los espacios de la contraseña son parte de ella
    model_config = ConfigDict(extra="forbid")

    # str y no EmailStr: un email mal escrito da el mismo 401 que uno inexistente
    email: str = Field(min_length=1, max_length=EMAIL_MAX)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)

    @field_validator("email")
    @classmethod
    def recortar_email(cls, value: str) -> str:
        return value.strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # segundos hasta que vence el token
    role: Role  # para que el panel sepa si mostrar el modo demo


class CurrentUser(BaseModel):
    # from_attributes: se puede crear a partir de un objeto User de SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
