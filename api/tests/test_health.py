from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_health_ok_con_base_de_datos(client):
    # Usa la base real del DATABASE_URL: si PostgreSQL no está corriendo, este test falla
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_503_si_la_base_no_responde(client):
    class SesionCaida:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    # Se reemplaza la dependencia get_db por una sesión que simula la base caída
    app.dependency_overrides[get_db] = lambda: SesionCaida()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "unavailable"}


def test_docs_disponibles_en_desarrollo(client):
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]
