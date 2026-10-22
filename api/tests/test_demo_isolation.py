"""El usuario demo NUNCA ve una fila real, por ningún camino.

Se crean filas reales con un marcador único (en nombre, email, teléfono, mensaje y notas) y
filas demo. Luego se recorre como demo cada ruta del panel con todas las combinaciones de
filtros, búsquedas, órdenes y páginas, y se comprueba que:
- ningún id real aparece,
- el marcador no aparece en ningún cuerpo de respuesta,
- las métricas cuentan solo filas demo,
- el detalle de una real da el mismo 404 que un id inexistente, y escribir da 403.
"""

import itertools

import pytest

from app.main import app
from app.models import QuoteNote, QuoteStatusChange
from app.models.base import QUOTE_STATUSES, SERVICES
from app.schemas.quote import QuoteListParams, business_today
from app.services.metrics import metrics_summary
from app.services.quotes import add_note, change_status, get_quote, list_quotes
from tests.helpers import bearer, local, make_quote

# Marcadores que solo existen en las filas reales
MARCADOR = "Zyxwvut"
EMAIL_REAL = "zyxwvut.secreto@privado.example"
TELEFONO_REAL = "(917) 888-7777"
DIGITOS_REALES = "9178887777"
SORTS = ("created_at", "-created_at", "preferred_date", "-preferred_date")


@pytest.fixture
def mundo(db_session, admin, demo):
    """Filas reales (con marcador) y demo, en todos los estados y servicios, con hijos."""
    hoy = local(business_today())
    reales, ficticias = [], []
    for i, (status, service) in enumerate(itertools.product(QUOTE_STATUSES, SERVICES)):
        home_size = "office" if service == "office" else "3-bed"
        real = make_quote(
            db_session,
            name=f"{MARCADOR} Real {i}",
            email=EMAIL_REAL if i == 0 else f"{MARCADOR.lower()}{i}@privado.example",
            phone=TELEFONO_REAL,
            message=f"Mensaje {MARCADOR}",
            status=status,
            service=service,
            home_size=home_size,
            created_at=hoy,
        )
        db_session.add(QuoteNote(quote_id=real.id, body=f"Nota {MARCADOR}", author_id=admin.id))
        if status != "new":
            db_session.add(
                QuoteStatusChange(
                    quote_id=real.id, from_status="new", to_status=status, changed_by=admin.id
                )
            )
        reales.append(real)
        # Las demo comparten estado y servicio (mismos filtros), pero no el marcador
        ficticias.append(
            make_quote(
                db_session,
                is_demo=True,
                status=status,
                service=service,
                home_size=home_size,
                created_at=hoy,
            )
        )
    db_session.flush()
    return {"reales": reales, "ficticias": ficticias}


def assert_sin_datos_reales(response, reales) -> None:
    texto = response.text
    assert MARCADOR not in texto
    assert MARCADOR.lower() not in texto
    assert DIGITOS_REALES not in texto
    assert "888-7777" not in texto
    assert "privado.example" not in texto
    ids_reales = {q.id for q in reales}
    body = response.json()
    if isinstance(body, dict) and "items" in body:
        assert not ids_reales & {item["id"] for item in body["items"]}


def listados_posibles():
    """Todas las combinaciones de filtros y órdenes que puede pedir el panel."""
    busquedas = [
        None, MARCADOR, MARCADOR.lower(), "Real", EMAIL_REAL, "privado", "secreto",
        TELEFONO_REAL, DIGITOS_REALES, "888-7777", "917", "%%", "__",
    ]
    for status, q, sort in itertools.product((None, *QUOTE_STATUSES), busquedas, SORTS):
        params = {"sort": sort, "page_size": 100}
        if status:
            params["status"] = status
        if q:
            params["q"] = q
        yield params


