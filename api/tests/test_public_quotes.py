from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.main import MAX_BODY_BYTES
from app.models import Quote
from app.models.base import QUOTE_STATUSES
from app.schemas.quote import MAX_DAYS_AHEAD, business_today

URL = "/v1/public/quotes"


def payload(**overrides) -> dict:
    data = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "(212) 555-0100",
        "service": "standard",
        "home_size": "2-bed",
        "preferred_date": (business_today() + timedelta(days=7)).isoformat(),
        "message": "We have a friendly cat.",
    }
    return data | overrides


def quotes_count(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(Quote))


def error_locs(response) -> list[tuple]:
    return [tuple(error["loc"]) for error in response.json()["detail"]]


# --- Caso válido ---


def test_cotizacion_valida_se_guarda(client, db_session):
    response = client.post(URL, json=payload(name="  Ada Lovelace  ", message="  Hi!  "))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "created_at"}  # la respuesta no repite datos personales

    quote = db_session.get(Quote, body["id"])
    assert quote.name == "Ada Lovelace"  # espacios recortados
    assert quote.message == "Hi!"
    assert quote.service == "standard" and quote.home_size == "2-bed"
    # El servidor fija estos valores
    assert quote.status == "new" and quote.status in QUOTE_STATUSES
    assert quote.is_demo is False
    assert quote.created_at.isoformat() == body["created_at"].replace("Z", "+00:00")


def test_message_es_opcional_y_vacio_se_guarda_como_null(client, db_session):
    sin_mensaje = payload()
    del sin_mensaje["message"]

    r1 = client.post(URL, json=sin_mensaje)
    r2 = client.post(URL, json=payload(message="   "))

    assert (r1.status_code, r2.status_code) == (201, 201)
    assert db_session.get(Quote, r1.json()["id"]).message is None
    assert db_session.get(Quote, r2.json()["id"]).message is None


def test_fecha_de_hoy_y_limite_futuro_se_aceptan(client):
    hoy = business_today()
    for fecha in (hoy, hoy + timedelta(days=MAX_DAYS_AHEAD)):
        assert client.post(URL, json=payload(preferred_date=fecha.isoformat())).status_code == 201


@pytest.mark.parametrize("phone", ["2125550100", "+1 (212) 555-0100", "212.555.0100"])
def test_formatos_de_telefono_aceptados(client, phone):
    assert client.post(URL, json=payload(phone=phone)).status_code == 201


# --- Validaciones (422) ---


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("name", "A"),
        ("name", "   "),
        ("name", "x" * 101),
        ("name", 123),
        ("email", "no-es-un-email"),
        ("email", "ada@localhost"),
        ("email", "a" * 64 + "@" + ("b" * 60 + ".") * 4 + "com"),  # 313 caracteres
        ("phone", "555-0100"),  # menos de 10 dígitos
        ("phone", "212-555-0100 ext"),  # letras
        ("phone", "1" * 31),
        ("service", "laundry"),
        ("home_size", "5-bed"),
        ("preferred_date", "mañana"),
        ("preferred_date", "2020-01-01"),
        ("message", "x" * 501),
    ],
)
def test_campo_invalido_da_422(client, db_session, campo, valor):
    response = client.post(URL, json=payload(**{campo: valor}))

    assert response.status_code == 422
    assert ("body", campo) in error_locs(response)
    assert quotes_count(db_session) == 0


def test_fecha_pasada_y_demasiado_lejana_con_mensaje_claro(client):
    hoy = business_today()
    ayer = client.post(URL, json=payload(preferred_date=(hoy - timedelta(days=1)).isoformat()))
    lejos = client.post(URL, json=payload(preferred_date=(hoy + timedelta(days=MAX_DAYS_AHEAD + 1)).isoformat()))

    assert ayer.status_code == lejos.status_code == 422
    assert "cannot be in the past" in ayer.json()["detail"][0]["msg"]
    assert f"within the next {MAX_DAYS_AHEAD} days" in lejos.json()["detail"][0]["msg"]


@pytest.mark.parametrize("campo", ["name", "email", "phone", "service", "home_size", "preferred_date"])
def test_campo_obligatorio_ausente_da_422(client, campo):
    data = payload()
    del data[campo]

    response = client.post(URL, json=data)

    assert response.status_code == 422
    assert ("body", campo) in error_locs(response)


def test_json_mal_formado_da_422(client):
    response = client.post(URL, content=b"{no es json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


# --- Campos que el cliente no puede enviar ---


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("status", "closed"),
        ("is_demo", True),
        ("id", 1),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("updated_at", "2026-01-01T00:00:00Z"),
        ("campo_inventado", "x"),
    ],
)
def test_campos_prohibidos_dan_422(client, db_session, campo, valor):
    response = client.post(URL, json=payload(**{campo: valor}))

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"
    assert ("body", campo) in error_locs(response)
    assert quotes_count(db_session) == 0


# --- Honeypot ---


def test_honeypot_lleno_responde_201_pero_no_guarda(client, db_session):
    response = client.post(URL, json=payload(website="https://spam.example"))

    assert response.status_code == 201
    assert set(response.json()) == {"id", "created_at"}  # misma forma que un éxito real
    assert quotes_count(db_session) == 0


def test_honeypot_vacio_o_con_espacios_guarda_normal(client, db_session):
    assert client.post(URL, json=payload(website="")).status_code == 201
    assert client.post(URL, json=payload(website="   ")).status_code == 201
    assert quotes_count(db_session) == 2


# --- Tamaño del cuerpo (413) ---


def test_cuerpo_demasiado_grande_da_413(client, db_session):
    # Un JSON de más de 10 KB: el límite actúa antes que la validación de Pydantic
    response = client.post(URL, json=payload(message="x" * MAX_BODY_BYTES))

    assert response.status_code == 413
    assert quotes_count(db_session) == 0


def test_cuerpo_grande_enviado_por_partes_da_413(client, db_session):
    def partes():
        yield b'{"name": "Ada", "message": "'
        for _ in range(20):
            yield b"x" * 1024
        yield b'"}'

    response = client.post(URL, content=partes(), headers={"Content-Type": "application/json"})

    assert "content-length" not in response.request.headers
    assert response.status_code == 413
    assert quotes_count(db_session) == 0


# --- Límite de solicitudes (429) ---


def test_sexta_solicitud_en_un_minuto_da_429(client, db_session):
    for _ in range(5):
        assert client.post(URL, json=payload()).status_code == 201

    response = client.post(URL, json=payload())

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert quotes_count(db_session) == 5


def test_solicitudes_invalidas_tambien_cuentan_para_el_limite(client):
    for _ in range(5):
        assert client.post(URL, json={"basura": True}).status_code == 422

    # Un bot no puede tantear validaciones sin gastar su cupo
    assert client.post(URL, json=payload()).status_code == 429


# --- CORS en el endpoint real ---


def test_cors_permite_la_landing_en_el_endpoint(client):
    response = client.post(URL, json=payload(), headers={"Origin": "http://localhost:8000"})

    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
