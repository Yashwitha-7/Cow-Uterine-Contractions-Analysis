from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BolusRecord(Base):
    """
    Stores bolus data from both Excel sheets.

    record_type:
    - "10min" for the main 10-minute bolus sheet
    - "daily" for the daily summary sheet

    This keeps Sheet 2 information in the bolus table while preserving
    which sheet each row came from.
    """

    __tablename__ = "bolus_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    record_type: Mapped[str] = mapped_column(String(30), index=True)

    source_file: Mapped[str] = mapped_column(String(255))
    source_sheet: Mapped[str] = mapped_column(String(255))

    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_without_drinkcycles: Mapped[float | None] = mapped_column(Float, nullable=True)
    normal_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    heat_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    rumination_min_24h: Mapped[float | None] = mapped_column(Float, nullable=True)

    water_intake_l: Mapped[float | None] = mapped_column(Float, nullable=True)