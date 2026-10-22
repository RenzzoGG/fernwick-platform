from datetime import date

import pytest

from tests.helpers import bearer, make_quote

URL = "/v1/quotes"


def ids(response) -> list[int]:
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer no-es-un-jwt"}], ids=["sin-token", "token-invalido"]
)
def test_sin_token_valido_da_401(client, headers):
    response = client.get(URL, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_lista_formato_y_orden_por_defecto(client, admin, db_session):
    viejo = make_quote(db_session)
    nuevo = make_quote(db_session)
    response = client.get(URL, headers=bearer(admin))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    # Por defecto: más recientes primero
    assert ids(response) == [nuevo.id, viejo.id]
    assert set(body["items"][0]) == {
        "id", "name", "email", "phone", "service", "home_size",
        "preferred_date", "status", "created_at",
    }
    assert body["items"][0]["created_at"].endswith("Z")


def test_filtro_por_estado(client, admin, db_session):
    make_quote(db_session, status="new")
    contactada = make_quote(db_session, status="contacted")
    response = client.get(URL, params={"status": "contacted"}, headers=bearer(admin))
    assert ids(response) == [contactada.id]
    assert response.json()["total"] == 1


@pytest.mark.parametrize(
    ("q", "esperado"),
    [
        ("lovelace", "ada"),  # parte del nombre, sin distinguir mayúsculas
        ("ADA@EXAMPLE", "ada"),  # parte del email
        ("hopper", "grace"),
        ("555-0199", "grace"),  # teléfono con otro formato: se compara por dígitos
        ("(646) 555", "grace"),
        ("6465550199", "grace"),
    ],
)
def test_busqueda_por_nombre_email_y_telefono(client, admin, db_session, q, esperado):
    personas = {
        "ada": make_quote(
            db_session, name="Ada Lovelace", email="ada@example.com", phone="212-555-0100"
        ),
        "grace": make_quote(
            db_session, name="Grace Hopper", email="grace@navy.example", phone="+1 646.555.0199"
        ),
    }
    response = client.get(URL, params={"q": q}, headers=bearer(admin))
    assert ids(response) == [personas[esperado].id]


def test_busqueda_sin_digitos_suficientes_no_busca_en_el_telefono(client, admin, db_session):
    make_quote(db_session, name="Ada Lovelace", phone="212-555-0100")
    # "x1" tiene un solo dígito: no se busca en el teléfono (si no, encontraría todo con un 1)
    assert client.get(URL, params={"q": "x1"}, headers=bearer(admin)).json()["total"] == 0


def test_texto_con_letras_no_busca_en_el_telefono(client, admin, db_session):
    make_quote(db_session, name="Ada Lovelace", phone="212-555-0100")
    # "a2125" tiene dígitos del teléfono, pero no es un teléfono: solo se busca en nombre y email
    assert client.get(URL, params={"q": "a2125"}, headers=bearer(admin)).json()["total"] == 0


def test_busqueda_escapa_los_comodines_de_like(client, admin, db_session):
    make_quote(db_session, name="Ana Ruiz")
    con_guion_bajo = make_quote(db_session, name="Ana_Ruiz")
    # Sin escapar, "_" sería "cualquier carácter" y también encontraría "Ana Ruiz"
    assert ids(client.get(URL, params={"q": "a_r"}, headers=bearer(admin))) == [con_guion_bajo.id]
    assert client.get(URL, params={"q": "%%"}, headers=bearer(admin)).json()["total"] == 0


def test_busqueda_vacia_equivale_a_no_buscar(client, admin, db_session):
    make_quote(db_session)
    make_quote(db_session)
    assert client.get(URL, params={"q": "   "}, headers=bearer(admin)).json()["total"] == 2


def test_busqueda_combinada_con_estado(client, admin, db_session):
    make_quote(db_session, name="Ana Nueva", status="new")
    cerrada = make_quote(db_session, name="Ana Cerrada", status="closed")
    response = client.get(URL, params={"q": "ana", "status": "closed"}, headers=bearer(admin))
    assert ids(response) == [cerrada.id]


@pytest.mark.parametrize(
    ("sort", "orden"),
    [
        ("created_at", [0, 1, 2]),
        ("-created_at", [2, 1, 0]),
        ("preferred_date", [1, 2, 0]),
        ("-preferred_date", [0, 2, 1]),
    ],
)
def test_ordenamientos_permitidos(client, admin, db_session, sort, orden):
    quotes = [
        make_quote(db_session, preferred_date=date(2026, 12, 30)),
        make_quote(db_session, preferred_date=date(2026, 12, 1)),
        make_quote(db_session, preferred_date=date(2026, 12, 15)),
    ]
    response = client.get(URL, params={"sort": sort}, headers=bearer(admin))
    assert ids(response) == [quotes[i].id for i in orden]


def test_empates_se_desempatan_por_id(client, admin, db_session):
    mismo_dia = date(2026, 12, 1)
    quotes = [make_quote(db_session, preferred_date=mismo_dia) for _ in range(5)]
    response = client.get(URL, params={"sort": "preferred_date"}, headers=bearer(admin))
    assert ids(response) == sorted(q.id for q in quotes)


def test_paginacion(client, admin, db_session):
    quotes = [make_quote(db_session) for _ in range(5)]
    esperado = [q.id for q in reversed(quotes)]
    paginas = [
        client.get(URL, params={"page": page, "page_size": 2}, headers=bearer(admin)).json()
        for page in (1, 2, 3)
    ]
    assert [item["id"] for p in paginas for item in p["items"]] == esperado
    assert [len(p["items"]) for p in paginas] == [2, 2, 1]
    assert all(p["total"] == 5 for p in paginas)


def test_pagina_fuera_de_rango_da_lista_vacia(client, admin, db_session):
    make_quote(db_session)
    body = client.get(URL, params={"page": 50}, headers=bearer(admin)).json()
    assert body["items"] == []
    assert body["total"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {"page_size": 101},
        {"page_size": 0},
        {"page": 0},
        {"page": 10_001},
        {"sort": "name"},
        {"sort": "password_hash"},
        {"sort": "created_at; DROP TABLE quotes"},
        {"status": "deleted"},
        {"q": "a"},
        {"q": "x" * 101},
        {"order_by": "email"},  # parámetro desconocido
        {"is_demo": "true"},
    ],
)
def test_parametros_invalidos_dan_422(client, admin, params):
    assert client.get(URL, params=params, headers=bearer(admin)).status_code == 422


def test_page_size_maximo_es_100(client, admin):
    response = client.get(URL, params={"page_size": 100}, headers=bearer(admin))
    assert response.status_code == 200
    assert response.json()["page_size"] == 100


def test_el_admin_solo_ve_filas_reales(client, admin, db_session):
    real = make_quote(db_session)
    make_quote(db_session, is_demo=True)
    response = client.get(URL, headers=bearer(admin))
    assert ids(response) == [real.id]


def test_el_demo_solo_ve_filas_demo(client, demo, db_session):
    make_quote(db_session)
    ficticia = make_quote(db_session, is_demo=True)
    response = client.get(URL, headers=bearer(demo))
    assert response.status_code == 200
    assert ids(response) == [ficticia.id]
    assert response.json()["total"] == 1
