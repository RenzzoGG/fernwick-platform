import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.rate_limit import RateLimiter, client_ip, rate_limit

PEER = "10.0.0.1"  # IP de la conexión TCP (en producción, el proxy de Railway)


def hacer_request(*headers: tuple[str, str]) -> Request:
    """Request mínima de Starlette con la IP de conexión PEER y los encabezados dados."""
    scope = {
        "type": "http",
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers],
        "client": (PEER, 50000),
    }
    return Request(scope)


# --- Modo "none": nunca se confía en los encabezados ---


def test_none_ignora_los_encabezados_de_proxy():
    request = hacer_request(("X-Forwarded-For", "1.2.3.4"), ("CF-Connecting-IP", "5.6.7.8"))
    assert client_ip(request, "none") == PEER


# --- Modo "x-forwarded-for" ---


def test_xff_usa_la_entrada_derecha():
    # "6.6.6.6" la inventó el cliente; "1.2.3.4" la agregó el proxy
    request = hacer_request(("X-Forwarded-For", "6.6.6.6, 1.2.3.4"))
    assert client_ip(request, "x-forwarded-for") == "1.2.3.4"


def test_xff_repetido_en_varias_lineas():
    request = hacer_request(("X-Forwarded-For", "6.6.6.6"), ("X-Forwarded-For", "1.2.3.4"))
    assert client_ip(request, "x-forwarded-for") == "1.2.3.4"


def test_xff_ignora_cf_connecting_ip():
    request = hacer_request(("X-Forwarded-For", "1.2.3.4"), ("CF-Connecting-IP", "5.6.7.8"))
    assert client_ip(request, "x-forwarded-for") == "1.2.3.4"


# --- Modo "cf-connecting-ip" ---


def test_cf_usa_su_encabezado_e_ignora_xff():
    request = hacer_request(("X-Forwarded-For", "1.2.3.4"), ("CF-Connecting-IP", "5.6.7.8"))
    assert client_ip(request, "cf-connecting-ip") == "5.6.7.8"


def test_ipv6_se_normaliza():
    request = hacer_request(("CF-Connecting-IP", "2001:DB8:0:0:0:0:0:1"))
    assert client_ip(request, "cf-connecting-ip") == "2001:db8::1"


# --- Valores faltantes o inválidos: se usa la IP de la conexión ---


@pytest.mark.parametrize("header", ["x-forwarded-for", "cf-connecting-ip"])
def test_sin_encabezado_usa_la_conexion(header):
    assert client_ip(hacer_request(), header) == PEER


@pytest.mark.parametrize(
    ("header", "nombre", "valor"),
    [
        ("x-forwarded-for", "X-Forwarded-For", "1.2.3.4, no-es-una-ip"),
        ("x-forwarded-for", "X-Forwarded-For", "1.2.3.4,"),
        ("cf-connecting-ip", "CF-Connecting-IP", "999.1.1.1"),
        ("cf-connecting-ip", "CF-Connecting-IP", ""),
    ],
)
def test_valor_invalido_usa_la_conexion(header, nombre, valor):
    assert client_ip(hacer_request((nombre, valor)), header) == PEER


# --- Integración con el limitador ---


def app_con_limite(client_ip_header: str) -> TestClient:
    app = FastAPI()
    limiter = RateLimiter([(2, 60)])

    @app.get("/x", dependencies=[Depends(rate_limit(limiter))])
    def x() -> dict[str, bool]:
        return {"ok": True}

    # La dependencia lee la configuración con Depends(get_settings): se puede reemplazar
    settings = get_settings().model_copy(update={"client_ip_header": client_ip_header})
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_con_none_falsificar_xff_no_da_cupo_nuevo():
    client = app_con_limite("none")
    codigos = [
        client.get("/x", headers={"X-Forwarded-For": f"1.1.1.{i}"}).status_code for i in range(3)
    ]
    assert codigos == [200, 200, 429]


def test_con_xff_cada_ip_tiene_su_cupo():
    client = app_con_limite("x-forwarded-for")
    for _ in range(2):
        assert client.get("/x", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/x", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert client.get("/x", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_client_ip_header_invalido_falla_al_arrancar():
    with pytest.raises(ValidationError):
        Settings(client_ip_header="true")
