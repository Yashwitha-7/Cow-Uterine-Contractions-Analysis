from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.visualization_service import generate_all_visualizations

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


def parse_optional_datetime(value: str | None):
    """
    Converts frontend datetime string into a naive Python datetime for SQLite.
    """
    if not value:
        return None

    cleaned = value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format: {value}",
        ) from exc


def create_or_update_cow(
    db: Session,
    cow_id: str,
    calving_datetime: str | None,
    notes: str | None,
):
    """
    Creates a cow if missing, or updates calving datetime/notes if the cow exists.
    """
    parsed_calving = parse_optional_datetime(calving_datetime)

    cow = db.get(Cow, cow_id)

    if cow is None:
        cow = Cow(
            cow_id=cow_id,
            calving_datetime=parsed_calving,
            notes=notes,
        )
        db.add(cow)
    else:
        if parsed_calving is not None:
            cow.calving_datetime = parsed_calving

        if notes:
            cow.notes = notes

    db.commit()
    db.refresh(cow)

    return cow


def ensure_data_type_not_already_uploaded(
    db: Session,
    cow_id: str,
    data_type: str,
):
    """
    Blocks repeated upload of the same data type for the same cow.

    Example:
    - cow 6263 contractions uploaded once -> cannot upload 6263 contractions again
    - cow 6263 bolus uploaded once -> cannot upload 6263 bolus again
    """
    existing_upload = (
        db.query(UploadBatch)
        .filter(
            UploadBatch.cow_id == cow_id,
            UploadBatch.data_type == data_type,
            UploadBatch.row_count > 0,
        )
        .first()
    )

    if existing_upload:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{data_type.capitalize()} data for cow {cow_id} has already been uploaded. "
                "To re-upload, reset this cow's database records and generated files first."
            ),
        )


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
    allowed_data_types = {
        "contractions",
        "bolus",
        "contractions_timing_qc",
        "contractions_qc",
        "bolus_qc",
        "contractions_preprocessed",
        "contraction_events",
        "contractions_10min_summary",
        "bolus_preprocessed",
        "merged_10min_all_bolus",
        "merged_10min_overlap_only",
    }

    if data_type not in allowed_data_types:
        raise HTTPException(status_code=400, detail="Invalid data type.")

    file_map = {
        "contractions": f"cow_{cow_id}_contractions_processed.csv",
        "bolus": f"cow_{cow_id}_bolus_processed.csv",
        "contractions_timing_qc": f"cow_{cow_id}_contractions_timing_qc.csv",
        "contractions_qc": f"cow_{cow_id}_contractions_qc_report.csv",
        "bolus_qc": f"cow_{cow_id}_bolus_qc_report.csv",
        "contractions_preprocessed": f"cow_{cow_id}_contractions_preprocessed.csv",
        "contraction_events": f"cow_{cow_id}_contraction_events.csv",
        "contractions_10min_summary": f"cow_{cow_id}_contractions_10min_summary.csv",
        "bolus_preprocessed": f"cow_{cow_id}_bolus_preprocessed.csv",
        "merged_10min_all_bolus": f"cow_{cow_id}_merged_10min_all_bolus.csv",
        "merged_10min_overlap_only": f"cow_{cow_id}_merged_10min_overlap_only.csv",
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


@router.post("/visualizations/{cow_id}")
def generate_visualizations(cow_id: str, db: Session = Depends(get_db)):
    processed_folder = get_processed_folder(cow_id)

    if not processed_folder.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No processed folder found for cow {cow_id}. Run upload and Phase 3 first.",
        )

    required_file = processed_folder / f"cow_{cow_id}_contractions_preprocessed.csv"

    if not required_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Phase 3 preprocessed contraction file not found. Run Phase 3 first.",
        )

    try:
        outputs = generate_all_visualizations(
            cow_id=cow_id,
            processed_folder=processed_folder,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "Visualizations generated successfully.",
        "cow_id": cow_id,
        "figure_count": len(outputs),
        "outputs": outputs,
    }


@router.get("/download-figure/{cow_id}/{file_name}")
def download_figure(cow_id: str, file_name: str):
    if "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid file name.")

    file_path = get_processed_folder(cow_id) / "figures" / file_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Figure not found.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="image/png",
    )


