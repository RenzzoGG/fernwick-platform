from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import NOTE_BODY_MAX, Base

if TYPE_CHECKING:
    from app.models.quote import Quote
    from app.models.user import User


class QuoteNote(Base):
    """Nota interna que un administrador agrega a una cotización."""

    __tablename__ = "quote_notes"
    __table_args__ = (
        # FK compuesta: la nota apunta a (id, is_demo) de su cotización, así es imposible
        # una nota "real" colgada de una cotización demo o al revés
        ForeignKeyConstraint(
            ["quote_id", "is_demo"], ["quotes.id", "quotes.is_demo"], ondelete="CASCADE"
        ),
        CheckConstraint(f"char_length(body) BETWEEN 1 AND {NOTE_BODY_MAX}", name="body_longitud"),
        Index("ix_quote_notes_quote_id_created_at", "quote_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    quote_id: Mapped[int] = mapped_column(BigInteger)
    # SET NULL: si se borra el usuario, la nota se conserva como "autor eliminado"
    author_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    quote: Mapped["Quote"] = relationship(back_populates="notes")
    author: Mapped["User | None"] = relationship()
