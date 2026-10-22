from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import SecretStr, ValidationError

from app.config import Settings, get_settings
from app.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def settings() -> Settings:
    return get_settings()


# --- Contraseñas ---


def test_hash_es_argon2id_y_lleva_sal():
    hash1, hash2 = hash_password("una clave larga"), hash_password("una clave larga")
    assert hash1.startswith("$argon2id$")
    assert hash1 != hash2  # sal aleatoria: la misma clave da hashes distintos
    assert "una clave larga" not in hash1


def test_verifica_la_clave_correcta_y_rechaza_la_incorrecta():
    hashed = hash_password("una clave larga")
    assert verify_password("una clave larga", hashed) == (True, None)
    assert verify_password("otra clave", hashed) == (False, None)


def test_hash_invalido_del_demo_nunca_coincide():
    # El usuario demo tiene password_hash = "!": no hay contraseña que entre
    assert verify_password("!", "!") == (False, None)
    assert verify_password("", "!") == (False, None)


def test_hash_con_parametros_viejos_se_actualiza():
    # Un hash "barato" (como si los parámetros recomendados hubieran subido después)
    viejo = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash("una clave larga")
    ok, nuevo = verify_password("una clave larga", viejo)
    assert ok is True
    assert nuevo is not None and nuevo.startswith("$argon2id$v=19$m=65536")


# --- Tokens ---


def test_token_ida_y_vuelta(settings):
    token = create_access_token(42, "admin", settings)
    claims = decode_access_token(token, settings)
    assert (claims.user_id, claims.role) == (42, "admin")


def test_token_trae_sub_role_iat_exp(settings):
    ahora = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    token = create_access_token(7, "demo", settings, now=ahora)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload == {
        "sub": "7",
        "role": "demo",
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(minutes=60)).timestamp()),
    }


def test_token_vencido(settings):
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    token = create_access_token(1, "admin", settings, now=hace_dos_horas)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_firmado_con_otro_secreto(settings):
    # model_copy no valida: hay que pasar SecretStr, como haría Settings
    otro = settings.model_copy(update={"jwt_secret": SecretStr("x" * 40)})
    token = create_access_token(1, "admin", otro)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_manipulado(settings):
    # Se cambia el rol en el contenido sin volver a firmar
    header, _, firma = create_access_token(1, "demo", settings).split(".")
    falso = jwt.encode({"sub": "1", "role": "admin", "iat": 0, "exp": 9999999999}, "x" * 40)
    _, payload_falso, _ = falso.split(".")
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{payload_falso}.{firma}", settings)


def test_token_sin_firma_alg_none(settings):
    ahora = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "1", "role": "admin", "iat": ahora, "exp": ahora + timedelta(hours=1)},
        key=None,
        algorithm="none",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


@pytest.mark.parametrize("falta", ["sub", "role", "iat", "exp"])
def test_token_sin_un_dato_obligatorio(settings, falta):
    ahora = datetime.now(timezone.utc)
    payload = {"sub": "1", "role": "admin", "iat": ahora, "exp": ahora + timedelta(hours=1)}
    del payload[falta]
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_con_sub_que_no_es_numero(settings):
    ahora = datetime.now(timezone.utc)
    payload = {"sub": "abc", "role": "admin", "iat": ahora, "exp": ahora + timedelta(hours=1)}
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


@pytest.mark.parametrize("token", ["", "basura", "a.b.c"])
def test_token_mal_formado(settings, token):
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


# --- Configuración ---


def test_jwt_secret_corto_falla_al_arrancar():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(jwt_secret="corto")


def test_jwt_secret_no_se_muestra_al_imprimir(settings):
    assert settings.jwt_secret.get_secret_value() not in repr(settings)
