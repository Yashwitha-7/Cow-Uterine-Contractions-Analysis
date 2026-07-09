from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UploadBatch(Base):
    """
    Stores one upload event.

    Example:
    - Cow 6269 contraction TXT folder upload
    - Cow 6263 bolus Excel upload
    """

    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    data_type: Mapped[str] = mapped_column(String(30))  # contractions or bolus

    raw_folder_path: Mapped[str] = mapped_column(Text)
    processed_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_count: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)