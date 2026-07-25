from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ContractionEvent(Base):
    """
    Stores candidate contraction peaks detected from the strain signal.

    These are candidate events, not confirmed biological contractions.
    """

    __tablename__ = "contraction_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    peak_time: Mapped[datetime] = mapped_column(DateTime, index=True)

    source_file: Mapped[str] = mapped_column(String(255))
    peak_amplitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    prominence: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    movement_flag_near_peak: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movement_score_near_peak: Mapped[float | None] = mapped_column(Float, nullable=True)

    event_label: Mapped[str] = mapped_column(String(80))