from datetime import datetime, timedelta, timezone
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_role
from app.models import User
from app.models.user import DEMO_EMAIL
from app.security import create_access_token
from app.services.auth import create_admin

CLAVE = "una clave bastante larga"
LOGIN_FALLIDO = {"detail": "Incorrect email or password."}
NO_AUTENTICADO = {"detail": "Could not validate credentials."}


@pytest.fixture
def admin(db_session: Session) -> User:
    return create_admin(db_session, "admin@example.com", CLAVE)


@pytest.fixture
def demo(db_session: Session) -> User:
    # Igual que lo crea seed-demo: "!" no es un hash válido, nadie entra con contraseña
    user = User(email=DEMO_EMAIL, password_hash="!", role="demo")
    db_session.add(user)
    db_session.flush()
    return user


def bearer(user: User, **kwargs) -> dict[str, str]:
    token = create_access_token(user.id, user.role, get_settings(), **kwargs)
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


# --- POST /v1/auth/login ---


def test_login_correcto(client, admin, db_session):
    response = login(client, "admin@example.com", CLAVE)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "role"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 60 * 60
    assert body["role"] == "admin"

    db_session.refresh(admin)
    assert admin.last_login_at is not None

    # El token sirve para entrar a una ruta protegida
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == {"id": admin.id, "email": "admin@example.com", "role": "admin"}


def test_login_no_distingue_mayusculas_ni_espacios_en_el_email(client, admin):
    assert login(client, "  ADMIN@Example.COM ", CLAVE).status_code == 200


def test_login_con_clave_incorrecta(client, admin, db_session):
    response = login(client, "admin@example.com", "otra clave cualquiera")
    assert response.status_code == 401
    assert response.json() == LOGIN_FALLIDO
    assert response.headers["www-authenticate"] == "Bearer"
    db_session.refresh(admin)
    assert admin.last_login_at is None


def test_login_con_espacios_de_mas_en_la_clave(client, admin):
    # Los espacios de la contraseña son parte de ella: no se recortan
    assert login(client, "admin@example.com", f" {CLAVE} ").status_code == 401


def test_email_inexistente_da_la_misma_respuesta(client, admin):
    inexistente = login(client, "nadie@example.com", CLAVE)
    clave_mala = login(client, "admin@example.com", "otra clave cualquiera")
    assert inexistente.status_code == clave_mala.status_code == 401
    assert inexistente.json() == clave_mala.json() == LOGIN_FALLIDO


def test_usuario_desactivado_no_puede_entrar(client, admin, db_session):
    admin.is_active = False
    db_session.flush()
    response = login(client, "admin@example.com", CLAVE)
    assert response.status_code == 401
    assert response.json() == LOGIN_FALLIDO


@pytest.mark.parametrize("clave", ["!", "demo", CLAVE])
def test_el_demo_no_entra_con_contraseña(client, demo, clave):
    response = login(client, DEMO_EMAIL, clave)
    assert response.status_code == 401
    assert response.json() == LOGIN_FALLIDO


@pytest.mark.parametrize(
    "body",
    [
        {"email": "admin@example.com"},
        {"password": CLAVE},
        {"email": "", "password": CLAVE},
        {"email": "admin@example.com", "password": ""},
        {"email": "admin@example.com", "password": "x" * 129},
        {"email": "admin@example.com", "password": CLAVE, "role": "admin"},
    ],
)
def test_login_con_cuerpo_invalido_da_422(client, admin, body):
    assert client.post("/v1/auth/login", json=body).status_code == 422


def test_login_se_actualiza_el_hash_con_parametros_viejos(client, db_session):
    viejo = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash(CLAVE)
    user = User(email="viejo@example.com", password_hash=viejo, role="admin")
    db_session.add(user)
    db_session.flush()

    assert login(client, "viejo@example.com", CLAVE).status_code == 200
    db_session.refresh(user)
    assert user.password_hash != viejo
    assert user.password_hash.startswith("$argon2id$v=19$m=65536")


def test_login_limite_de_10_por_minuto(client, admin):
    # Cuerpos inválidos (422) también cuentan: un bot no puede tantear gratis
    for _ in range(10):
        assert client.post("/v1/auth/login", json={}).status_code == 422
    response = login(client, "admin@example.com", CLAVE)  # incluso con la clave correcta
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_login_rechazado_por_limite_deja_un_warning(client, caplog):
    for _ in range(10):
        client.post("/v1/auth/login", json={})
    with caplog.at_level("WARNING", logger="app"):
        client.post("/v1/auth/login", json={})
    assert "Límite de solicitudes alcanzado en /v1/auth/login" in caplog.text


def test_login_fallido_no_registra_email_ni_clave(client, admin, caplog):
    with caplog.at_level("INFO", logger="app"):
        login(client, "admin@example.com", "otra clave cualquiera")
    assert "Login fallido" in caplog.text
    assert "admin@example.com" not in caplog.text
    assert "otra clave cualquiera" not in caplog.text


