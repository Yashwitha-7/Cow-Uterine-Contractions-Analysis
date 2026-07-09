from datetime import datetime, timedelta
from pathlib import Path

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


def parse_start_time_from_filename(file_path: Path) -> datetime:
    """
    Parses recording start time from contraction TXT filename.

    Expected filename style:
        260624132830.txt

    Interpreted as:
        YY MM DD HH MM SS
        26 06 24 13 28 30
        2026-06-24 13:28:30

    This follows your project note that the start time comes from the TXT filename.
    """
    stem = file_path.stem

    if len(stem) < 12 or not stem[:12].isdigit():
        raise ValueError(
            f"Cannot parse datetime from filename '{file_path.name}'. "
            "Expected format like YYMMDDHHMMSS.txt."
        )

    return datetime.strptime(stem[:12], "%y%m%d%H%M%S")


def read_single_contraction_file(file_path: Path, file_order: int) -> pd.DataFrame:
    """
    Reads one contraction TXT file and returns standardized rows.

    Phase 1 does not modify the signal. It only:
    - reads numeric columns
    - standardizes names
    - adds source file metadata
    - reconstructs timestamps within the hourly file
    """
    file_start = parse_start_time_from_filename(file_path)

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
            f"{file_path.name} has {df.shape[1]} columns. Expected 10 numeric columns."
        )

    df.columns = CONTRACTION_COLUMNS

    row_count = len(df)

    # Each TXT file represents approximately one hour.
    # We compute the interval from the actual row count instead of assuming exactly 1 second.
    sampling_interval_seconds = 3600 / row_count

    df["sample_index"] = range(row_count)
    df["timestamp"] = [
        file_start + timedelta(seconds=i * sampling_interval_seconds)
        for i in range(row_count)
    ]

    df["source_file"] = file_path.name
    df["file_order"] = file_order
    df["estimated_sampling_interval_seconds"] = sampling_interval_seconds

    return df


def combine_contraction_files(cow_id: str, file_paths: list[Path]) -> pd.DataFrame:
    """
    Combines all hourly contraction TXT files for one cow.

    Files are sorted by parsed filename datetime so the final dataset is time ordered.
    """
    sorted_files = sorted(file_paths, key=parse_start_time_from_filename)

    frames: list[pd.DataFrame] = []

    for file_order, file_path in enumerate(sorted_files):
        frame = read_single_contraction_file(file_path, file_order=file_order)
        frames.append(frame)

    if not frames:
        raise ValueError("No contraction TXT files were provided.")

    combined = pd.concat(frames, ignore_index=True)
    combined.insert(0, "cow_id", cow_id)
    combined["global_sample_index"] = range(len(combined))

    ordered_columns = [
        "cow_id",
        "timestamp",
        "source_file",
        "file_order",
        "sample_index",
        "global_sample_index",
        "estimated_sampling_interval_seconds",
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

    return combined[ordered_columns]