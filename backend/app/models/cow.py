from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Cow(Base):
    """
    Stores cow-level metadata.

    One cow can have contraction uploads, bolus uploads, or both.
    """

    __tablename__ = "cows"

    cow_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    calving_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)