@router.post("/upload/contractions")
async def upload_contractions(
    cow_id: str = Form(...),
    calving_datetime: str | None = Form(None),
    notes: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    try:
        ensure_data_type_not_already_uploaded(
            db=db,
            cow_id=cow_id,
            data_type="contractions",
        )

        raw_folder = get_raw_folder(cow_id, "contractions")
        processed_folder = get_processed_folder(cow_id)
        raw_folder.mkdir(parents=True, exist_ok=True)
        processed_folder.mkdir(parents=True, exist_ok=True)

        create_or_update_cow(
            db=db,
            cow_id=cow_id,
            calving_datetime=calving_datetime,
            notes=notes,
        )

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
                raise HTTPException(
                    status_code=400,
                    detail=f"{file.filename} is not a TXT file.",
                )

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

        df, timing_qc_df = combine_contraction_files(
            cow_id=cow_id,
            file_paths=saved_paths,
        )

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
                dataset_type="contractions_timing_qc",
                file_path=str(timing_qc_file),
                row_count=len(timing_qc_df),
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
            "timing_qc_file": str(timing_qc_file),
            "qc_file": str(qc_file),
            "duplicate_files": duplicate_files,
            "estimated_sample_period_summary": {
                "min": float(df["estimated_sample_period_seconds"].min()),
                "median": float(df["estimated_sample_period_seconds"].median()),
                "max": float(df["estimated_sample_period_seconds"].max()),
            },
        }

    except HTTPException:
        raise
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
        ensure_data_type_not_already_uploaded(
            db=db,
            cow_id=cow_id,
            data_type="bolus",
        )

        if not file.filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=400,
                detail="Bolus upload must be Excel for this version.",
            )

        raw_folder = get_raw_folder(cow_id, "bolus")
        processed_folder = get_processed_folder(cow_id)
        raw_folder.mkdir(parents=True, exist_ok=True)
        processed_folder.mkdir(parents=True, exist_ok=True)

        create_or_update_cow(
            db=db,
            cow_id=cow_id,
            calving_datetime=calving_datetime,
            notes=notes,
        )

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
            raise HTTPException(
                status_code=409,
                detail=f"Bolus file for cow {cow_id} has already been uploaded.",
            )

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
        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="bolus_qc_report",
                file_path=str(qc_file),
                row_count=len(qc_df),
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

    except HTTPException:
        raise
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
        raise HTTPException(
            status_code=404,
            detail="Contraction processed CSV not found.",
        )

    contractions_preprocessed_path = (
        processed_folder / f"cow_{cow_id}_contractions_preprocessed.csv"
    )
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

    outputs = {
        "contractions_preprocessed": str(contractions_preprocessed_path),
        "contraction_events": str(events_path),
        "contractions_10min_summary": str(summary_path),
    }

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

    if bolus_csv.exists():
        bolus_preprocessed_path = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"
        merged_all_path = processed_folder / f"cow_{cow_id}_merged_10min_all_bolus.csv"
        merged_overlap_path = processed_folder / f"cow_{cow_id}_merged_10min_overlap_only.csv"

        bolus_df = preprocess_bolus(
            cow_id=cow_id,
            bolus_csv_path=bolus_csv,
            output_path=bolus_preprocessed_path,
            bolus_offset_minutes=bolus_offset_minutes,
        )

        merged_all_df, merged_overlap_df = merge_bolus_and_contractions_10min(
            cow_id=cow_id,
            bolus_preprocessed_df=bolus_df,
            contraction_summary_df=summary_df,
            all_bolus_output_path=merged_all_path,
            overlap_output_path=merged_overlap_path,
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
                dataset_type="merged_10min_all_bolus",
                file_path=str(merged_all_path),
                row_count=len(merged_all_df),
            )
        )
        db.add(
            ProcessedDataset(
                cow_id=cow_id,
                dataset_type="merged_10min_overlap_only",
                file_path=str(merged_overlap_path),
                row_count=len(merged_overlap_df),
            )
        )

        outputs["bolus_preprocessed"] = str(bolus_preprocessed_path)
        outputs["merged_10min_all_bolus"] = str(merged_all_path)
        outputs["merged_10min_overlap_only"] = str(merged_overlap_path)

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
        outputs["contraction_strain_10min_sampled_only"] = (
            export_clocklab_csv_and_awd(
                input_csv_path=summary_10min,
                output_folder=clocklab_folder,
                output_stem=f"cow_{cow_id}_contraction_strain_10min_sampled_only_clocklab",
                timestamp_col="timestamp",
                value_col="strain_mean",
                require_sample_data_col="has_contraction_samples",
            )
        )

        outputs["contraction_peak_count_10min_sampled_only"] = (
            export_clocklab_csv_and_awd(
                input_csv_path=summary_10min,
                output_folder=clocklab_folder,
                output_stem=f"cow_{cow_id}_contraction_peak_count_10min_sampled_only_clocklab",
                timestamp_col="timestamp",
                value_col="candidate_peak_count",
                require_sample_data_col="has_contraction_samples",
            )
        )

    if not outputs:
        raise HTTPException(
            status_code=404,
            detail="No Phase 3 files found for ClockLab export.",
        )

    return {
        "message": "ClockLab CSV and AWD files created.",
        "cow_id": cow_id,
        "outputs": outputs,
    }


