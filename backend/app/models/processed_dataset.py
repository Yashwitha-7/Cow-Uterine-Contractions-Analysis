from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProcessedDataset(Base):
    """
    Tracks generated processed outputs.

    Examples:
    - contractions_processed
    - contractions_qc_report
    - contractions_preprocessed
    - contraction_events
    - contractions_10min_summary
    - bolus_preprocessed
    - merged_10min
    - clocklab_awd
    """

    __tablename__ = "processed_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    dataset_type: Mapped[str] = mapped_column(String(100), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)