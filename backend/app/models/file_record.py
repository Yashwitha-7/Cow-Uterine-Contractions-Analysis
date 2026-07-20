from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FileRecord(Base):
    """
    Stores every raw file that has been uploaded.

    Used for duplicate upload detection and traceability.
    """

    __tablename__ = "file_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    data_type: Mapped[str] = mapped_column(String(30), index=True)
    source_file: Mapped[str] = mapped_column(String(255), index=True)
    file_hash: Mapped[str] = mapped_column(String(128), index=True)
    raw_file_path: Mapped[str] = mapped_column(Text)

    upload_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "cow_id",
            "data_type",
            "file_hash",
            name="uq_cow_data_file_hash",
        ),
    )