from pathlib import Path
import shutil

import pandas as pd


def export_clocklab_csv_and_awd(
    input_csv_path: Path,
    output_folder: Path,
    output_stem: str,
    timestamp_col: str,
    value_col: str,
    require_sample_data_col: str | None = None,
) -> dict:
    """
    Creates a simple ClockLab-ready CSV and an AWD copy.

    Output format:
        timestamp,value

    AWD is created by copying the CSV with .awd extension.
    This preserves the CSV backup and follows the ClockLab conversion idea.
    """
    df = pd.read_csv(input_csv_path)

    if timestamp_col not in df.columns:
        raise ValueError(f"{timestamp_col} not found in {input_csv_path.name}")

    if value_col not in df.columns:
        raise ValueError(f"{value_col} not found in {input_csv_path.name}")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    if require_sample_data_col and require_sample_data_col in df.columns:
        df = df[df[require_sample_data_col].astype(bool)]

    out = df[[timestamp_col, value_col]].dropna().copy()
    out = out.rename(columns={timestamp_col: "timestamp", value_col: "value"})

    output_folder.mkdir(parents=True, exist_ok=True)

    csv_path = output_folder / f"{output_stem}.csv"
    awd_path = output_folder / f"{output_stem}.awd"

    out.to_csv(csv_path, index=False)
    shutil.copyfile(csv_path, awd_path)

    return {
        "csv_path": str(csv_path),
        "awd_path": str(awd_path),
        "row_count": len(out),
    }