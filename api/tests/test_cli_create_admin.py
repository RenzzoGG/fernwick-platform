import sys

import pytest
from sqlalchemy import func, select

from app import cli
from app.models import User
from app.security import verify_password
from app.services.auth import AdminCreationError, create_admin

CLAVE = "una clave bastante larga"


def test_crea_un_admin_con_hash_argon2id(db_session):
    user = create_admin(db_session, "  Renzzo@Example.com ", CLAVE)
    assert user.id is not None
    assert user.role == "admin" and user.is_active
    # email-validator normaliza el dominio a minúsculas y se recortan los espacios
    assert user.email == "Renzzo@example.com"
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(CLAVE, user.password_hash)[0]


def test_rechaza_un_email_repetido_sin_importar_mayusculas(db_session):
    create_admin(db_session, "admin@example.com", CLAVE)
    with pytest.raises(AdminCreationError, match="Ya existe"):
        create_admin(db_session, "ADMIN@example.com", CLAVE)


@pytest.mark.parametrize("clave", ["corta", "x" * 11, "x" * 129])
def test_rechaza_una_contraseña_fuera_de_rango(db_session, clave):
    with pytest.raises(AdminCreationError, match="entre 12 y 128"):
        create_admin(db_session, "admin@example.com", clave)


@pytest.mark.parametrize("email", ["sin-arroba", "a@b", ""])
def test_rechaza_un_email_invalido(db_session, email):
    with pytest.raises(AdminCreationError, match="Email inválido"):
        create_admin(db_session, email, CLAVE)


def test_comando_create_admin(db_session, monkeypatch, capsys):
    # El comando abre su propia sesión: se le da la de la prueba para que todo se revierta
    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": CLAVE)
    monkeypatch.setattr(sys, "argv", ["app.cli", "create-admin", "--email", "jefe@example.com"])
    cli.main()

    assert "Administrador creado: jefe@example.com" in capsys.readouterr().out
    user = db_session.scalar(select(User).where(func.lower(User.email) == "jefe@example.com"))
    assert user is not None and user.role == "admin"


def test_comando_create_admin_si_las_claves_no_coinciden(monkeypatch):
    respuestas = iter([CLAVE, "otra clave distinta"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(respuestas))
    monkeypatch.setattr(sys, "argv", ["app.cli", "create-admin", "--email", "jefe@example.com"])
    with pytest.raises(SystemExit, match="no coinciden"):
        cli.main()
