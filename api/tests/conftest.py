from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    # TestClient llama a la app en el mismo proceso, sin levantar un servidor
    with TestClient(app) as test_client:
        yield test_client
    # Si un test reemplazó dependencias, se restauran para no afectar a los demás
    app.dependency_overrides.clear()
