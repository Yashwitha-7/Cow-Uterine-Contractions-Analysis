from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ContractionRecord(Base):
    """
    Stores one processed contraction sensor row.

    Phase 1 stores raw standardized signals only.
    No peak detection, correction, synchronization, or signal filtering is done here.
    """

    __tablename__ = "contraction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)

    source_file: Mapped[str] = mapped_column(String(255))
    file_order: Mapped[int] = mapped_column(Integer)
    sample_index: Mapped[int] = mapped_column(Integer)
    global_sample_index: Mapped[int] = mapped_column(Integer)

    acc_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    acc_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    acc_z: Mapped[float | None] = mapped_column(Float, nullable=True)

    gyro_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyro_z: Mapped[float | None] = mapped_column(Float, nullable=True)

    strain: Mapped[float | None] = mapped_column(Float, nullable=True)

    movement_flag: Mapped[float | None] = mapped_column(Float, nullable=True)
    unknown_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    unknown_2: Mapped[float | None] = mapped_column(Float, nullable=True)