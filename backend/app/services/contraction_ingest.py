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

NORMAL_MIN_ROWS = 1600
NORMAL_MAX_ROWS = 2400

FULL_HOUR_MIN_SECONDS = 3500
FULL_HOUR_MAX_SECONDS = 3705

REASONABLE_MIN_SAMPLE_PERIOD = 1.4
REASONABLE_MAX_SAMPLE_PERIOD = 2.4

DEFAULT_SAMPLE_PERIOD_SECONDS = 1.8

SEGMENT_SHIFT_THRESHOLD_SECONDS = 0.12


@dataclass
class FileTimingInfo:
    source_file: str
    file_order: int
    file_start_time: datetime
    next_file_start_time: datetime | None
    row_count: int
    estimated_sample_period_seconds: float
    sample_period_source: str
    recording_segment_id: int
    file_duration_seconds: float
    file_natural_end_time: datetime
    gap_after_file_seconds: float | None
    file_type: str
    qc_warning: str | None


def parse_start_time_from_filename(file_path: Path) -> datetime:
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

    Important device rule:
    The TXT header says Time Acc.X Acc.Y..., but the Time header is a device bug.
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


def _read_file_metadata(file_paths: list[Path]) -> pd.DataFrame:
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


def _mark_full_hour_candidates(metadata: pd.DataFrame) -> pd.DataFrame:
    """
    Marks reliable full-hour files and computes candidate sample periods.

    A file is reliable for sample-period estimation only if:
    - row count is in a normal range
    - next file starts about one hour later
    - calculated sample period is reasonable
    """
    metadata = metadata.copy()

    metadata["is_full_hour_candidate"] = (
        metadata["row_count"].between(NORMAL_MIN_ROWS, NORMAL_MAX_ROWS)
        & metadata["gap_to_next_start_seconds"].between(
            FULL_HOUR_MIN_SECONDS,
            FULL_HOUR_MAX_SECONDS,
        )
    )

    metadata["candidate_sample_period_seconds"] = np.nan

    candidate_mask = metadata["is_full_hour_candidate"]

    metadata.loc[candidate_mask, "candidate_sample_period_seconds"] = (
        metadata.loc[candidate_mask, "gap_to_next_start_seconds"]
        / metadata.loc[candidate_mask, "row_count"]
    )

    reasonable_mask = metadata["candidate_sample_period_seconds"].between(
        REASONABLE_MIN_SAMPLE_PERIOD,
        REASONABLE_MAX_SAMPLE_PERIOD,
    )

    metadata["is_full_hour_candidate"] = (
        metadata["is_full_hour_candidate"] & reasonable_mask
    )

    metadata.loc[
        ~metadata["is_full_hour_candidate"],
        "candidate_sample_period_seconds",
    ] = np.nan

    return metadata


