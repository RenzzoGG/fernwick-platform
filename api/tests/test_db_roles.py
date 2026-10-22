"""Los roles de PostgreSQL y sus permisos, leídos del catálogo (DESIGN §3.1).

Estas pruebas no dependen de datos: preguntan a PostgreSQL qué puede hacer cada rol.
"""

import pytest
from sqlalchemy import text

from app.db import APP_ROLE, DEMO_ROLE

TABLAS = ("quotes", "quote_notes", "quote_status_changes", "users")
TABLAS_COTIZACIONES = ("quotes", "quote_notes", "quote_status_changes")


def scalar(session, sql: str, **params):
    return session.scalar(text(sql), params)


@pytest.mark.parametrize("role", [APP_ROLE, DEMO_ROLE])
def test_ningun_rol_salta_rls(db_session, role):
    # Superusuarios y roles con BYPASSRLS ignoran RLS siempre
    row = db_session.execute(
        text("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = :r"),
        {"r": role},
    ).one()
    assert tuple(row) == (False, False, False, False)


def test_solo_la_app_puede_iniciar_sesion(db_session):
    login = dict(db_session.execute(text(
        "SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname IN (:a, :d)"
    ), {"a": APP_ROLE, "d": DEMO_ROLE}).all())
    assert login == {APP_ROLE: True, DEMO_ROLE: False}


@pytest.mark.parametrize("role", [APP_ROLE, DEMO_ROLE])
def test_ningun_rol_es_dueno_de_nada(db_session, role):
    # El dueño de una tabla salta RLS (salvo FORCE) y puede cambiar o desactivar las políticas
    assert scalar(db_session, "SELECT count(*) FROM pg_class WHERE relowner = CAST(:r AS regrole)", r=role) == 0


def test_la_app_puede_ponerse_el_rol_demo_sin_heredarlo(db_session):
    # INHERIT FALSE: si la app heredara de fernwick_demo, la política *_demo (is_demo) también le
    # aplicaría y vería las filas demo. SET TRUE: puede hacer SET ROLE fernwick_demo.
    row = db_session.execute(text(
        """
        SELECT inherit_option, set_option FROM pg_auth_members
        WHERE roleid = CAST(:d AS regrole) AND member = CAST(:a AS regrole) AND NOT admin_option
        """
    ), {"a": APP_ROLE, "d": DEMO_ROLE}).one()
    assert tuple(row) == (False, True)
    # Y el demo no es miembro de la app (no puede "subir" de rol)
    assert not scalar(db_session, "SELECT pg_has_role(:d, :a, 'MEMBER')", a=APP_ROLE, d=DEMO_ROLE)


@pytest.mark.parametrize("tabla", TABLAS)
def test_rls_activo_y_forzado(db_session, tabla):
    row = db_session.execute(
        text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = CAST(:t AS regclass)"),
        {"t": tabla},
    ).one()
    assert tuple(row) == (True, True)


def permisos(session, role: str, tabla: str) -> set[str]:
    privilegios = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
    return {
        p for p in privilegios
        if scalar(session, "SELECT has_table_privilege(:r, :t, :p)", r=role, t=tabla, p=p)
    }


def test_permisos_de_la_app(db_session):
    assert permisos(db_session, APP_ROLE, "quotes") == {"SELECT", "INSERT"}
    assert permisos(db_session, APP_ROLE, "quote_notes") == {"SELECT", "INSERT"}
    assert permisos(db_session, APP_ROLE, "quote_status_changes") == {"SELECT", "INSERT"}
    assert permisos(db_session, APP_ROLE, "users") == {"SELECT", "INSERT"}
    assert permisos(db_session, APP_ROLE, "alembic_version") == set()


def columnas_con(session, role: str, tabla: str, privilegio: str) -> set[str]:
    columnas = session.scalars(text(
        "SELECT attname FROM pg_attribute WHERE attrelid = CAST(:t AS regclass) AND attnum > 0 AND NOT attisdropped"
    ), {"t": tabla})
    return {
        c for c in columnas
        if scalar(session, "SELECT has_column_privilege(:r, :t, :c, :p)", r=role, t=tabla, c=c, p=privilegio)
    }


def test_la_app_solo_actualiza_las_columnas_que_cambia(db_session):
    assert columnas_con(db_session, APP_ROLE, "quotes", "UPDATE") == {"status", "updated_at"}
    assert columnas_con(db_session, APP_ROLE, "users", "UPDATE") == {"last_login_at", "password_hash"}
    for tabla in ("quote_notes", "quote_status_changes"):
        assert columnas_con(db_session, APP_ROLE, tabla, "UPDATE") == set()


def test_permisos_del_demo(db_session):
    for tabla in TABLAS_COTIZACIONES:
        assert permisos(db_session, DEMO_ROLE, tabla) == {"SELECT"}
        assert columnas_con(db_session, DEMO_ROLE, tabla, "UPDATE") == set()
    # En users solo lee id y email: nunca password_hash
    assert permisos(db_session, DEMO_ROLE, "users") == set()
    assert columnas_con(db_session, DEMO_ROLE, "users", "SELECT") == {"id", "email"}
    assert columnas_con(db_session, DEMO_ROLE, "users", "UPDATE") == set()
    assert permisos(db_session, DEMO_ROLE, "alembic_version") == set()


def test_secuencias(db_session):
    # La app usa nextval() de quotes (honeypot); el demo ninguna
    secuencias = db_session.scalars(text(
        "SELECT oid::regclass::text FROM pg_class WHERE relkind = 'S' AND relnamespace = 'public'::regnamespace"
    )).all()
    for secuencia in secuencias:
        demo = scalar(db_session, "SELECT has_sequence_privilege(:r, :s, 'USAGE')", r=DEMO_ROLE, s=secuencia)
        assert not demo
    assert scalar(db_session, "SELECT has_sequence_privilege(:r, 'quotes_id_seq', 'USAGE')", r=APP_ROLE)


def test_politicas(db_session):
    politicas = {
        (tabla, nombre): (roles, cmd, using, check)
        for tabla, nombre, roles, cmd, using, check in db_session.execute(text(
            "SELECT tablename, policyname, roles, cmd, qual, with_check FROM pg_policies "
            "WHERE schemaname = 'public'"
        ))
    }
    esperado = {}
    for tabla in TABLAS_COTIZACIONES:
        esperado[(tabla, f"{tabla}_app")] = ([APP_ROLE], "ALL", "(NOT is_demo)", "(NOT is_demo)")
        esperado[(tabla, f"{tabla}_demo")] = ([DEMO_ROLE], "SELECT", "is_demo", None)
    esperado[("users", "users_app")] = ([APP_ROLE], "ALL", "true", "true")
    esperado[("users", "users_demo")] = ([DEMO_ROLE], "SELECT", "(role = 'demo'::text)", None)
    assert politicas == esperado
