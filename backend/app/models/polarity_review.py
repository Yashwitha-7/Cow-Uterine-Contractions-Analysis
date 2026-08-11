from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PolarityReview(Base):
    __tablename__ = "polarity_reviews"
    __table_args__ = (
        UniqueConstraint("cow_id", "section_key", name="uq_polarity_review_section"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    section_key: Mapped[str] = mapped_column(String(120))
    continuous_segment_id: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    first_source_file: Mapped[str] = mapped_column(String(255))
    last_source_file: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
