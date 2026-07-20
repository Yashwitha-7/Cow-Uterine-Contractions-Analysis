from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


CONTRACTION_COLUMNS = [
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "strain",
    "movement_flag",
    "unknown_1",
    "unknown_2",
]

# Full-hour files normally have about 2000 rows.
# 3600 / 2000 ≈ 1.8 sec/sample.
NORMAL_MIN_ROWS = 1700
NORMAL_MAX_ROWS = 2300
FULL_HOUR_MIN_SECONDS = 3500
FULL_HOUR_MAX_SECONDS = 3700
DEFAULT_SAMPLE_PERIOD_SECONDS = 1.8


@dataclass
class FileTimingInfo:
    source_file: str
    file_order: int
    file_start_time: datetime
    next_file_start_time: datetime | None
    row_count: int
    estimated_sample_period_seconds: float
    sample_period_source: str
    file_duration_seconds: float
    file_natural_end_time: datetime
    gap_after_file_seconds: float | None
    file_type: str
    qc_warning: str | None


def parse_start_time_from_filename(file_path: Path) -> datetime:
    """
    Parses recording start datetime from a TXT filename.

    Expected filename format:
        YYMMDDHHMMSS.txt

    Example:
        260703060001.txt -> 2026-07-03 06:00:01
    """
    stem = file_path.stem

    if len(stem) < 12 or not stem[:12].isdigit():
        raise ValueError(
            f"Cannot parse datetime from filename '{file_path.name}'. "
            "Expected format like YYMMDDHHMMSS.txt."
        )

    return datetime.strptime(stem[:12], "%y%m%d%H%M%S")


def read_numeric_contraction_file(file_path: Path) -> pd.DataFrame:
    """
    Reads one raw TXT file.

    Important device note:
    The header includes 'Time', but Mohammad confirmed this is a device bug.
    The first numeric column is Acc.X, not time.
    """
    df = pd.read_csv(
        file_path,
        sep=r"\s+",
        engine="python",
        skiprows=1,
        header=None,
    )

    if df.empty:
        raise ValueError(f"{file_path.name} is empty.")

    if df.shape[1] != 10:
        raise ValueError(
            f"{file_path.name} has {df.shape[1]} numeric columns. "
            "Expected 10 columns: Acc.X Acc.Y Acc.Z G.X G.Y G.Z Strain Sensor User1 User2."
        )

    df.columns = CONTRACTION_COLUMNS

    for col in CONTRACTION_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _read_file_row_counts(file_paths: list[Path]) -> pd.DataFrame:
    rows = []

    for file_path in sorted(file_paths, key=parse_start_time_from_filename):
        df = read_numeric_contraction_file(file_path)
        rows.append(
            {
                "file_path": file_path,
                "source_file": file_path.name,
                "file_start_time": parse_start_time_from_filename(file_path),
                "row_count": len(df),
            }
        )

    metadata = pd.DataFrame(rows)
    metadata = metadata.sort_values("file_start_time").reset_index(drop=True)
    metadata["file_order"] = metadata.index
    metadata["next_file_start_time"] = metadata["file_start_time"].shift(-1)
    metadata["gap_to_next_start_seconds"] = (
        metadata["next_file_start_time"] - metadata["file_start_time"]
    ).dt.total_seconds()

    return metadata


def _estimate_valid_sample_period(metadata: pd.DataFrame) -> tuple[float, str]:
    """
    Estimates a cow-level sample period from reliable full-hour files only.

    A reliable full-hour file:
    - has normal row count
    - next file starts approximately one hour later
    - gives sample period around the expected ~1.8 sec/sample

    Partial/restarted/final files are excluded.
    """
    candidates = metadata[
        (metadata["row_count"].between(NORMAL_MIN_ROWS, NORMAL_MAX_ROWS))
        & (metadata["gap_to_next_start_seconds"].between(FULL_HOUR_MIN_SECONDS, FULL_HOUR_MAX_SECONDS))
    ].copy()

    if candidates.empty:
        return DEFAULT_SAMPLE_PERIOD_SECONDS, "default_1p8_no_full_hour_candidate"

    candidates["candidate_sample_period"] = (
        candidates["gap_to_next_start_seconds"] / candidates["row_count"]
    )

    candidates = candidates[
        candidates["candidate_sample_period"].between(1.5, 2.2)
    ]

    if candidates.empty:
        return DEFAULT_SAMPLE_PERIOD_SECONDS, "default_1p8_no_reasonable_candidate"

    median_period = float(candidates["candidate_sample_period"].median())
    return median_period, "median_from_full_hour_files"


def _classify_file(
    row: pd.Series,
    sample_period: float,
) -> tuple[str, str | None, datetime, float | None]:
    """
    Classifies files for QC.

    We use the next file only for gap/QC classification, not to stretch the
    current file duration.
    """
    row_count = int(row["row_count"])
    file_start_time = row["file_start_time"]
    next_start = row["next_file_start_time"]

    duration_seconds = row_count * sample_period
    natural_end = file_start_time + timedelta(seconds=duration_seconds)

    gap_after = None
    warnings: list[str] = []

    if pd.notna(next_start):
        gap_after = (next_start - natural_end).total_seconds()

    if row_count < NORMAL_MIN_ROWS:
        file_type = "partial_or_interrupted"
        warnings.append("low_row_count_partial_or_interrupted_file")
    elif row_count > NORMAL_MAX_ROWS:
        file_type = "long_or_high_row_count"
        warnings.append("high_row_count_check_file")
    else:
        file_type = "normal_length"

    if gap_after is not None:
        if gap_after > 120:
            warnings.append("gap_after_file_device_off_or_removed")
        elif gap_after < -120:
            warnings.append("overlap_after_file_check_timestamps")

    if pd.isna(next_start):
        warnings.append("final_file_no_next_boundary")

    qc_warning = "; ".join(warnings) if warnings else None

    return file_type, qc_warning, natural_end, gap_after


