"""Modelos de la base de datos.

Importarlos aquí registra todas las tablas en Base.metadata, que es lo que Alembic
compara contra la base para generar migraciones.
"""

from app.models.base import Base
from app.models.note import QuoteNote
from app.models.quote import Quote
from app.models.status_change import QuoteStatusChange
from app.models.user import User

__all__ = ["Base", "Quote", "QuoteNote", "QuoteStatusChange", "User"]
