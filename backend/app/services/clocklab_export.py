from pathlib import Path
import shutil

import pandas as pd


def export_clocklab_csv_and_awd(
    input_csv_path: Path,
    output_folder: Path,
    output_stem: str,
    timestamp_col: str,
    value_col: str,
) -> dict:
    """
    Creates a simple ClockLab-ready CSV and an AWD copy.

    The provided ClockLab instruction says to convert CSV files to .awd.
    We use copy behavior so the CSV is preserved.

    Output format:
        timestamp,value

    If ClockLab later requires a different column format, this function can be
    adjusted in one place.
    """
    df = pd.read_csv(input_csv_path)
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

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