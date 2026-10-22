"""Hash de contraseñas (Argon2id, con pwdlib) y tokens de acceso JWT (con PyJWT)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.config import Settings

JWT_ALGORITHM = "HS256"

# recommended(): Argon2id con los parámetros por defecto de argon2-cffi (64 MiB de memoria,
# 3 pasadas). El hash resultante guarda algoritmo, parámetros y sal: "$argon2id$v=19$m=65536,..."
password_hash = PasswordHash.recommended()

# Hash de una contraseña que nadie conoce. Cuando el email no existe se verifica contra él,
# para que la respuesta tarde lo mismo y no revele qué emails tienen cuenta.
_DUMMY_HASH = password_hash.hash("no-es-la-contraseña-de-nadie")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """Devuelve (si la contraseña es correcta, hash nuevo o None).

    El hash nuevo llega solo si el guardado usa parámetros viejos (p. ej. si algún día se
    sube el costo de Argon2): quien llama debe guardarlo en lugar del anterior.
    """
    try:
        return password_hash.verify_and_update(password, hashed)
    except UnknownHashError:
        # Un hash que no es de ningún algoritmo conocido (p. ej. el "!" del usuario demo)
        # nunca coincide. Igual se gasta el mismo tiempo que con un hash real.
        burn_password_check(password)
        return False, None


def burn_password_check(password: str) -> None:
    """Gasta el mismo tiempo que una verificación real (para usuarios inexistentes)."""
    password_hash.verify(password, _DUMMY_HASH)


class InvalidTokenError(Exception):
    """El token no sirve: mal formado, firma incorrecta, vencido o le faltan datos."""


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: str


def create_access_token(
    user_id: int, role: str, settings: Settings, now: datetime | None = None
) -> str:
    now = now or datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # el estándar exige que "sub" sea texto
        "role": role,  # solo para que el panel pinte la interfaz; la API usa el rol de la base
        "iat": now,  # emitido en (PyJWT convierte datetime a segundos Unix)
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),  # vence en
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            # Lista fija de algoritmos: sin ella, un token con "alg": "none" (sin firma)
            # o con otro algoritmo podría colarse. PyJWT valida firma y "exp" por su cuenta.
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "role", "iat", "exp"]},
        )
        return TokenClaims(user_id=int(payload["sub"]), role=str(payload["role"]))
    except (jwt.PyJWTError, ValueError) as exc:
        # ValueError: "sub" que no es un número
        raise InvalidTokenError from exc
