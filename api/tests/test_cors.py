import pytest
from pydantic import ValidationError

from app.config import Settings

PERMITIDO = "http://localhost:8080"  # fijado en conftest.py


def preflight(client, origin: str):
    # El navegador manda este OPTIONS antes de un POST con JSON desde otro origen
    return client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_preflight_desde_origen_permitido(client):
    response = preflight(client, PERMITIDO)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PERMITIDO


def test_preflight_desde_origen_no_permitido(client):
    response = preflight(client, "https://sitio-malicioso.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_respuesta_normal_no_autoriza_otros_origenes(client):
    response = client.get("/health", headers={"Origin": "https://sitio-malicioso.example"})

    # La API responde, pero sin el header el navegador no deja que esa página lea la respuesta
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_se_lee_separado_por_comas():
    settings = Settings(_env_file=None, database_url="x", cors_origins=" https://a.example/ , https://b.example,")

    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_cors_origins_rechaza_comodin():
    with pytest.raises(ValidationError, match="no admite"):
        Settings(_env_file=None, database_url="x", cors_origins="https://a.example,*")