def _assign_recording_segments(metadata: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns segment IDs using only reliable full-hour candidate files.

    The segment ID is informational/QC metadata.
    The actual sample period is assigned file-by-file.
    """
    metadata = metadata.copy()
    metadata["recording_segment_id"] = np.nan

    candidates = metadata[metadata["is_full_hour_candidate"]].copy()

    if candidates.empty:
        metadata["recording_segment_id"] = 1
        return metadata

    candidates = candidates.sort_values("file_start_time")

    segment_by_file = {}
    current_segment = 1
    previous_period = None

    for _, row in candidates.iterrows():
        period = float(row["candidate_sample_period_seconds"])

        if previous_period is not None:
            if abs(period - previous_period) > SEGMENT_SHIFT_THRESHOLD_SECONDS:
                current_segment += 1

        segment_by_file[row["source_file"]] = current_segment
        previous_period = period

    metadata.loc[
        metadata["source_file"].isin(segment_by_file.keys()),
        "recording_segment_id",
    ] = metadata["source_file"].map(segment_by_file)

    # Fill non-candidate files using nearby candidate segment.
    metadata["recording_segment_id"] = metadata["recording_segment_id"].ffill()
    metadata["recording_segment_id"] = metadata["recording_segment_id"].bfill()
    metadata["recording_segment_id"] = metadata["recording_segment_id"].fillna(1)
    metadata["recording_segment_id"] = metadata["recording_segment_id"].astype(int)

    return metadata


def _assign_sample_periods(metadata: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns sample period to every file.

    Rule:
    - Reliable full-hour file gets its own calculated sample period.
    - Partial/interrupted file gets previous reliable sample period.
    - If no previous reliable period exists, use next reliable period.
    - If no reliable period exists at all, use default 1.8 sec/sample.
    """
    metadata = metadata.copy()

    metadata["estimated_sample_period_seconds"] = np.nan
    metadata["sample_period_source"] = None

    # Reliable full-hour files use their own direct estimate.
    candidate_mask = metadata["is_full_hour_candidate"]
    metadata.loc[candidate_mask, "estimated_sample_period_seconds"] = metadata.loc[
        candidate_mask,
        "candidate_sample_period_seconds",
    ]
    metadata.loc[candidate_mask, "sample_period_source"] = (
        "direct_from_this_full_hour_file"
    )

    # Partial/non-candidate files use nearest reliable period.
    periods = metadata["estimated_sample_period_seconds"].copy()

    previous_period = periods.ffill()
    next_period = periods.bfill()

    for idx, row in metadata.iterrows():
        if pd.notna(row["estimated_sample_period_seconds"]):
            continue

        if pd.notna(previous_period.iloc[idx]):
            metadata.at[idx, "estimated_sample_period_seconds"] = float(
                previous_period.iloc[idx]
            )
            metadata.at[idx, "sample_period_source"] = (
                "previous_full_hour_file"
            )
        elif pd.notna(next_period.iloc[idx]):
            metadata.at[idx, "estimated_sample_period_seconds"] = float(
                next_period.iloc[idx]
            )
            metadata.at[idx, "sample_period_source"] = "next_full_hour_file"
        else:
            metadata.at[idx, "estimated_sample_period_seconds"] = (
                DEFAULT_SAMPLE_PERIOD_SECONDS
            )
            metadata.at[idx, "sample_period_source"] = (
                "default_1p8_no_full_hour_candidates"
            )

    # An inherited period can make a partial file extend past the timestamp of
    # the next file. When the two filename times define a plausible positive
    # interval, shorten that file's inferred period so its sample boundary
    # lands exactly on the next file start. This preserves every observation
    # while preventing timestamps from running backwards at file boundaries.
    for idx, row in metadata.iterrows():
        gap_seconds = row["gap_to_next_start_seconds"]
        if pd.isna(gap_seconds) or gap_seconds <= 0:
            continue

        row_count = int(row["row_count"])
        assigned_period = float(metadata.at[idx, "estimated_sample_period_seconds"])
        boundary_period = float(gap_seconds) / row_count

        if (
            row_count * assigned_period > float(gap_seconds)
            and REASONABLE_MIN_SAMPLE_PERIOD <= boundary_period <= REASONABLE_MAX_SAMPLE_PERIOD
        ):
            metadata.at[idx, "estimated_sample_period_seconds"] = boundary_period
            metadata.at[idx, "sample_period_source"] = (
                "adjusted_to_next_file_boundary"
            )

    return metadata


def _classify_file(
    row: pd.Series,
    sample_period: float,
) -> tuple[str, str | None, datetime, float | None]:
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
    elif bool(row.get("is_full_hour_candidate", False)):
        file_type = "normal_full_hour_reference"
    else:
        file_type = "normal_length_nonreference"

    if pd.isna(next_start):
        # Final file naturally has no next boundary. Not a warning.
        pass
    elif gap_after is not None:
        if gap_after > 300:
            warnings.append("device_off_gap_after_file")
        elif gap_after < -300:
            warnings.append("possible_overlap_after_file")

    qc_warning = "; ".join(warnings) if warnings else None
    return file_type, qc_warning, natural_end, gap_after


def build_file_timing_table(
    file_paths: list[Path],
) -> tuple[list[FileTimingInfo], pd.DataFrame]:
    metadata = _read_file_metadata(file_paths)
    metadata = _mark_full_hour_candidates(metadata)
    metadata = _assign_recording_segments(metadata)
    metadata = _assign_sample_periods(metadata)

    infos: list[FileTimingInfo] = []
    qc_rows: list[dict] = []

    for _, row in metadata.iterrows():
        sample_period = float(row["estimated_sample_period_seconds"])

        file_type, qc_warning, natural_end, gap_after = _classify_file(
            row,
            sample_period,
        )
        duration_seconds = int(row["row_count"]) * sample_period

        info = FileTimingInfo(
            source_file=row["source_file"],
            file_order=int(row["file_order"]),
            file_start_time=row["file_start_time"],
            next_file_start_time=(
                row["next_file_start_time"]
                if pd.notna(row["next_file_start_time"])
                else None
            ),
            row_count=int(row["row_count"]),
            estimated_sample_period_seconds=sample_period,
            sample_period_source=str(row["sample_period_source"]),
            recording_segment_id=int(row["recording_segment_id"]),
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
                "is_full_hour_candidate": bool(row["is_full_hour_candidate"]),
                "candidate_sample_period_seconds": row[
                    "candidate_sample_period_seconds"
                ],
                "estimated_sample_period_seconds": info.estimated_sample_period_seconds,
                "sample_period_source": info.sample_period_source,
                "recording_segment_id": info.recording_segment_id,
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
    df = read_numeric_contraction_file(file_path)

    if len(df) != timing_info.row_count:
        raise ValueError(
            f"Row count mismatch for {file_path.name}. "
            f"Expected {timing_info.row_count}, got {len(df)}."
        )

    df["sample_index"] = np.arange(len(df))
    df["elapsed_seconds"] = (
        df["sample_index"] * timing_info.estimated_sample_period_seconds
    )

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
    df["recording_segment_id"] = timing_info.recording_segment_id
    df["file_duration_seconds"] = timing_info.file_duration_seconds
    df["file_natural_end_time"] = timing_info.file_natural_end_time
    df["gap_after_file_seconds"] = timing_info.gap_after_file_seconds
    df["file_type"] = timing_info.file_type
    df["qc_warning"] = timing_info.qc_warning

    return df


def combine_contraction_files(
    cow_id: str,
    file_paths: list[Path],
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        "recording_segment_id",
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
