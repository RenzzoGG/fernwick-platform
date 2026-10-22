import logging

import pytest

from app.logging_config import HANDLER_NAME, configure_logging


@pytest.fixture(autouse=True)
def restaurar_logger_app():
    # La configuración del logger es global: se restaura para no afectar a otras pruebas
    logger = logging.getLogger("app")
    level, handlers, propagate = logger.level, list(logger.handlers), logger.propagate
    yield
    logger.setLevel(level)
    logger.handlers[:] = handlers
    logger.propagate = propagate


def test_development_muestra_debug_e_info():
    configure_logging("development")
    logger = logging.getLogger("app.routers.public")  # hereda de "app"
    assert logger.isEnabledFor(logging.DEBUG)
    assert logger.isEnabledFor(logging.INFO)


def test_production_muestra_info_pero_no_debug():
    configure_logging("production")
    logger = logging.getLogger("app.routers.public")
    assert logger.isEnabledFor(logging.INFO)
    assert not logger.isEnabledFor(logging.DEBUG)


def test_no_duplica_handlers_al_llamarse_dos_veces():
    configure_logging("development")
    configure_logging("development")
    # Solo se cuenta el nuestro: pytest agrega sus propios handlers de captura
    nuestros = [h for h in logging.getLogger("app").handlers if h.get_name() == HANDLER_NAME]
    assert len(nuestros) == 1


def test_no_activa_los_logs_de_sqlalchemy():
    configure_logging("development")
    assert not logging.getLogger("sqlalchemy.engine.Engine").isEnabledFor(logging.INFO)
