from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Identity, Index, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import EMAIL_CHECK, USER_ROLES, Base, sql_in

# Email del único usuario demo (lo crea `seed-demo` y lo usa POST /v1/auth/demo).
# .example es un dominio reservado: nunca será real.
DEMO_EMAIL = "demo@fernwick.example"

class User(Base):
    """Personas que pueden entrar al panel (administradores y la cuenta demo)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(sql_in("role", USER_ROLES), name="role_valido"),
        CheckConstraint(EMAIL_CHECK.format(column="email"), name="email_formato"),
    )

    # GENERATED ALWAYS AS IDENTITY: PostgreSQL asigna el id y no deja insertarlo a mano
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # `| None` en la anotación = columna que admite NULL
    last_login_at: Mapped[datetime | None]


# Índice único sobre una expresión: impide Admin@x.com y admin@x.com como dos usuarios
# y lo usa el login al buscar con WHERE lower(email) = lower(:email)
Index("uq_users_email_lower", func.lower(User.email), unique=True)
