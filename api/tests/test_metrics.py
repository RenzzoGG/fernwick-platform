from datetime import date, timedelta

from app.models.base import QUOTE_STATUSES, SERVICES
from app.schemas.quote import business_today
from app.services.metrics import metrics_summary
from tests.helpers import bearer, local, make_quote

URL = "/v1/metrics/summary"
HOY = date(2026, 10, 21)


def por_dia(summary) -> dict[date, int]:
    return {item.date: item.count for item in summary.last_30_days}


def test_sin_cotizaciones_todo_en_cero(db_session, admin):
    summary = metrics_summary(db_session, admin, today=HOY)
    assert summary.total == 0
    assert summary.by_status == dict.fromkeys(QUOTE_STATUSES, 0)
    assert summary.by_service == dict.fromkeys(SERVICES, 0)
    assert len(summary.last_30_days) == 30
    assert all(item.count == 0 for item in summary.last_30_days)


def test_treinta_dias_consecutivos_terminando_hoy(db_session, admin):
    dias = [item.date for item in metrics_summary(db_session, admin, today=HOY).last_30_days]
    assert dias == [HOY - timedelta(days=29 - i) for i in range(30)]


def test_dias_sin_cotizaciones_aparecen_en_cero(db_session, admin):
    make_quote(db_session, created_at=local(HOY))
    make_quote(db_session, created_at=local(HOY, 18))
    make_quote(db_session, created_at=local(HOY - timedelta(days=5)))
    make_quote(db_session, created_at=local(HOY - timedelta(days=29)))
    conteo = por_dia(metrics_summary(db_session, admin, today=HOY))
    assert conteo[HOY] == 2
    assert conteo[HOY - timedelta(days=5)] == 1
    assert conteo[HOY - timedelta(days=29)] == 1
    assert conteo[HOY - timedelta(days=1)] == 0
    assert sum(conteo.values()) == 4
    assert list(conteo.values()).count(0) == 27


def test_fuera_de_la_ventana_cuenta_en_el_total_pero_no_en_los_dias(db_session, admin):
    make_quote(db_session, created_at=local(HOY - timedelta(days=30)))
    make_quote(db_session, created_at=local(HOY + timedelta(days=1)))
    summary = metrics_summary(db_session, admin, today=HOY)
    assert summary.total == 2
    assert sum(por_dia(summary).values()) == 0


def test_el_dia_se_corta_a_medianoche_en_la_zona_del_negocio(db_session, admin):
    ayer = HOY - timedelta(days=1)
    # Un minuto antes y un minuto después de la medianoche local (no la de UTC)
    make_quote(db_session, created_at=local(ayer, 23, 59))
    make_quote(db_session, created_at=local(HOY, 0, 1))
    make_quote(db_session, created_at=local(HOY, 0, 0))
    conteo = por_dia(metrics_summary(db_session, admin, today=HOY))
    assert conteo[ayer] == 1
    assert conteo[HOY] == 2


def test_por_estado_y_por_servicio_con_todas_las_claves(db_session, admin):
    make_quote(db_session, status="new", service="deep")
    make_quote(db_session, status="new", service="deep")
    make_quote(db_session, status="closed", service="office", home_size="office")
    summary = metrics_summary(db_session, admin, today=HOY)
    assert summary.total == 3
    assert summary.by_status == {"new": 2, "contacted": 0, "scheduled": 0, "closed": 1}
    assert summary.by_service == dict.fromkeys(SERVICES, 0) | {"deep": 2, "office": 1}


def test_cada_rol_cuenta_solo_su_alcance(db_session, admin, demo):
    make_quote(db_session, created_at=local(HOY), status="closed")
    for _ in range(3):
        make_quote(db_session, created_at=local(HOY), is_demo=True)
    del_admin = metrics_summary(db_session, admin, today=HOY)
    del_demo = metrics_summary(db_session, demo, today=HOY)
    assert (del_admin.total, por_dia(del_admin)[HOY], del_admin.by_status["closed"]) == (1, 1, 1)
    assert (del_demo.total, por_dia(del_demo)[HOY], del_demo.by_status["closed"]) == (3, 3, 0)


def test_endpoint(client, admin, db_session):
    hoy = business_today()
    make_quote(db_session, created_at=local(hoy))
    response = client.get(URL, headers=bearer(admin))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"total", "by_status", "by_service", "last_30_days"}
    assert body["total"] == 1
    assert len(body["last_30_days"]) == 30
    assert body["last_30_days"][-1] == {"date": hoy.isoformat(), "count": 1}
    assert body["last_30_days"][0] == {
        "date": (hoy - timedelta(days=29)).isoformat(),
        "count": 0,
    }


def test_el_demo_puede_ver_metricas(client, demo):
    assert client.get(URL, headers=bearer(demo)).status_code == 200


def test_sin_token_da_401(client):
    assert client.get(URL).status_code == 401


def test_dias_correctos_al_cruzar_el_cambio_de_horario(db_session, admin):
    # En America/New_York el horario de verano termina el 1 de noviembre de 2026: ese día
    # dura 25 horas. Cada día debe seguir cortándose a medianoche local.
    hoy = date(2026, 11, 10)
    make_quote(db_session, created_at=local(date(2026, 11, 1), 23, 30))
    make_quote(db_session, created_at=local(date(2026, 11, 2), 0, 30))
    make_quote(db_session, created_at=local(date(2026, 10, 31), 23, 30))
    conteo = por_dia(metrics_summary(db_session, admin, today=hoy))
    assert conteo[date(2026, 10, 31)] == 1
    assert conteo[date(2026, 11, 1)] == 1
    assert conteo[date(2026, 11, 2)] == 1
