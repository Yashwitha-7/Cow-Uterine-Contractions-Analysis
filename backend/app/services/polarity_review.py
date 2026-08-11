import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


VALID_DECISIONS = {"keep", "flip", "uncertain"}


def find_review_sections(df: pd.DataFrame) -> pd.DataFrame:
    files = (
        df.groupby(["continuous_segment_id", "source_file"], sort=False)
        .agg(
            file_order=("file_order", "first"),
            start_time=("timestamp_corrected", "min"),
            end_time=("timestamp_corrected", "max"),
            possible_inverted=("possible_inverted_signal", "max"),
        )
        .reset_index()
        .sort_values(["continuous_segment_id", "file_order"])
    )
    flagged = files[files["possible_inverted"]].copy()
    if flagged.empty:
        return pd.DataFrame(columns=[
            "section_key", "continuous_segment_id", "start_time", "end_time",
            "first_source_file", "last_source_file", "reason",
        ])

    adjacent = (
        flagged["continuous_segment_id"].ne(flagged["continuous_segment_id"].shift())
        | flagged["file_order"].sub(flagged["file_order"].shift()).ne(1)
    )
    flagged["review_group"] = adjacent.cumsum()
    rows = []
    for _, group in flagged.groupby("review_group", sort=False):
        start = pd.Timestamp(group["start_time"].min())
        end = pd.Timestamp(group["end_time"].max())
        segment = int(group["continuous_segment_id"].iloc[0])
        raw_key = f"{segment}|{start.isoformat()}|{end.isoformat()}"
        rows.append({
            "section_key": hashlib.sha256(raw_key.encode()).hexdigest()[:20],
            "continuous_segment_id": segment,
            "start_time": start,
            "end_time": end,
            "first_source_file": str(group["source_file"].iloc[0]),
            "last_source_file": str(group["source_file"].iloc[-1]),
            "reason": "Negative strain excursions dominate consecutive source files.",
        })
    return pd.DataFrame(rows, columns=[
        "section_key", "continuous_segment_id", "start_time", "end_time",
        "first_source_file", "last_source_file", "reason",
    ])


def apply_reviewed_polarity(df: pd.DataFrame, reviews: list[dict]) -> pd.DataFrame:
    out = df.copy()
    out["polarity_multiplier"] = 1
    out["polarity_review_status"] = "not_flagged"
    times = pd.to_datetime(out["timestamp_corrected"])
    for review in reviews:
        mask = times.between(review["start_time"], review["end_time"])
        out.loc[mask, "polarity_review_status"] = review["status"]
        if review["status"] == "flip":
            out.loc[mask, "polarity_multiplier"] = -1
    out["strain_orientation_corrected"] = (
        out["strain_centered_file"] * out["polarity_multiplier"]
    )
    return out


def downsample_signal(df: pd.DataFrame, limit: int = 2400) -> list[dict]:
    if df.empty:
        return []
    step = max(1, int(np.ceil(len(df) / limit)))
    sample = df.iloc[::step].copy()
    columns = [
        "timestamp_corrected", "strain", "strain_centered_file",
        "strain_orientation_corrected", "acc_magnitude", "gyro_magnitude",
        "movement_artifact_flag", "source_file",
    ]
    sample = sample[[column for column in columns if column in sample.columns]]
    sample = sample.replace({np.nan: None})
    sample["timestamp_corrected"] = pd.to_datetime(
        sample["timestamp_corrected"]
    ).dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
    return sample.to_dict(orient="records")


def write_review_manifest(sections: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sections.to_csv(output_path, index=False)
