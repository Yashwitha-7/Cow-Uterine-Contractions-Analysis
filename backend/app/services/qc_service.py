from pathlib import Path

import numpy as np
import pandas as pd


def create_contraction_qc_report(df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    """
    Creates file-level QC report for contraction data.

    This does not delete data. It flags potential issues for review.
    """
    rows = []

    for source_file, group in df.groupby("source_file", sort=False):
        strain = pd.to_numeric(group["strain"], errors="coerce")
        movement = pd.to_numeric(group["movement_flag"], errors="coerce")

        row_count = len(group)
        strain_std = float(strain.std()) if row_count > 1 else 0.0
        strain_min = float(strain.min()) if row_count else np.nan
        strain_max = float(strain.max()) if row_count else np.nan
        movement_flag_count = int((movement == 5).sum())

        warnings = []

        if row_count < 1700:
            warnings.append("partial_or_short_file")

        if row_count > 2300:
            warnings.append("high_row_count_file")

        if strain_std < 0.05:
            warnings.append("flat_or_stuck_strain_signal")

        invalid_movement_values = sorted(
            set(movement.dropna().unique()) - {0, 5}
        )
        if invalid_movement_values:
            warnings.append(f"unexpected_movement_values={invalid_movement_values}")

        if group[["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z", "strain"]].isna().any().any():
            warnings.append("missing_numeric_values")

        if group["qc_warning"].dropna().astype(str).str.len().gt(0).any():
            warnings.append("timestamp_or_file_gap_warning")

        rows.append(
            {
                "source_file": source_file,
                "file_start_time": group["file_start_time"].iloc[0],
                "file_natural_end_time": group["file_natural_end_time"].iloc[0],
                "next_file_start_time": group["next_file_start_time"].iloc[0],
                "row_count": row_count,
                "estimated_sample_period_seconds": group["estimated_sample_period_seconds"].iloc[0],
                "sample_period_source": group["sample_period_source"].iloc[0],
                "file_type": group["file_type"].iloc[0],
                "gap_after_file_seconds": group["gap_after_file_seconds"].iloc[0],
                "strain_min": strain_min,
                "strain_max": strain_max,
                "strain_median": float(strain.median()) if row_count else np.nan,
                "strain_std": strain_std,
                "movement_flag_count": movement_flag_count,
                "qc_warning": "; ".join(sorted(set(warnings))) if warnings else None,
            }
        )

    qc_df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    qc_df.to_csv(output_path, index=False)

    return qc_df


def create_bolus_qc_report(df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    """
    Creates bolus QC report.

    Keeps 10-min and daily records separate using record_type.
    """
    working = df.copy()
    working["timestamp"] = pd.to_datetime(working["timestamp"], errors="coerce")

    rows = []

    for record_type, group in working.groupby("record_type", dropna=False):
        group = group.sort_values("timestamp")
        timestamp_gaps = group["timestamp"].diff().dt.total_seconds() / 60

        warnings = []

        if group["timestamp"].isna().any():
            warnings.append("missing_timestamp")

        if group["timestamp"].duplicated().any():
            warnings.append("duplicate_timestamps")

        if record_type == "10min":
            non_10min = timestamp_gaps.dropna()
            non_10min = non_10min[(non_10min < 9) | (non_10min > 11)]
            if len(non_10min) > 0:
                warnings.append("non_10_minute_spacing")

            if "temperature_c" in group.columns and group["temperature_c"].isna().all():
                warnings.append("missing_raw_temperature")

            if "temp_without_drinkcycles" in group.columns and group["temp_without_drinkcycles"].isna().all():
                warnings.append("missing_temp_without_drinkcycles")

        rows.append(
            {
                "record_type": record_type,
                "row_count": len(group),
                "start_time": group["timestamp"].min(),
                "end_time": group["timestamp"].max(),
                "duplicate_timestamp_count": int(group["timestamp"].duplicated().sum()),
                "missing_timestamp_count": int(group["timestamp"].isna().sum()),
                "max_gap_minutes": float(timestamp_gaps.max()) if timestamp_gaps.notna().any() else None,
                "qc_warning": "; ".join(warnings) if warnings else None,
            }
        )

    qc_df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    qc_df.to_csv(output_path, index=False)

    return qc_df