# --- GET /v1/auth/me y rutas protegidas ---


def test_me_con_token_valido(client, admin):
    response = client.get("/v1/auth/me", headers=bearer(admin))
    assert response.status_code == 200
    assert response.json() == {"id": admin.id, "email": "admin@example.com", "role": "admin"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer no-es-un-jwt"},
        {"Authorization": "Basic YWRtaW46YWRtaW4="},
    ],
)
def test_me_sin_token_valido_da_401(client, headers):
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json() == NO_AUTENTICADO
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_con_token_vencido(client, admin):
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    response = client.get("/v1/auth/me", headers=bearer(admin, now=hace_dos_horas))
    assert response.status_code == 401
    assert response.json() == NO_AUTENTICADO


def test_me_con_token_manipulado(client, admin):
    token = bearer(admin)["Authorization"]
    # Cambia el último carácter de la firma
    falso = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get("/v1/auth/me", headers={"Authorization": falso}).status_code == 401


def test_me_de_un_usuario_que_ya_no_existe(client, admin, db_session):
    headers = bearer(admin)
    db_session.delete(admin)
    db_session.flush()
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_me_de_un_usuario_desactivado_despues_de_emitir_el_token(client, admin, db_session):
    headers = bearer(admin)
    assert client.get("/v1/auth/me", headers=headers).status_code == 200
    admin.is_active = False
    db_session.flush()
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_manda_el_rol_de_la_base_y_no_el_del_token(client, admin, db_session):
    headers = bearer(admin)  # el token dice "admin"
    admin.role = "demo"
    db_session.flush()
    assert client.get("/v1/auth/me", headers=headers).json()["role"] == "demo"


# --- require_role ---


@pytest.fixture
def app_con_ruta_de_admin(db_session) -> TestClient:
    """Mini-app con una ruta solo para admin (las del panel llegan en la fase 5)."""
    app = FastAPI()

    @app.post("/solo-admin")
    def solo_admin(user: Annotated[User, Depends(require_role("admin"))]) -> dict[str, int]:
        return {"id": user.id}

    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_require_role_deja_pasar_al_admin(app_con_ruta_de_admin, admin):
    response = app_con_ruta_de_admin.post("/solo-admin", headers=bearer(admin))
    assert response.status_code == 200
    assert response.json() == {"id": admin.id}


def test_require_role_rechaza_al_demo_con_403(app_con_ruta_de_admin, demo):
    response = app_con_ruta_de_admin.post("/solo-admin", headers=bearer(demo))
    assert response.status_code == 403
    assert response.json() == {"detail": "You do not have permission to perform this action."}


def test_require_role_sin_token_da_401(app_con_ruta_de_admin):
    assert app_con_ruta_de_admin.post("/solo-admin").status_code == 401


def test_require_role_usa_el_rol_de_la_base(app_con_ruta_de_admin, admin, db_session):
    headers = bearer(admin)
    admin.role = "demo"  # p. ej. se le quitó el rol de admin después del login
    db_session.flush()
    assert app_con_ruta_de_admin.post("/solo-admin", headers=headers).status_code == 403


# --- POST /v1/auth/demo ---


def test_demo_entrega_un_token_del_usuario_demo(client, demo, db_session):
    response = client.post("/v1/auth/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "demo"
    assert body["expires_in"] == 60 * 60

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == {"id": demo.id, "email": DEMO_EMAIL, "role": "demo"}
    db_session.refresh(demo)
    assert demo.last_login_at is not None


def test_demo_apagado_da_404(client, demo):
    settings = get_settings().model_copy(update={"demo_enabled": False})
    client.app.dependency_overrides[get_settings] = lambda: settings
    response = client.post("/v1/auth/demo")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_demo_sin_seed_da_404(client, caplog):
    with caplog.at_level("WARNING", logger="app"):
        response = client.post("/v1/auth/demo")
    assert response.status_code == 404
    assert "seed-demo" in caplog.text


def test_demo_desactivado_en_la_base_da_404(client, demo, db_session):
    demo.is_active = False
    db_session.flush()
    assert client.post("/v1/auth/demo").status_code == 404


def test_demo_limite_de_20_por_minuto(client, demo):
    assert all(client.post("/v1/auth/demo").status_code == 200 for _ in range(20))
    response = client.post("/v1/auth/demo")
    assert response.status_code == 429
    assert "retry-after" in response.headers


def test_limites_de_login_y_demo_son_independientes(client, admin, demo):
    for _ in range(10):
        client.post("/v1/auth/login", json={})
    assert client.post("/v1/auth/login", json={}).status_code == 429
    assert client.post("/v1/auth/demo").status_code == 200
