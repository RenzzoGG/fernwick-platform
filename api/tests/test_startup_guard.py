"""En producción la API no arranca si entra a PostgreSQL con un rol que se salta RLS."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import check_login_role, engine


def test_rechaza_el_login_de_las_pruebas():
    # Las pruebas entran como el dueño de las tablas, con BYPASSRLS (DESIGN §3.1)
    with pytest.raises(RuntimeError, match="BYPASSRLS, dueño de las tablas"):
        check_login_role(engine)


def test_en_produccion_no_arranca_con_ese_rol(monkeypatch):
    produccion = main.settings.model_copy(update={"environment": "production"})
    monkeypatch.setattr(main, "settings", produccion)
    # Entrar al TestClient ejecuta el lifespan (el arranque de la API)
    with pytest.raises(RuntimeError, match="fernwick_app"), TestClient(main.app):
        pass


def test_en_desarrollo_arranca(client):
    # En desarrollo la conexión es la del dueño a propósito: cada transacción baja de rol
    assert client.get("/health").status_code == 200
