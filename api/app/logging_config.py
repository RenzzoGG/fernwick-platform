"""Configuración de los logs de la app según ENVIRONMENT."""

import logging
import sys

# Formato simple: hora, nivel, módulo y mensaje
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# Nombre de nuestro handler, para reconocerlo entre otros (p. ej. los que agrega pytest)
HANDLER_NAME = "fernwick"


def configure_logging(environment: str) -> None:
    """Configura el logger "app" (y por herencia todos los `logging.getLogger(__name__)` de app.*).

    No se toca el logger raíz: con la raíz en INFO, SQLAlchemy imprimiría cada consulta SQL.
    Uvicorn configura sus propios loggers (uvicorn, uvicorn.access) por separado.
    """
    logger = logging.getLogger("app")
    # development: todo, incluido DEBUG. test/production: desde INFO (honeypot, logins fallidos)
    logger.setLevel(logging.DEBUG if environment == "development" else logging.INFO)
    # Idempotente: si se llama dos veces, no se duplican las líneas
    if not any(h.get_name() == HANDLER_NAME for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.set_name(HANDLER_NAME)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    # Sin propagate: los mensajes no se repiten en el logger raíz
    logger.propagate = False
