from datetime import datetime, timezone

import pytest

from app.models import QuoteNote, QuoteStatusChange
from tests.helpers import bearer, make_quote


def url(quote_id: int) -> str:
    return f"/v1/quotes/{quote_id}"


def test_detalle_con_notas_e_historial(client, admin, db_session):
    quote = make_quote(db_session, message="Tenemos un gato.", status="scheduled")
    t1 = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    # Se insertan desordenados a propósito: la respuesta debe venir en orden cronológico
    db_session.add_all(
        [
            QuoteStatusChange(
                quote_id=quote.id, from_status="contacted", to_status="scheduled",
                changed_by=admin.id, changed_at=t2,
            ),
            QuoteStatusChange(
                quote_id=quote.id, from_status="new", to_status="contacted",
                changed_by=None, changed_at=t1,
            ),
            QuoteNote(quote_id=quote.id, body="Segunda", author_id=admin.id, created_at=t2),
            QuoteNote(quote_id=quote.id, body="Primera", author_id=None, created_at=t1),
        ]
    )
    db_session.flush()

    response = client.get(url(quote.id), headers=bearer(admin))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == quote.id
    assert body["message"] == "Tenemos un gato."
    assert body["status"] == "scheduled"
    assert body["updated_at"].endswith("Z")
    # Con el email del autor (o null si no hay), sin exponer ids de usuario
    notes = [{k: v for k, v in note.items() if k != "id"} for note in body["notes"]]
    assert notes == [
        {"body": "Primera", "author_email": None, "created_at": "2026-10-02T10:00:00Z"},
        {
            "body": "Segunda",
            "author_email": "admin@example.com",
            "created_at": "2026-10-03T10:00:00Z",
        },
    ]
    assert body["status_history"] == [
        {
            "from_status": "new",
            "to_status": "contacted",
            "changed_by_email": None,
            "changed_at": "2026-10-02T10:00:00Z",
        },
        {
            "from_status": "contacted",
            "to_status": "scheduled",
            "changed_by_email": "admin@example.com",
            "changed_at": "2026-10-03T10:00:00Z",
        },
    ]


def test_detalle_sin_notas_ni_historial(client, admin, db_session):
    quote = make_quote(db_session)
    body = client.get(url(quote.id), headers=bearer(admin)).json()
    assert body["notes"] == []
    assert body["status_history"] == []
    assert body["message"] is None


def test_id_inexistente_da_404(client, admin):
    response = client.get(url(999_999_999), headers=bearer(admin))
    assert response.status_code == 404
    assert response.json() == {"detail": "Quote not found."}


@pytest.mark.parametrize("quote_id", ["abc", "0", "-1", str(2**63)])
def test_id_invalido_da_422(client, admin, quote_id):
    assert client.get(f"/v1/quotes/{quote_id}", headers=bearer(admin)).status_code == 422


def test_demo_pidiendo_una_real_da_404_igual_que_inexistente(client, demo, db_session):
    real = make_quote(db_session)
    inexistente = client.get(url(999_999_999), headers=bearer(demo))
    oculta = client.get(url(real.id), headers=bearer(demo))
    # Misma respuesta exacta: no se puede distinguir "no existe" de "existe pero no es tuya"
    assert oculta.status_code == inexistente.status_code == 404
    assert oculta.json() == inexistente.json()


def test_demo_ve_el_detalle_de_una_demo(client, demo, db_session):
    ficticia = make_quote(db_session, is_demo=True)
    assert client.get(url(ficticia.id), headers=bearer(demo)).status_code == 200


def test_admin_pidiendo_una_demo_da_404(client, admin, db_session):
    ficticia = make_quote(db_session, is_demo=True)
    assert client.get(url(ficticia.id), headers=bearer(admin)).status_code == 404


def test_sin_token_da_401(client, db_session):
    quote = make_quote(db_session)
    assert client.get(url(quote.id)).status_code == 401
