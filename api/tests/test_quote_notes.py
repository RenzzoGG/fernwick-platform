import pytest
from sqlalchemy import select

from app.models import QuoteNote
from app.models.base import NOTE_BODY_MAX
from tests.helpers import bearer, make_quote


def url(quote_id: int) -> str:
    return f"/v1/quotes/{quote_id}/notes"


def notes_of(db_session, quote) -> list[QuoteNote]:
    return list(db_session.scalars(select(QuoteNote).where(QuoteNote.quote_id == quote.id)))


def test_agregar_nota(client, admin, db_session):
    quote = make_quote(db_session)
    response = client.post(
        url(quote.id), json={"body": "  Llamar el lunes.  "}, headers=bearer(admin)
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "body", "author_email", "created_at"}
    assert body["body"] == "Llamar el lunes."
    assert body["author_email"] == "admin@example.com"
    assert body["created_at"].endswith("Z")

    [note] = notes_of(db_session, quote)
    assert note.id == body["id"]
    assert note.author_id == admin.id
    assert note.is_demo is False

    # Aparece en el detalle
    detail = client.get(f"/v1/quotes/{quote.id}", headers=bearer(admin)).json()
    assert [n["body"] for n in detail["notes"]] == ["Llamar el lunes."]


def test_varias_notas_salen_en_orden(client, admin, db_session):
    quote = make_quote(db_session)
    for texto in ("uno", "dos", "tres"):
        client.post(url(quote.id), json={"body": texto}, headers=bearer(admin))
    detail = client.get(f"/v1/quotes/{quote.id}", headers=bearer(admin)).json()
    assert [n["body"] for n in detail["notes"]] == ["uno", "dos", "tres"]


def test_nota_de_largo_maximo(client, admin, db_session):
    quote = make_quote(db_session)
    payload = {"body": "x" * NOTE_BODY_MAX}
    response = client.post(url(quote.id), json=payload, headers=bearer(admin))
    assert response.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        {"body": ""},
        {"body": "   "},
        {"body": "x" * (NOTE_BODY_MAX + 1)},
        {"body": None},
        {},
        {"body": "hola", "author_id": 1},
        {"body": "hola", "is_demo": True},
    ],
)
def test_cuerpo_invalido_da_422(client, admin, db_session, payload):
    quote = make_quote(db_session)
    assert client.post(url(quote.id), json=payload, headers=bearer(admin)).status_code == 422
    assert notes_of(db_session, quote) == []


def test_el_demo_recibe_403(client, demo, db_session):
    ficticia = make_quote(db_session, is_demo=True)
    response = client.post(url(ficticia.id), json={"body": "hola"}, headers=bearer(demo))
    assert response.status_code == 403
    assert notes_of(db_session, ficticia) == []


def test_el_demo_recibe_403_aunque_el_id_no_exista(client, demo):
    response = client.post(url(999_999_999), json={"body": "hola"}, headers=bearer(demo))
    assert response.status_code == 403


def test_id_inexistente_da_404(client, admin):
    response = client.post(url(999_999_999), json={"body": "hola"}, headers=bearer(admin))
    assert response.status_code == 404
    assert response.json() == {"detail": "Quote not found."}


def test_admin_no_puede_anotar_una_demo(client, admin, db_session):
    ficticia = make_quote(db_session, is_demo=True)
    response = client.post(url(ficticia.id), json={"body": "hola"}, headers=bearer(admin))
    assert response.status_code == 404
    assert notes_of(db_session, ficticia) == []


def test_sin_token_da_401(client, db_session):
    quote = make_quote(db_session)
    assert client.post(url(quote.id), json={"body": "hola"}).status_code == 401
