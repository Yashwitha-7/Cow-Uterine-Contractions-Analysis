from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.bolus import BolusRecord
from app.models.contraction import ContractionRecord
from app.models.contraction_event import ContractionEvent
from app.models.cow import Cow
from app.models.file_record import FileRecord
from app.models.processed_dataset import ProcessedDataset
from app.models.qc import QCLog
from app.models.upload import UploadBatch
from app.services.bolus_ingest import read_bolus_excel
from app.services.clocklab_export import export_clocklab_csv_and_awd
from app.services.contraction_ingest import combine_contraction_files
from app.services.database_write import insert_bolus_records, insert_contraction_records
from app.services.file_hashing import calculate_file_sha256
from app.services.phase3_processing import (
    create_contraction_10min_summary,
    detect_contraction_events,
    merge_bolus_and_contractions_10min,
    preprocess_bolus,
    preprocess_contractions,
)
from app.services.qc_service import create_bolus_qc_report, create_contraction_qc_report
from app.services.storage import get_processed_folder, get_raw_folder, save_upload_file

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "message": "Hoffmann Lab API is running"}


@router.get("/cows")
def list_cows(db: Session = Depends(get_db)):
    cows = db.query(Cow).all()
    results = []

    for cow in cows:
        contraction_count = (
            db.query(func.count(ContractionRecord.id))
            .filter(ContractionRecord.cow_id == cow.cow_id)
            .scalar()
        )
        bolus_count = (
            db.query(func.count(BolusRecord.id))
            .filter(BolusRecord.cow_id == cow.cow_id)
            .scalar()
        )

        results.append(
            {
                "cow_id": cow.cow_id,
                "calving_datetime": cow.calving_datetime,
                "notes": cow.notes,
                "contraction_rows": contraction_count,
                "bolus_rows": bolus_count,
                "has_contractions": contraction_count > 0,
                "has_bolus": bolus_count > 0,
            }
        )

    return results


@router.get("/uploads")
def list_uploads(db: Session = Depends(get_db)):
    uploads = db.query(UploadBatch).order_by(UploadBatch.created_at.desc()).all()

    return [
        {
            "id": item.id,
            "cow_id": item.cow_id,
            "data_type": item.data_type,
            "file_count": item.file_count,
            "row_count": item.row_count,
            "raw_folder_path": item.raw_folder_path,
            "processed_file_path": item.processed_file_path,
            "notes": item.notes,
            "created_at": item.created_at,
        }
        for item in uploads
    ]