def build_file_timing_table(file_paths: list[Path]) -> tuple[list[FileTimingInfo], pd.DataFrame]:
    """
    Builds a file-level timing/QC table for one cow.
    """
    metadata = _read_file_row_counts(file_paths)
    sample_period, sample_period_source = _estimate_valid_sample_period(metadata)

    infos: list[FileTimingInfo] = []
    qc_rows: list[dict] = []

    for _, row in metadata.iterrows():
        row_count = int(row["row_count"])
        file_start_time = row["file_start_time"]
        file_type, qc_warning, natural_end, gap_after = _classify_file(row, sample_period)

        duration_seconds = row_count * sample_period

        info = FileTimingInfo(
            source_file=row["source_file"],
            file_order=int(row["file_order"]),
            file_start_time=file_start_time,
            next_file_start_time=(
                row["next_file_start_time"]
                if pd.notna(row["next_file_start_time"])
                else None
            ),
            row_count=row_count,
            estimated_sample_period_seconds=sample_period,
            sample_period_source=sample_period_source,
            file_duration_seconds=duration_seconds,
            file_natural_end_time=natural_end,
            gap_after_file_seconds=gap_after,
            file_type=file_type,
            qc_warning=qc_warning,
        )

        infos.append(info)

        qc_rows.append(
            {
                "source_file": info.source_file,
                "file_order": info.file_order,
                "file_start_time": info.file_start_time,
                "next_file_start_time": info.next_file_start_time,
                "row_count": info.row_count,
                "estimated_sample_period_seconds": info.estimated_sample_period_seconds,
                "sample_period_source": info.sample_period_source,
                "file_duration_seconds": info.file_duration_seconds,
                "file_natural_end_time": info.file_natural_end_time,
                "gap_after_file_seconds": info.gap_after_file_seconds,
                "file_type": info.file_type,
                "qc_warning": info.qc_warning,
            }
        )

    qc_df = pd.DataFrame(qc_rows)
    return infos, qc_df


def read_single_contraction_file(
    file_path: Path,
    timing_info: FileTimingInfo,
) -> pd.DataFrame:
    """
    Reads one TXT file and creates row-level timestamps.

    The first numeric column is preserved as acc_x.
    A new elapsed_seconds column is generated from sample_index and the
    estimated full-hour sample period.
    """
    df = read_numeric_contraction_file(file_path)

    if len(df) != timing_info.row_count:
        raise ValueError(
            f"Row count mismatch for {file_path.name}. "
            f"Expected {timing_info.row_count}, got {len(df)}."
        )

    df["sample_index"] = np.arange(len(df))
    df["elapsed_seconds"] = df["sample_index"] * timing_info.estimated_sample_period_seconds
    df["timestamp"] = [
        timing_info.file_start_time + timedelta(seconds=float(seconds))
        for seconds in df["elapsed_seconds"]
    ]

    df["source_file"] = timing_info.source_file
    df["file_order"] = timing_info.file_order
    df["file_start_time"] = timing_info.file_start_time
    df["next_file_start_time"] = timing_info.next_file_start_time
    df["file_row_count"] = timing_info.row_count
    df["estimated_sample_period_seconds"] = timing_info.estimated_sample_period_seconds
    df["sample_period_source"] = timing_info.sample_period_source
    df["file_duration_seconds"] = timing_info.file_duration_seconds
    df["file_natural_end_time"] = timing_info.file_natural_end_time
    df["gap_after_file_seconds"] = timing_info.gap_after_file_seconds
    df["file_type"] = timing_info.file_type
    df["qc_warning"] = timing_info.qc_warning

    return df


def combine_contraction_files(cow_id: str, file_paths: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Combines all TXT files for one cow.

    Returns:
        combined row-level contraction dataframe
        file-level QC dataframe
    """
    if not file_paths:
        raise ValueError("No contraction TXT files were provided.")

    timing_infos, qc_df = build_file_timing_table(file_paths)
    info_by_name = {info.source_file: info for info in timing_infos}

    sorted_files = sorted(file_paths, key=parse_start_time_from_filename)
    frames: list[pd.DataFrame] = []

    for file_path in sorted_files:
        frames.append(
            read_single_contraction_file(
                file_path=file_path,
                timing_info=info_by_name[file_path.name],
            )
        )

    combined = pd.concat(frames, ignore_index=True)
    combined.insert(0, "cow_id", cow_id)
    combined["global_sample_index"] = np.arange(len(combined))

    ordered_columns = [
        "cow_id",
        "timestamp",
        "elapsed_seconds",
        "source_file",
        "file_order",
        "sample_index",
        "global_sample_index",
        "file_start_time",
        "next_file_start_time",
        "file_row_count",
        "estimated_sample_period_seconds",
        "sample_period_source",
        "file_duration_seconds",
        "file_natural_end_time",
        "gap_after_file_seconds",
        "file_type",
        "qc_warning",
        "acc_x",
        "acc_y",
        "acc_z",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "strain",
        "movement_flag",
        "unknown_1",
        "unknown_2",
    ]

    qc_df.insert(0, "cow_id", cow_id)

    return combined[ordered_columns], qc_df