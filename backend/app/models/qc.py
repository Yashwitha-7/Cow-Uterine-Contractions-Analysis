from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class QCLog(Base):
    """
    Stores file-level quality-control notes.

    Phase 1 only logs obvious ingestion issues:
    unreadable files, wrong column counts, empty files, or failed parsing.
    """

    __tablename__ = "qc_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cow_id: Mapped[str] = mapped_column(String(50), index=True)
    data_type: Mapped[str] = mapped_column(String(30))
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issue_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(30), default="low")
    message: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)