"""Roles fernwick_app y fernwick_demo, permisos mínimos y Row-Level Security (DESIGN §3).

- fernwick_app: el rol con el que trabaja la API. Lee y escribe solo filas reales.
- fernwick_demo: sin login; la API se lo pone con SET LOCAL ROLE en las peticiones del demo.
  Solo lee filas demo y no puede escribir nada.

Los roles son del clúster (no de una base): `fernwick` y `fernwick_test` los comparten. Por eso
se crean solo si no existen y el downgrade NO los borra (la otra base los sigue usando).
Se crean sin contraseña: la de fernwick_app se pone a mano en producción (`\\password` en psql).

Requiere que quien migra sea superusuario o tenga CREATEROLE (DESIGN §3.1).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tablas con la columna is_demo: misma política en las tres
QUOTE_TABLES = ("quotes", "quote_notes", "quote_status_changes")
ALL_TABLES = (*QUOTE_TABLES, "users")


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Roles. NOSUPERUSER NOBYPASSRLS: esos dos atributos saltan RLS siempre.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fernwick_app') THEN
                CREATE ROLE fernwick_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fernwick_demo') THEN
                CREATE ROLE fernwick_demo NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
            -- Si ya existían (otra base, o creados a mano), se comprueba que no salten RLS.
            -- No se corrige solo: quitar esos atributos exige ser superusuario.
            IF EXISTS (
                SELECT FROM pg_roles
                WHERE rolname IN ('fernwick_app', 'fernwick_demo') AND (rolsuper OR rolbypassrls)
            ) THEN
                RAISE EXCEPTION 'fernwick_app/fernwick_demo no pueden ser SUPERUSER ni BYPASSRLS';
            END IF;
        END
        $$
        """
    )

    # 2. Membresías.
    # La API (fernwick_app) puede ponerse el rol demo con SET ROLE; no al revés.
    # INHERIT FALSE es clave: las políticas aplican al rol nombrado Y A SUS MIEMBROS que heredan.
    # Con INHERIT TRUE, la política *_demo (USING is_demo) también le aplicaría a fernwick_app y,
    # sumada con OR a *_app (USING NOT is_demo), la API vería todas las filas.
    op.execute("GRANT fernwick_demo TO fernwick_app WITH INHERIT FALSE, SET TRUE")
    # El dueño (quien migra) puede hacer SET ROLE fernwick_app para las pruebas y para revisar
    # con psql. INHERIT FALSE: no hereda los permisos ni las políticas de fernwick_app.
    op.execute("GRANT fernwick_app TO CURRENT_USER WITH INHERIT FALSE, SET TRUE")

    # 3. Permisos mínimos. Ningún rol tiene DELETE. UPDATE solo en las columnas que la API cambia.
    op.execute("GRANT SELECT, INSERT, UPDATE (status, updated_at) ON quotes TO fernwick_app")
    op.execute("GRANT SELECT, INSERT ON quote_notes, quote_status_changes TO fernwick_app")
    # INSERT: create-admin. UPDATE: el login guarda last_login_at (y el hash si se actualiza)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE (last_login_at, password_hash) ON users TO fernwick_app"
    )
    # nextval() explícito del honeypot (fake_quote_receipt)
    op.execute("GRANT USAGE ON SEQUENCE quotes_id_seq TO fernwick_app")

    op.execute("GRANT SELECT ON quotes, quote_notes, quote_status_changes TO fernwick_demo")
    # Solo las columnas que muestra el detalle (email del autor): nunca password_hash
    op.execute("GRANT SELECT (id, email) ON users TO fernwick_demo")

    # 4. Row-Level Security. FORCE: también aplica al dueño de la tabla (si no tiene BYPASSRLS).
    for table in ALL_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    for table in QUOTE_TABLES:
        # USING filtra lo que se lee o actualiza; WITH CHECK valida lo que se escribe
        op.execute(
            f"CREATE POLICY {table}_app ON {table} FOR ALL TO fernwick_app "
            "USING (NOT is_demo) WITH CHECK (NOT is_demo)"
        )
        op.execute(f"CREATE POLICY {table}_demo ON {table} FOR SELECT TO fernwick_demo USING (is_demo)")

    op.execute(
        "CREATE POLICY users_app ON users FOR ALL TO fernwick_app USING (true) WITH CHECK (true)"
    )
    # El demo solo ve usuarios demo: ni siquiera el email de los admins
    op.execute("CREATE POLICY users_demo ON users FOR SELECT TO fernwick_demo USING (role = 'demo')")


def downgrade() -> None:
    """Downgrade schema."""
    for table in QUOTE_TABLES:
        op.execute(f"DROP POLICY {table}_app ON {table}")
        op.execute(f"DROP POLICY {table}_demo ON {table}")
    op.execute("DROP POLICY users_app ON users")
    op.execute("DROP POLICY users_demo ON users")
    for table in ALL_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {table} FROM fernwick_app, fernwick_demo")
    op.execute("REVOKE ALL ON SEQUENCE quotes_id_seq FROM fernwick_app")
    # Los roles y sus membresías se quedan: son del clúster y la otra base los usa
