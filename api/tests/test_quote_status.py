import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.models import Quote, QuoteStatusChange, User
from app.services.quotes import change_status
from tests.helpers import bearer, make_quote


def url(quote_id: int) -> str:
    return f"/v1/quotes/{quote_id}/status"


def history(db_session, quote: Quote) -> list[tuple[str, str]]:
    rows = db_session.execute(
        select(QuoteStatusChange.from_status, QuoteStatusChange.to_status)
        .where(QuoteStatusChange.quote_id == quote.id)
        .order_by(QuoteStatusChange.id)
    )
    return [tuple(row) for row in rows]


def test_cambio_de_estado_guarda_estado_e_historial(client, admin, db_session):
    quote = make_quote(db_session)
    antes = quote.updated_at
    response = client.patch(url(quote.id), json={"status": "contacted"}, headers=bearer(admin))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "contacted"
    assert body["status_history"] == [
        {
            "from_status": "new",
            "to_status": "contacted",
            "changed_by_email": "admin@example.com",
            "changed_at": body["status_history"][0]["changed_at"],
        }
    ]
    db_session.refresh(quote)
    assert quote.status == "contacted"
    assert quote.updated_at >= antes
    assert history(db_session, quote) == [("new", "contacted")]


def test_se_puede_retroceder_y_el_historial_acumula(client, admin, db_session):
    quote = make_quote(db_session)
    for status in ("contacted", "scheduled", "contacted"):
        response = client.patch(url(quote.id), json={"status": status}, headers=bearer(admin))
        assert response.status_code == 200
    body = client.get(f"/v1/quotes/{quote.id}", headers=bearer(admin)).json()
    assert [(c["from_status"], c["to_status"]) for c in body["status_history"]] == [
        ("new", "contacted"),
        ("contacted", "scheduled"),
        ("scheduled", "contacted"),
    ]


def test_mismo_estado_da_409_y_no_guarda_historial(client, admin, db_session):
    quote = make_quote(db_session, status="contacted")
    response = client.patch(url(quote.id), json={"status": "contacted"}, headers=bearer(admin))
    assert response.status_code == 409
    assert response.json() == {"detail": "Quote already has this status."}
    assert history(db_session, quote) == []


def test_el_demo_recibe_403(client, demo, db_session):
    ficticia = make_quote(db_session, is_demo=True)
    response = client.patch(url(ficticia.id), json={"status": "closed"}, headers=bearer(demo))
    assert response.status_code == 403
    db_session.refresh(ficticia)
    assert ficticia.status == "new"
    assert history(db_session, ficticia) == []


@pytest.mark.parametrize("body", [{"status": "closed"}, {"status": "no-existe"}, {}])
def test_el_demo_recibe_403_antes_de_validar_o_buscar(client, demo, body):
    # Id inexistente o cuerpo inválido: igual 403, sin revelar si el id existe
    response = client.patch(url(999_999_999), json=body, headers=bearer(demo))
    assert response.status_code == 403


def test_id_inexistente_da_404(client, admin):
    response = client.patch(url(999_999_999), json={"status": "closed"}, headers=bearer(admin))
    assert response.status_code == 404
    assert response.json() == {"detail": "Quote not found."}


def test_admin_no_puede_cambiar_una_demo(client, admin, db_session):
    ficticia = make_quote(db_session, is_demo=True)
    response = client.patch(url(ficticia.id), json={"status": "closed"}, headers=bearer(admin))
    assert response.status_code == 404
    db_session.refresh(ficticia)
    assert ficticia.status == "new"


@pytest.mark.parametrize(
    "body",
    [{"status": "deleted"}, {"status": None}, {}, {"status": "closed", "changed_by": 1}],
)
def test_cuerpo_invalido_da_422(client, admin, db_session, body):
    quote = make_quote(db_session)
    assert client.patch(url(quote.id), json=body, headers=bearer(admin)).status_code == 422


def test_sin_token_da_401(client, db_session):
    quote = make_quote(db_session)
    assert client.patch(url(quote.id), json={"status": "closed"}).status_code == 401


def test_si_falla_el_historial_no_cambia_el_estado(db_session):
    """Atomicidad: el INSERT del historial falla (FK de changed_by rota) y el UPDATE se revierte."""
    quote = make_quote(db_session)
    # Ya guardada (en las pruebas, commit cierra un SAVEPOINT): el rollback del servicio
    # debe volver a este punto, no borrarla
    db_session.commit()
    # Un "admin" que no existe en la base: changed_by viola la FK hacia users
    fantasma = User(id=10**12, email="fantasma@example.com", password_hash="!", role="admin")

    with pytest.raises(IntegrityError):
        change_status(db_session, fantasma, quote.id, "closed")

    # Lo que dice la base, no la copia en memoria
    db_session.expire_all()
    assert db_session.get(Quote, quote.id).status == "new"
    assert history(db_session, quote) == []
    assert db_session.scalar(select(func.count()).select_from(QuoteStatusChange)) == 0


def test_bloquea_la_fila_con_for_update(client, admin, db_session):
    quote = make_quote(db_session)
    sentencias: list[str] = []

    def capturar(conn, cursor, statement, *args):
        sentencias.append(statement)

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", capturar)
    try:
        client.patch(url(quote.id), json={"status": "closed"}, headers=bearer(admin))
    finally:
        event.remove(connection, "before_cursor_execute", capturar)
    assert any("FROM quotes" in s and "FOR UPDATE" in s for s in sentencias)
