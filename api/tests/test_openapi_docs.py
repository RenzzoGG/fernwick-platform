"""Cada ruta documenta en /openapi.json todos los códigos de error que puede devolver."""

import pytest

from app.main import app

# (método, ruta) -> códigos que deben aparecer documentados
EXPECTED = {
    ("get", "/health"): {"200", "503"},
    ("post", "/v1/public/quotes"): {"201", "413", "422", "429"},
    ("post", "/v1/auth/login"): {"200", "401", "422", "429"},
    ("post", "/v1/auth/demo"): {"200", "404", "429"},
    ("get", "/v1/auth/me"): {"200", "401"},
}


@pytest.fixture(scope="module")
def spec() -> dict:
    return app.openapi()


@pytest.mark.parametrize(("method", "path"), sorted(EXPECTED))
def test_ruta_documenta_sus_errores(spec, method, path):
    assert set(spec["paths"][path][method]["responses"]) == EXPECTED[(method, path)]


def test_todas_las_rutas_estan_en_la_lista(spec):
    # Si se agrega una ruta nueva, hay que decidir qué errores documenta
    rutas = {(method, path) for path, ops in spec["paths"].items() for method in ops}
    assert rutas == set(EXPECTED)


def test_los_errores_tienen_el_formato_detail(spec):
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            for code in ("401", "403", "404", "409", "413", "429"):
                if code in op["responses"] and path != "/health":
                    example = op["responses"][code]["content"]["application/json"]["example"]
                    assert set(example) == {"detail"}, (method, path, code)
