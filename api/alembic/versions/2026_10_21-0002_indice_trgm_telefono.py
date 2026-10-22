"""Índice de trigramas sobre los dígitos del teléfono, para la búsqueda del panel.

La búsqueda es `name ILIKE … OR email ILIKE … OR dígitos(phone) LIKE …`. Si una rama del OR
no tiene índice, PostgreSQL recorre toda la tabla y tampoco usa los índices de nombre y email;
con este índice las tres ramas se combinan con un BitmapOr.

Escrita a mano (SQL explícito): autogenerate no compara bien los índices de expresión.
`regexp_replace` es IMMUTABLE, requisito para poder indexar una expresión.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # La expresión debe ser idéntica a PHONE_DIGITS de app/models/quote.py
    op.execute(
        r"CREATE INDEX ix_quotes_phone_digits_trgm ON quotes "
        r"USING gin (regexp_replace(phone, '\D', '', 'g') gin_trgm_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX ix_quotes_phone_digits_trgm")
