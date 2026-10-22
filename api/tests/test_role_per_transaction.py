"""SET LOCAL ROLE nunca se "queda pegado" en una conexión del pool.

Se usa un engine propio con UNA sola conexión (pool_size=1): cada sesión nueva recibe
exactamente la misma conexión de PostgreSQL (mismo pg_backend_pid), igual que dos peticiones
seguidas en producción. Solo se hacen SELECT: no queda nada guardado.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import APP_ROLE, DEMO_ROLE, engine, set_role

QUIEN = text("SELECT pg_backend_pid(), current_user, session_user")


@pytest.fixture
def sesiones() -> Iterator[sessionmaker[Session]]:
    # Misma base que la app (la de pruebas), pero con un pool de una sola conexión
    una_conexion = create_engine(engine.url, pool_size=1, max_overflow=0)
    try:
        # Igual que SessionLocal en app/db.py
        yield sessionmaker(bind=una_conexion, autoflush=False, expire_on_commit=False)
    finally:
        una_conexion.dispose()


def quien(session: Session) -> tuple[int, str, str]:
    return tuple(session.execute(QUIEN).one())


class Falla(Exception):
    pass


@pytest.mark.parametrize("final", ["commit", "rollback", "excepcion"])
def test_el_rol_demo_no_pasa_a_la_siguiente_peticion(sesiones, final):
    try:
        with sesiones() as demo:
            set_role(demo, DEMO_ROLE)
            pid, current, login = quien(demo)
            assert current == DEMO_ROLE
            if final == "commit":
                demo.commit()
            elif final == "rollback":
                demo.rollback()
            else:
                raise Falla  # la petición falla a la mitad; la sesión se cierra igual
    except Falla:
        pass

    # Siguiente "petición": misma conexión del pool, y sin rastro del rol demo
    with sesiones() as siguiente:
        pid2, current2, login2 = quien(siguiente)
        assert pid2 == pid
        assert current2 == login2 == login

    # Y una petición de admin corre como fernwick_app
    with sesiones() as admin:
        set_role(admin, APP_ROLE)
        pid3, current3, _ = quien(admin)
        assert (pid3, current3) == (pid, APP_ROLE)


def test_el_rol_se_reaplica_en_cada_transaccion_de_la_misma_sesion(sesiones):
    # Las rutas hacen commit() y siguen consultando (cambiar estado -> leer el detalle)
    with sesiones() as session:
        set_role(session, DEMO_ROLE)
        assert quien(session)[1] == DEMO_ROLE
        session.commit()  # aquí PostgreSQL olvida el SET LOCAL...
        assert quien(session)[1] == DEMO_ROLE  # ...y after_begin lo vuelve a poner
        session.rollback()
        assert quien(session)[1] == DEMO_ROLE


def test_cambiar_de_rol_a_mitad_de_la_transaccion(sesiones):
    # get_current_user carga el usuario como fernwick_app y luego get_db_for_user pasa a demo
    with sesiones() as session:
        set_role(session, APP_ROLE)
        assert quien(session)[1] == APP_ROLE
        set_role(session, DEMO_ROLE)
        assert quien(session)[1] == DEMO_ROLE


def test_rol_desconocido_se_rechaza(sesiones):
    with sesiones() as session, pytest.raises(ValueError):
        set_role(session, "postgres; DROP TABLE quotes")


def test_sin_local_el_rol_si_se_quedaria_pegado(sesiones):
    """Control: con SET ROLE (sin LOCAL) el rol sobrevive al commit y pasa a la siguiente
    petición. Por eso la API usa SET LOCAL."""
    with sesiones() as demo:
        demo.execute(text(f"SET ROLE {DEMO_ROLE}"))
        demo.commit()
    try:
        with sesiones() as siguiente:
            assert quien(siguiente)[1] == DEMO_ROLE  # ¡heredó el rol de la petición anterior!
    finally:
        with sesiones() as limpiar:
            limpiar.execute(text("RESET ROLE"))
            limpiar.commit()
