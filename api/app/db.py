"""Conexión a PostgreSQL con SQLAlchemy, y el rol de PostgreSQL de cada transacción.

Cada transacción de la API empieza con `SET LOCAL ROLE fernwick_app` (o `fernwick_demo` en
las peticiones del demo). Así las políticas de RLS (DESIGN §3) se aplican siempre, sea cual sea
el usuario con el que se abrió la conexión: en Railway ya es fernwick_app; en local es el dueño.
"""

from collections.abc import Iterator

from sqlalchemy import Connection, create_engine, event, pool, text
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from app.config import get_settings

# Roles de PostgreSQL con los que trabaja la API (los crea la migración 0003, DESIGN §3)
APP_ROLE = "fernwick_app"
DEMO_ROLE = "fernwick_demo"
# Lista cerrada: un nombre de rol no puede ir como parámetro enlazado ($1), así que solo se
# aceptan estas constantes (nunca un texto que venga de una petición)
ROLES = (APP_ROLE, DEMO_ROLE)
# Dónde guarda cada sesión su rol (Session.info es un diccionario libre de SQLAlchemy)
ROLE_KEY = "db_role"

# El engine se crea una vez por proceso y administra un pool de conexiones.
# pool_pre_ping: antes de prestar una conexión del pool comprueba que siga viva
# (p. ej. si PostgreSQL se reinició), y si no, abre una nueva.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def set_role(session: Session, role: str) -> None:
    """Fija el rol de PostgreSQL de la sesión: lo llevará cada transacción desde ahora.

    Si ya hay una transacción abierta (p. ej. ya se cargó el usuario), cambia en ese momento.
    """
    if role not in ROLES:
        raise ValueError(f"Rol desconocido: {role!r}")
    session.info[ROLE_KEY] = role
    if session.in_transaction():
        session.execute(text(f"SET LOCAL ROLE {role}"))


@event.listens_for(Session, "after_begin")
def _set_local_role(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    """Al empezar CADA transacción de una sesión con rol, lo primero es SET LOCAL ROLE.

    - LOCAL: el rol dura solo hasta el COMMIT o ROLLBACK. Con un pool de conexiones esto es
      clave: la conexión vuelve al pool sin rol y la próxima petición (quizá de un admin) no
      hereda el del demo.
    - Por eso se repite en cada transacción: si una ruta hace commit() y sigue consultando
      (p. ej. cambiar el estado y luego leer el detalle), la nueva transacción también lo lleva.
    - Las sesiones sin rol (seed-demo, fixtures de las pruebas) no hacen nada: siguen como dueño.
    """
    role = session.info.get(ROLE_KEY)
    if role is not None:
        connection.exec_driver_sql(f"SET LOCAL ROLE {role}")


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, como fernwick_app, que se cierra al terminar.

    Las rutas del panel usan get_db_for_user (app/deps.py), que pasa al rol demo si hace falta.
    """
    with SessionLocal() as session:
        set_role(session, APP_ROLE)
        yield session


def owner_session() -> Session:
    """Sesión como dueño de las tablas (MIGRATIONS_DATABASE_URL), solo para seed-demo.

    El rol de la API no puede escribir filas demo (RLS) y el demo no puede escribir nada.
    NullPool: el comando abre una conexión, trabaja y la cierra; no necesita un pool.
    """
    owner_engine = create_engine(get_settings().owner_database_url, poolclass=pool.NullPool)
    return Session(bind=owner_engine, autoflush=False, expire_on_commit=False)
