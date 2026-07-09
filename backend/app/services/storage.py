from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings


def ensure_data_directories() -> None:
    """
    Ensures the core data directories exist.

    Raw data and processed data are intentionally stored separately.
    Raw data should never be modified.
    """
    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATABASE_DIR.mkdir(parents=True, exist_ok=True)


def get_raw_folder(cow_id: str, data_type: str) -> Path:
    return settings.RAW_DATA_DIR / f"cow_{cow_id}" / data_type


def get_processed_folder(cow_id: str) -> Path:
    return settings.PROCESSED_DATA_DIR / f"cow_{cow_id}"


async def save_upload_file(upload_file: UploadFile, destination: Path) -> Path:
    """
    Saves one uploaded file to disk.

    The file is saved as-is. No raw data modification happens here.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as buffer:
        content = await upload_file.read()
        buffer.write(content)

    return destination