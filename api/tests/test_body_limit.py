from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.main import MAX_BODY_BYTES
from app.middleware import BodySizeLimitMiddleware

# App mínima solo para probar el middleware: un endpoint que lee el cuerpo completo
mini_app = FastAPI()
mini_app.add_middleware(BodySizeLimitMiddleware, max_bytes=100)


@mini_app.post("/eco")
async def eco(request: Request) -> dict[str, int]:
    return {"bytes": len(await request.body())}


mini_client = TestClient(mini_app)


def partes(total: int, tam: int = 30):
    # Un generador hace que httpx envíe el cuerpo por partes, sin Content-Length
    for inicio in range(0, total, tam):
        yield b"x" * min(tam, total - inicio)


def test_cuerpo_dentro_del_limite_pasa():
    response = mini_client.post("/eco", content=b"x" * 100)
    assert response.status_code == 200
    assert response.json() == {"bytes": 100}


def test_cuerpo_grande_con_content_length_da_413():
    response = mini_client.post("/eco", content=b"x" * 101)
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large"}


def test_cuerpo_grande_sin_content_length_da_413():
    response = mini_client.post("/eco", content=partes(500))
    assert "content-length" not in response.request.headers
    assert response.status_code == 413


def test_cuerpo_por_partes_dentro_del_limite_pasa():
    response = mini_client.post("/eco", content=partes(90))
    assert response.status_code == 200
    assert response.json() == {"bytes": 90}


def test_app_real_limita_a_10_kb(client):
    assert MAX_BODY_BYTES == 10 * 1024
    # Aún sin endpoint que lea el cuerpo, el middleware de la app real corta por Content-Length
    response = client.post("/health", content=b"x" * (MAX_BODY_BYTES + 1))
    assert response.status_code == 413
