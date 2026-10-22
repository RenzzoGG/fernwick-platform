import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import rate_limit as rate_limit_module
from app.rate_limit import RateLimiter, rate_limit

DIA = 24 * 60 * 60


class RelojFalso:
    """Reloj que solo avanza cuando la prueba lo pide."""

    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


@pytest.fixture
def reloj() -> RelojFalso:
    return RelojFalso()


@pytest.fixture
def limiter(reloj) -> RateLimiter:
    return RateLimiter([(5, 60), (20, DIA)], clock=reloj)


def test_acepta_hasta_el_maximo_y_rechaza_el_siguiente(limiter):
    assert all(limiter.hit("1.1.1.1") is None for _ in range(5))
    assert limiter.hit("1.1.1.1") == pytest.approx(60)


def test_la_ventana_se_desliza(limiter, reloj):
    for _ in range(5):
        limiter.hit("1.1.1.1")
        reloj.avanzar(10)  # marcas en t = 0, 10, 20, 30, 40

    # En t = 50 la más vieja (t = 0) sigue dentro de la ventana: faltan 10 s
    assert limiter.hit("1.1.1.1") == pytest.approx(10)
    reloj.avanzar(10)  # t = 60: la marca de t = 0 ya salió
    assert limiter.hit("1.1.1.1") is None


def test_limite_diario(limiter, reloj):
    for _ in range(20):
        assert limiter.hit("1.1.1.1") is None
        reloj.avanzar(61)  # nunca choca con el límite por minuto

    retry_after = limiter.hit("1.1.1.1")
    assert retry_after is not None and retry_after > 60  # lo frena el límite diario
    reloj.avanzar(retry_after)
    assert limiter.hit("1.1.1.1") is None


def test_las_rechazadas_no_cuentan(limiter, reloj):
    for _ in range(5):
        limiter.hit("1.1.1.1")
    for _ in range(50):
        limiter.hit("1.1.1.1")  # insistir no alarga la espera
    reloj.avanzar(60)
    assert limiter.hit("1.1.1.1") is None


def test_cada_ip_tiene_su_propio_conteo(limiter):
    for _ in range(5):
        limiter.hit("1.1.1.1")
    assert limiter.hit("1.1.1.1") is not None
    assert limiter.hit("2.2.2.2") is None


def test_limpieza_borra_ips_inactivas(limiter, reloj, monkeypatch):
    monkeypatch.setattr(rate_limit_module, "CLEANUP_EVERY", 2)
    limiter.hit("1.1.1.1")
    reloj.avanzar(DIA + 1)
    limiter.hit("2.2.2.2")  # 2.ª llamada: dispara la limpieza
    assert set(limiter._hits) == {"2.2.2.2"}


def test_reset_olvida_todo(limiter):
    for _ in range(5):
        limiter.hit("1.1.1.1")
    limiter.reset()
    assert limiter.hit("1.1.1.1") is None


def test_dependencia_responde_429_con_retry_after(reloj):
    app = FastAPI()
    limiter = RateLimiter([(2, 60)], clock=reloj)

    @app.get("/x", dependencies=[Depends(rate_limit(limiter))])
    def x() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert [client.get("/x").status_code for _ in range(2)] == [200, 200]

    response = client.get("/x")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {"detail": "Too many requests. Please try again later."}
