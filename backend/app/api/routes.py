from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.cow import Cow
from app.models.upload import UploadBatch
from app.services.bolus_ingest import read_bolus_excel
from app.services.contraction_ingest import combine_contraction_files
from app.services.database_write import insert_bolus_records, insert_contraction_records
from app.services.storage import get_processed_folder, get_raw_folder, save_upload_file

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "message": "Hoffmann Lab API is running"}


@router.post("/upload/contractions")
async def upload_contractions(
    cow_id: str = Form(...),
    calving_datetime: str | None = Form(None),
    notes: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Uploads hourly contraction TXT files for one cow.

    Phase 1:
    - saves raw TXT files
    - parses start timestamp from each filename
    - combines all files into one processed CSV
    - stores rows in SQLite
    """
    try:
        raw_folder = get_raw_folder(cow_id, "contractions")
        processed_folder = get_processed_folder(cow_id)
        raw_folder.mkdir(parents=True, exist_ok=True)
        processed_folder.mkdir(parents=True, exist_ok=True)

        saved_paths: list[Path] = []

        for file in files:
            if not file.filename.lower().endswith(".txt"):
                raise HTTPException(
                    status_code=400,
                    detail=f"{file.filename} is not a TXT file.",
                )

            destination = raw_folder / file.filename
            saved_path = await save_upload_file(file, destination)
            saved_paths.append(saved_path)

        df = combine_contraction_files(cow_id=cow_id, file_paths=saved_paths)

        processed_file = processed_folder / f"cow_{cow_id}_contractions_processed.csv"
        df.to_csv(processed_file, index=False)

        cow = db.get(Cow, cow_id)
        if cow is None:
            cow = Cow(cow_id=cow_id, notes=notes)
            db.add(cow)
            db.commit()

        inserted_count = insert_contraction_records(db, df)

        upload_batch = UploadBatch(
            cow_id=cow_id,
            data_type="contractions",
            raw_folder_path=str(raw_folder),
            processed_file_path=str(processed_file),
            file_count=len(saved_paths),
            row_count=inserted_count,
            notes=notes,
        )
        db.add(upload_batch)
        db.commit()

        return {
            "message": "Contraction files uploaded and processed successfully.",
            "cow_id": cow_id,
            "file_count": len(saved_paths),
            "row_count": inserted_count,
            "processed_file": str(processed_file),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/upload/bolus")
async def upload_bolus(
    cow_id: str = Form(...),
    calving_datetime: str | None = Form(None),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Uploads one bolus Excel file for one cow.

    Phase 1:
    - saves raw Excel file
    - reads both 10-minute and daily sheets
    - stores both sheet types in one bolus table using record_type
    - creates one processed CSV
    """
    try:
        if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(
                status_code=400,
                detail="Bolus upload must be Excel or CSV.",
            )

        raw_folder = get_raw_folder(cow_id, "bolus")
        processed_folder = get_processed_folder(cow_id)
        raw_folder.mkdir(parents=True, exist_ok=True)
        processed_folder.mkdir(parents=True, exist_ok=True)

        saved_path = await save_upload_file(file, raw_folder / file.filename)

        if saved_path.suffix.lower() in [".xlsx", ".xls"]:
            df = read_bolus_excel(cow_id=cow_id, file_path=saved_path)
        else:
            raise ValueError("CSV bolus support will be added after Excel ingestion is stable.")

        processed_file = processed_folder / f"cow_{cow_id}_bolus_processed.csv"
        df.to_csv(processed_file, index=False)

        cow = db.get(Cow, cow_id)
        if cow is None:
            cow = Cow(cow_id=cow_id, notes=notes)
            db.add(cow)
            db.commit()

        inserted_count = insert_bolus_records(db, df)

        upload_batch = UploadBatch(
            cow_id=cow_id,
            data_type="bolus",
            raw_folder_path=str(raw_folder),
            processed_file_path=str(processed_file),
            file_count=1,
            row_count=inserted_count,
            notes=notes,
        )
        db.add(upload_batch)
        db.commit()

        return {
            "message": "Bolus file uploaded and processed successfully.",
            "cow_id": cow_id,
            "row_count": inserted_count,
            "processed_file": str(processed_file),
            "stored_sheets": sorted(df["record_type"].dropna().unique().tolist()),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/download/{cow_id}/{data_type}")
def download_processed_csv(cow_id: str, data_type: str):
    """
    Downloads processed CSV for a selected cow and data type.
    """
    if data_type not in {"contractions", "bolus"}:
        raise HTTPException(status_code=400, detail="Invalid data type.")

    file_path = (
        settings.PROCESSED_DATA_DIR
        / f"cow_{cow_id}"
        / f"cow_{cow_id}_{data_type}_processed.csv"
    )

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Processed file not found.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="text/csv",
    )