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

from app.models.base import QUOTE_STATUSES, Base, sql_in

if TYPE_CHECKING:
    from app.models.quote import Quote
    from app.models.user import User


class QuoteStatusChange(Base):
    """Historial de auditoría: cada cambio de estado de una cotización. Solo se inserta."""

    __tablename__ = "quote_status_changes"
    __table_args__ = (
        # Misma FK compuesta que en quote_notes
        ForeignKeyConstraint(
            ["quote_id", "is_demo"], ["quotes.id", "quotes.is_demo"], ondelete="CASCADE"
        ),
        CheckConstraint(sql_in("from_status", QUOTE_STATUSES), name="from_status_valido"),
        CheckConstraint(sql_in("to_status", QUOTE_STATUSES), name="to_status_valido"),
        CheckConstraint("from_status <> to_status", name="estado_distinto"),
        Index("ix_quote_status_changes_quote_id_changed_at", "quote_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    quote_id: Mapped[int] = mapped_column(BigInteger)
    from_status: Mapped[str] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=false())
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    quote: Mapped["Quote"] = relationship(back_populates="status_changes")
    changed_by_user: Mapped["User | None"] = relationship()