@router.get("/files/{cow_id}")
def list_generated_files(cow_id: str):
    processed_folder = get_processed_folder(cow_id)

    if not processed_folder.exists():
        return {"cow_id": cow_id, "files": []}

    file_descriptions = {
        "contractions_processed": {
            "file_name": f"cow_{cow_id}_contractions_processed.csv",
            "phase": "Phase 1 / Phase 2",
            "description": "Corrected full-resolution contraction data with timestamps, file metadata, and raw sensor columns.",
            "download_key": "contractions",
        },
        "contractions_timing_qc": {
            "file_name": f"cow_{cow_id}_contractions_timing_qc.csv",
            "phase": "Phase 2",
            "description": "File-level timing QC showing row counts, sample-period estimates, natural end times, gaps, and recording segments.",
            "download_key": "contractions_timing_qc",
        },
        "contractions_qc": {
            "file_name": f"cow_{cow_id}_contractions_qc_report.csv",
            "phase": "Phase 2",
            "description": "Signal QC report flagging partial files, flat/stuck strain, missing values, and movement flag issues.",
            "download_key": "contractions_qc",
        },
        "bolus_processed": {
            "file_name": f"cow_{cow_id}_bolus_processed.csv",
            "phase": "Phase 1 / Phase 2",
            "description": "Cleaned bolus Excel data including 10-minute records and daily records.",
            "download_key": "bolus",
        },
        "bolus_qc": {
            "file_name": f"cow_{cow_id}_bolus_qc_report.csv",
            "phase": "Phase 2",
            "description": "Bolus QC report checking timestamps, 10-minute spacing, duplicates, and missing temperature values.",
            "download_key": "bolus_qc",
        },
        "contractions_preprocessed": {
            "file_name": f"cow_{cow_id}_contractions_preprocessed.csv",
            "phase": "Phase 3",
            "description": "Full-resolution contraction data with baseline correction, orientation correction, movement score, and flat-signal flags.",
            "download_key": "contractions_preprocessed",
        },
        "contraction_events": {
            "file_name": f"cow_{cow_id}_contraction_events.csv",
            "phase": "Phase 3",
            "description": "Candidate contraction peak events detected from prominence-based strain analysis and labeled using movement/flat-signal flags.",
            "download_key": "contraction_events",
        },
        "contractions_10min_summary": {
            "file_name": f"cow_{cow_id}_contractions_10min_summary.csv",
            "phase": "Phase 3",
            "description": "Ten-minute contraction summaries for bolus synchronization and ClockLab export.",
            "download_key": "contractions_10min_summary",
        },
        "bolus_preprocessed": {
            "file_name": f"cow_{cow_id}_bolus_preprocessed.csv",
            "phase": "Phase 3",
            "description": "Bolus records with corrected timestamps, temperature-for-analysis, rolling temperature, activity, and daily deviation features.",
            "download_key": "bolus_preprocessed",
        },
        "merged_10min_all_bolus": {
            "file_name": f"cow_{cow_id}_merged_10min_all_bolus.csv",
            "phase": "Phase 3",
            "description": "Full bolus timeline merged with contraction data where available. Includes has_contraction_data and overlap flags.",
            "download_key": "merged_10min_all_bolus",
        },
        "merged_10min_overlap_only": {
            "file_name": f"cow_{cow_id}_merged_10min_overlap_only.csv",
            "phase": "Phase 3",
            "description": "Only the time windows where bolus and contraction samples both exist. Best file for multimodal comparison.",
            "download_key": "merged_10min_overlap_only",
        },
    }

    files = []

    for key, info in file_descriptions.items():
        path = processed_folder / info["file_name"]
        if path.exists():
            files.append(
                {
                    "dataset_key": key,
                    "file_name": info["file_name"],
                    "phase": info["phase"],
                    "description": info["description"],
                    "download_key": info["download_key"],
                    "file_path": str(path),
                    "size_bytes": path.stat().st_size,
                }
            )

    clocklab_folder = processed_folder / "clocklab_exports"

    if clocklab_folder.exists():
        for path in sorted(clocklab_folder.glob("*")):
            if path.is_file() and path.suffix.lower() in {".csv", ".awd"}:
                files.append(
                    {
                        "dataset_key": f"clocklab_{path.stem}",
                        "file_name": path.name,
                        "phase": "ClockLab Export",
                        "description": "ClockLab-ready timestamp-value file. CSV is preserved and AWD is the ClockLab extension copy.",
                        "download_key": None,
                        "file_path": str(path),
                        "size_bytes": path.stat().st_size,
                    }
                )

    figures_folder = processed_folder / "figures"

    if figures_folder.exists():

        figure_descriptions = {
            "full_clean_corrected_strain_trace": "Clean full multi-day trace of orientation-corrected strain with only the calving time marker.",
            "daily_contraction_strain_rows": "Daily row-wise plot of 10-minute mean corrected contraction strain. Each row is one day.",
            "actogram_candidate_peak_count": "24-hour actogram heatmap of all detected candidate peak counts per 10-minute bin.",
            "actogram_clean_candidate_peak_count": "24-hour actogram heatmap of clean contraction-candidate peak counts after movement and bad-signal filtering.",
            "actogram_strain_range": "24-hour actogram heatmap of corrected strain range per 10-minute bin.",
            "actogram_movement_fraction": "24-hour actogram heatmap of movement artifact fraction per 10-minute bin.",
            "double_actogram_candidate_peak_count": "48-hour double-plotted actogram of candidate peak count.",
            "daily_motion_sensor_rows": "Daily row-wise accelerometer and gyroscope magnitude plots derived from Acc.X/Y/Z and G.X/Y/Z.",
            "signal_correction_review": "QC plot comparing raw strain, file-centered strain, and orientation-corrected strain for selected files.",
            "bolus_temperature_actogram": "24-hour actogram heatmap of bolus temperature for analysis.",
            "daily_bolus_temperature_rows": "Daily row-wise bolus temperature plot.",
            "parallel_bolus_contraction_daily": "Parallel daily rows comparing bolus temperature and 10-minute contraction strain with calving marker.",
        }

        for path in sorted(figures_folder.glob("*.png")):
            description = "Generated visualization figure."

            for key, value in figure_descriptions.items():
                if key in path.stem:
                    description = value
                    break

            files.append(
                {
                    "dataset_key": f"figure_{path.stem}",
                    "file_name": path.name,
                    "phase": "Visualization",
                    "description": description,
                    "download_key": None,
                    "file_path": str(path),
                    "size_bytes": path.stat().st_size,
                }
            )           

    return {"cow_id": cow_id, "files": files}


