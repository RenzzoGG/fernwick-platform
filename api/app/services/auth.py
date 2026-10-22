"""Lógica de autenticación: crear administradores."""

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password

PASSWORD_MIN = 12
# Tope para no hashear textos gigantes (Argon2 tarda más con entradas más largas)
PASSWORD_MAX = 128


class AdminCreationError(ValueError):
    """Datos inválidos al crear un admin (el mensaje se muestra tal cual en la consola)."""


def find_user_by_email(session: Session, email: str) -> User | None:
    # lower(email) = lower(:email) usa el índice único uq_users_email_lower
    return session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def create_admin(session: Session, email: str, password: str) -> User:
    """Crea un usuario admin. Lanza AdminCreationError si los datos no sirven.

    No hace commit: quien la llama decide (el comando hace commit; las pruebas, rollback).
    """
    try:
        # check_deliverability=False: no consulta DNS (igual que EmailStr en el formulario)
        email = validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise AdminCreationError(f"Email inválido: {exc}") from None
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise AdminCreationError(
            f"La contraseña debe tener entre {PASSWORD_MIN} y {PASSWORD_MAX} caracteres."
        )
    if find_user_by_email(session, email) is not None:
        raise AdminCreationError(f"Ya existe un usuario con el email {email}.")

    user = User(email=email, password_hash=hash_password(password), role="admin")
    session.add(user)
    session.flush()  # asigna el id dentro de la transacción actual
    return user