@router.get("/qc-logs")
def list_qc_logs(db: Session = Depends(get_db)):
    logs = db.query(QCLog).order_by(QCLog.created_at.desc()).limit(500).all()

    return [
        {
            "id": log.id,
            "cow_id": log.cow_id,
            "data_type": log.data_type,
            "source_file": log.source_file,
            "issue_type": log.issue_type,
            "severity": log.severity,
            "message": log.message,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/preview/{cow_id}/{data_type}")
def preview_processed_data(
    cow_id: str,
    data_type: str,
    n_rows: int = Query(default=50, ge=5, le=500),
):
    if data_type not in {"contractions", "bolus", "contractions_preprocessed", "contraction_events", "contractions_10min_summary", "bolus_preprocessed", "merged_10min"}:
        raise HTTPException(status_code=400, detail="Invalid data type.")

    file_map = {
        "contractions": f"cow_{cow_id}_contractions_processed.csv",
        "bolus": f"cow_{cow_id}_bolus_processed.csv",
        "contractions_preprocessed": f"cow_{cow_id}_contractions_preprocessed.csv",
        "contraction_events": f"cow_{cow_id}_contraction_events.csv",
        "contractions_10min_summary": f"cow_{cow_id}_contractions_10min_summary.csv",
        "bolus_preprocessed": f"cow_{cow_id}_bolus_preprocessed.csv",
        "merged_10min": f"cow_{cow_id}_merged_10min.csv",
    }

    file_path = settings.PROCESSED_DATA_DIR / f"cow_{cow_id}" / file_map[data_type]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Processed file not found.")

    df = pd.read_csv(file_path)
    preview = df.head(n_rows).fillna("").to_dict(orient="records")

    return {
        "cow_id": cow_id,
        "data_type": data_type,
        "file_path": str(file_path),
        "row_count": len(df),
        "columns": df.columns.tolist(),
        "preview": preview,
    }


@router.post("/upload/contractions")
async def upload_contractions(
    cow_id: str = Form(...),
    calving_datetime: str | None = Form(None),
    notes: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    try:
        raw_folder = get_raw_folder(cow_id, "contractions")
        processed_folder = get_processed_folder(cow_id)
        raw_folder.mkdir(parents=True, exist_ok=True)
        processed_folder.mkdir(parents=True, exist_ok=True)

        cow = db.get(Cow, cow_id)
        if cow is None:
            cow = Cow(cow_id=cow_id, notes=notes)
            db.add(cow)
            db.commit()

        saved_paths: list[Path] = []
        duplicate_files: list[str] = []

        upload_batch = UploadBatch(
            cow_id=cow_id,
            data_type="contractions",
            raw_folder_path=str(raw_folder),
            processed_file_path=None,
            file_count=0,
            row_count=0,
            notes=notes,
        )
        db.add(upload_batch)
        db.commit()
        db.refresh(upload_batch)

        for file in files:
            if not file.filename.lower().endswith(".txt"):
                raise HTTPException(status_code=400, detail=f"{file.filename} is not a TXT file.")

            destination = raw_folder / file.filename
            saved_path = await save_upload_file(file, destination)
            file_hash = calculate_file_sha256(saved_path)

            existing = (
                db.query(FileRecord)
                .filter(
                    FileRecord.cow_id == cow_id,
                    FileRecord.data_type == "contractions",
                    FileRecord.file_hash == file_hash,
                )
                .first()
            )

            if existing:
                duplicate_files.append(file.filename)
                continue

            db.add(
                FileRecord(
                    cow_id=cow_id,
                    data_type="contractions",
                    source_file=file.filename,
                    file_hash=file_hash,
                    raw_file_path=str(saved_path),
                    upload_batch_id=upload_batch.id,
                )
            )
            saved_paths.append(saved_path)

        db.commit()

        if not saved_paths:
            return {
                "message": "No new contraction files processed because all uploaded files were duplicates.",
                "cow_id": cow_id,
                "duplicate_files": duplicate_files,
            }

        df, timing_qc_df = combine_contraction_files(cow_id=cow_id, file_paths=saved_paths)

        processed_file = processed_folder / f"cow_{cow_id}_contractions_processed.csv"
        df.to_csv(processed_file, index=False)

        timing_qc_file = processed_folder / f"cow_{cow_id}_contractions_timing_qc.csv"
        timing_qc_df.to_csv(timing_qc_file, index=False)

        qc_file = processed_folder / f"cow_{cow_id}_contractions_qc_report.csv"
        qc_df = create_contraction_qc_report(df, qc_file)

        inserted_count = insert_contraction_records(db, df)

        upload_batch.processed_file_path = str(processed_file)
        upload_batch.file_count = len(saved_paths)
        upload_batch.row_count = inserted_count
        db.add(upload_batch)

        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="contractions_processed",
                file_path=str(processed_file),
                row_count=len(df),
            )
        )
        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="contractions_qc_report",
                file_path=str(qc_file),
                row_count=len(qc_df),
            )
        )

        for _, row in qc_df.iterrows():
            if pd.notna(row.get("qc_warning")):
                db.add(
                    QCLog(
                        cow_id=cow_id,
                        data_type="contractions",
                        source_file=row["source_file"],
                        issue_type="file_qc_warning",
                        severity="medium",
                        message=str(row["qc_warning"]),
                    )
                )

        db.commit()

        return {
            "message": "Contraction files uploaded and processed successfully.",
            "cow_id": cow_id,
            "file_count": len(saved_paths),
            "row_count": inserted_count,
            "processed_file": str(processed_file),
            "qc_file": str(qc_file),
            "duplicate_files": duplicate_files,
            "estimated_sample_period_seconds": float(df["estimated_sample_period_seconds"].median()),
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
    try:
        if not file.filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Bolus upload must be Excel for this version.")

        raw_folder = get_raw_folder(cow_id, "bolus")
        processed_folder = get_processed_folder(cow_id)
        raw_folder.mkdir(parents=True, exist_ok=True)
        processed_folder.mkdir(parents=True, exist_ok=True)

        cow = db.get(Cow, cow_id)
        if cow is None:
            cow = Cow(cow_id=cow_id, notes=notes)
            db.add(cow)
            db.commit()

        saved_path = await save_upload_file(file, raw_folder / file.filename)
        file_hash = calculate_file_sha256(saved_path)

        existing = (
            db.query(FileRecord)
            .filter(
                FileRecord.cow_id == cow_id,
                FileRecord.data_type == "bolus",
                FileRecord.file_hash == file_hash,
            )
            .first()
        )

        if existing:
            return {
                "message": "Bolus file was already uploaded. Duplicate skipped.",
                "cow_id": cow_id,
                "duplicate_file": file.filename,
            }

        df = read_bolus_excel(cow_id=cow_id, file_path=saved_path)

        processed_file = processed_folder / f"cow_{cow_id}_bolus_processed.csv"
        df.to_csv(processed_file, index=False)

        qc_file = processed_folder / f"cow_{cow_id}_bolus_qc_report.csv"
        qc_df = create_bolus_qc_report(df, qc_file)

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
        db.refresh(upload_batch)

        db.add(
            FileRecord(
                cow_id=cow_id,
                data_type="bolus",
                source_file=file.filename,
                file_hash=file_hash,
                raw_file_path=str(saved_path),
                upload_batch_id=upload_batch.id,
            )
        )

        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="bolus_processed",
                file_path=str(processed_file),
                row_count=len(df),
            )
        )

        for _, row in qc_df.iterrows():
            if pd.notna(row.get("qc_warning")):
                db.add(
                    QCLog(
                        cow_id=cow_id,
                        data_type="bolus",
                        source_file=file.filename,
                        issue_type="bolus_qc_warning",
                        severity="medium",
                        message=str(row["qc_warning"]),
                    )
                )

        db.commit()

        return {
            "message": "Bolus file uploaded and processed successfully.",
            "cow_id": cow_id,
            "row_count": inserted_count,
            "processed_file": str(processed_file),
            "qc_file": str(qc_file),
            "stored_sheets": sorted(df["record_type"].dropna().unique().tolist()),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/process/phase3/{cow_id}")
def run_phase3_processing(
    cow_id: str,
    patch_offset_minutes: float = 0.0,
    bolus_offset_minutes: float = 0.0,
    db: Session = Depends(get_db),
):
    processed_folder = get_processed_folder(cow_id)

    contraction_csv = processed_folder / f"cow_{cow_id}_contractions_processed.csv"
    bolus_csv = processed_folder / f"cow_{cow_id}_bolus_processed.csv"

    if not contraction_csv.exists():
        raise HTTPException(status_code=404, detail="Contraction processed CSV not found.")

    contractions_preprocessed_path = processed_folder / f"cow_{cow_id}_contractions_preprocessed.csv"
    events_path = processed_folder / f"cow_{cow_id}_contraction_events.csv"
    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"

    preprocessed_df = preprocess_contractions(
        cow_id=cow_id,
        processed_csv_path=contraction_csv,
        output_path=contractions_preprocessed_path,
        patch_offset_minutes=patch_offset_minutes,
    )

    events_df = detect_contraction_events(
        cow_id=cow_id,
        preprocessed_df=preprocessed_df,
        output_path=events_path,
    )

    summary_df = create_contraction_10min_summary(
        cow_id=cow_id,
        preprocessed_df=preprocessed_df,
        events_df=events_df,
        output_path=summary_path,
    )

    db.add(
        ProcessedDataset(
            cow_id=cow_id,
            dataset_type="contractions_preprocessed",
            file_path=str(contractions_preprocessed_path),
            row_count=len(preprocessed_df),
        )
    )
    db.add(
        ProcessedDataset(
            cow_id=cow_id,
            dataset_type="contraction_events",
            file_path=str(events_path),
            row_count=len(events_df),
        )
    )
    db.add(
        ProcessedDataset(
            cow_id=cow_id,
            dataset_type="contractions_10min_summary",
            file_path=str(summary_path),
            row_count=len(summary_df),
        )
    )

    for _, row in events_df.iterrows():
        db.add(
            ContractionEvent(
                cow_id=cow_id,
                peak_time=pd.to_datetime(row["peak_time"]),
                source_file=row["source_file"],
                peak_amplitude=row["peak_amplitude"],
                prominence=row["prominence"],
                width_seconds=row["width_seconds"],
                movement_flag_near_peak=int(row["movement_flag_near_peak"]),
                movement_score_near_peak=row["movement_score_near_peak"],
                event_label=row["event_label"],
            )
        )

    outputs = {
        "contractions_preprocessed": str(contractions_preprocessed_path),
        "contraction_events": str(events_path),
        "contractions_10min_summary": str(summary_path),
    }

    if bolus_csv.exists():
        bolus_preprocessed_path = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"
        merged_path = processed_folder / f"cow_{cow_id}_merged_10min.csv"

        bolus_df = preprocess_bolus(
            cow_id=cow_id,
            bolus_csv_path=bolus_csv,
            output_path=bolus_preprocessed_path,
            bolus_offset_minutes=bolus_offset_minutes,
        )

        merged_df = merge_bolus_and_contractions_10min(
            cow_id=cow_id,
            bolus_preprocessed_df=bolus_df,
            contraction_summary_df=summary_df,
            output_path=merged_path,
        )

        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="bolus_preprocessed",
                file_path=str(bolus_preprocessed_path),
                row_count=len(bolus_df),
            )
        )
        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="merged_10min",
                file_path=str(merged_path),
                row_count=len(merged_df),
            )
        )

        outputs["bolus_preprocessed"] = str(bolus_preprocessed_path)
        outputs["merged_10min"] = str(merged_path)

    db.commit()

    return {
        "message": "Phase 3 preprocessing completed.",
        "cow_id": cow_id,
        "outputs": outputs,
        "candidate_event_count": len(events_df),
    }