def test_demo_nunca_ve_una_fila_real_por_http(client, demo, mundo):
    headers = bearer(demo)
    reales, ficticias = mundo["reales"], mundo["ficticias"]
    ids_ficticios = {q.id for q in ficticias}

    # 1. Lista: cada filtro, búsqueda y orden, recorriendo todas las páginas
    vistos = set()
    for params in listados_posibles():
        for page in itertools.count(1):
            response = client.get("/v1/quotes", params=params | {"page": page}, headers=headers)
            assert response.status_code == 200, params
            assert_sin_datos_reales(response, reales)
            items = response.json()["items"]
            vistos |= {item["id"] for item in items}
            if not items:
                break
    assert vistos == ids_ficticios  # además vio todas las demo

    # Páginas pequeñas: el total coincide solo con las demo
    response = client.get("/v1/quotes", params={"page_size": 1}, headers=headers)
    assert response.json()["total"] == len(ficticias)

    # 2. Detalle: cada id real da exactamente el mismo 404 que un id inexistente
    inexistente = client.get("/v1/quotes/999999999", headers=headers)
    for real in reales:
        response = client.get(f"/v1/quotes/{real.id}", headers=headers)
        assert response.status_code == 404
        assert response.json() == inexistente.json()
        assert_sin_datos_reales(response, reales)

    # Y el detalle de una demo no trae nada real
    for ficticia in ficticias:
        response = client.get(f"/v1/quotes/{ficticia.id}", headers=headers)
        assert response.status_code == 200
        assert_sin_datos_reales(response, reales)

    # 3. Escrituras sobre filas reales: 403 (y nada cambia)
    for real in reales:
        patch = client.patch(
            f"/v1/quotes/{real.id}/status", json={"status": "closed"}, headers=headers
        )
        post = client.post(f"/v1/quotes/{real.id}/notes", json={"body": "x"}, headers=headers)
        assert patch.status_code == post.status_code == 403
        assert_sin_datos_reales(patch, reales)
        assert_sin_datos_reales(post, reales)

    # 4. Métricas: solo cuentan filas demo
    response = client.get("/v1/metrics/summary", headers=headers)
    assert_sin_datos_reales(response, reales)
    body = response.json()
    assert body["total"] == len(ficticias)
    assert sum(body["by_status"].values()) == len(ficticias)
    assert sum(body["by_service"].values()) == len(ficticias)
    assert sum(day["count"] for day in body["last_30_days"]) == len(ficticias)


def test_demo_nunca_ve_una_fila_real_en_los_servicios(db_session, demo, mundo):
    """Lo mismo sin HTTP: el filtro vive en los servicios, así que protege aunque una ruta
    futura olvidara require_role o llamara al servicio de otra forma."""
    reales, ficticias = mundo["reales"], mundo["ficticias"]
    ids_reales = {q.id for q in reales}
    estados_originales = {q.id: q.status for q in reales}

    for params in listados_posibles():
        items, total = list_quotes(db_session, demo, QuoteListParams(**params))
        assert not ids_reales & {q.id for q in items}
        assert all(q.is_demo for q in items)
        assert total <= len(ficticias)

    for real in reales:
        assert get_quote(db_session, demo, real.id) is None
        # Aunque un demo llegara a los servicios de escritura, no encuentran la fila real
        assert change_status(db_session, demo, real.id, "closed") is None
        assert add_note(db_session, demo, real.id, "intrusa") is None

    summary = metrics_summary(db_session, demo)
    assert summary.total == len(ficticias)
    assert sum(day.count for day in summary.last_30_days) == len(ficticias)

    # Las filas reales siguen intactas
    db_session.expire_all()
    for real in reales:
        assert real.status == estados_originales[real.id]
        assert [note.body for note in real.notes] == [f"Nota {MARCADOR}"]


def test_el_admin_tampoco_ve_filas_demo(client, admin, mundo):
    headers = bearer(admin)
    ids_ficticios = {q.id for q in mundo["ficticias"]}
    response = client.get("/v1/quotes", params={"page_size": 100}, headers=headers)
    assert not ids_ficticios & {item["id"] for item in response.json()["items"]}
    assert response.json()["total"] == len(mundo["reales"])
    for ficticia in mundo["ficticias"]:
        assert client.get(f"/v1/quotes/{ficticia.id}", headers=headers).status_code == 404
    metrics = client.get("/v1/metrics/summary", headers=headers).json()
    assert metrics["total"] == len(mundo["reales"])


def test_la_prueba_cubre_todas_las_rutas_del_panel():
    """Si se agrega una ruta al panel, hay que sumarla a la prueba de aislamiento."""
    rutas = {
        (method, path)
        for path, ops in app.openapi()["paths"].items()
        if path.startswith(("/v1/quotes", "/v1/metrics"))
        for method in ops
    }
    assert rutas == {
        ("get", "/v1/quotes"),
        ("get", "/v1/quotes/{quote_id}"),
        ("patch", "/v1/quotes/{quote_id}/status"),
        ("post", "/v1/quotes/{quote_id}/notes"),
        ("get", "/v1/metrics/summary"),
    }