@router.get("/download/{cow_id}/{data_type}")
def download_processed_csv(cow_id: str, data_type: str):
    file_map = {
        "contractions": f"cow_{cow_id}_contractions_processed.csv",
        "bolus": f"cow_{cow_id}_bolus_processed.csv",
        "contractions_timing_qc": f"cow_{cow_id}_contractions_timing_qc.csv",
        "contractions_qc": f"cow_{cow_id}_contractions_qc_report.csv",
        "bolus_qc": f"cow_{cow_id}_bolus_qc_report.csv",
        "contractions_preprocessed": f"cow_{cow_id}_contractions_preprocessed.csv",
        "contraction_events": f"cow_{cow_id}_contraction_events.csv",
        "contractions_10min_summary": f"cow_{cow_id}_contractions_10min_summary.csv",
        "bolus_preprocessed": f"cow_{cow_id}_bolus_preprocessed.csv",
        "merged_10min_all_bolus": f"cow_{cow_id}_merged_10min_all_bolus.csv",
        "merged_10min_overlap_only": f"cow_{cow_id}_merged_10min_overlap_only.csv",
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


@router.get("/download-clocklab/{cow_id}/{file_name}")
def download_clocklab_file(cow_id: str, file_name: str):
    if "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid file name.")

    file_path = get_processed_folder(cow_id) / "clocklab_exports" / file_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ClockLab file not found.")

    media_type = (
        "text/csv"
        if file_path.suffix.lower() == ".csv"
        else "application/octet-stream"
    )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
    )