@router.post("/export/clocklab/{cow_id}")
def export_clocklab_files(cow_id: str):
    processed_folder = get_processed_folder(cow_id)
    clocklab_folder = processed_folder / "clocklab_exports"

    outputs = {}

    bolus_preprocessed = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"
    summary_10min = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"

    if bolus_preprocessed.exists():
        outputs["bolus_temp_without_drinkcycles"] = export_clocklab_csv_and_awd(
            input_csv_path=bolus_preprocessed,
            output_folder=clocklab_folder,
            output_stem=f"cow_{cow_id}_bolus_temp_without_drinkcycles_clocklab",
            timestamp_col="timestamp_corrected",
            value_col="temp_without_drinkcycles",
        )

        outputs["bolus_temperature_for_analysis"] = export_clocklab_csv_and_awd(
            input_csv_path=bolus_preprocessed,
            output_folder=clocklab_folder,
            output_stem=f"cow_{cow_id}_bolus_temperature_for_analysis_clocklab",
            timestamp_col="timestamp_corrected",
            value_col="temperature_for_analysis",
        )

    if summary_10min.exists():
        outputs["contraction_strain_10min"] = export_clocklab_csv_and_awd(
            input_csv_path=summary_10min,
            output_folder=clocklab_folder,
            output_stem=f"cow_{cow_id}_contraction_strain_10min_clocklab",
            timestamp_col="timestamp",
            value_col="strain_mean",
        )

        outputs["contraction_peak_count_10min"] = export_clocklab_csv_and_awd(
            input_csv_path=summary_10min,
            output_folder=clocklab_folder,
            output_stem=f"cow_{cow_id}_contraction_peak_count_10min_clocklab",
            timestamp_col="timestamp",
            value_col="candidate_peak_count",
        )

    if not outputs:
        raise HTTPException(status_code=404, detail="No Phase 3 files found for ClockLab export.")

    return {
        "message": "ClockLab CSV and AWD files created.",
        "cow_id": cow_id,
        "outputs": outputs,
    }


@router.get("/download/{cow_id}/{data_type}")
def download_processed_csv(cow_id: str, data_type: str):
    file_map = {
        "contractions": f"cow_{cow_id}_contractions_processed.csv",
        "bolus": f"cow_{cow_id}_bolus_processed.csv",
        "contractions_qc": f"cow_{cow_id}_contractions_qc_report.csv",
        "bolus_qc": f"cow_{cow_id}_bolus_qc_report.csv",
        "contractions_preprocessed": f"cow_{cow_id}_contractions_preprocessed.csv",
        "contraction_events": f"cow_{cow_id}_contraction_events.csv",
        "contractions_10min_summary": f"cow_{cow_id}_contractions_10min_summary.csv",
        "bolus_preprocessed": f"cow_{cow_id}_bolus_preprocessed.csv",
        "merged_10min": f"cow_{cow_id}_merged_10min.csv",
    }

    if data_type not in file_map:
        raise HTTPException(status_code=400, detail="Invalid data type.")

    file_path = settings.PROCESSED_DATA_DIR / f"cow_{cow_id}" / file_map[data_type]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Processed file not found.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="text/csv",
    )