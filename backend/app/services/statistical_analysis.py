import json
from pathlib import Path

import numpy as np
import pandas as pd


def _cosinor(timestamp: pd.Series, values: pd.Series) -> dict:
    valid = timestamp.notna() & values.notna()
    if valid.sum() < 12:
        return {"n": int(valid.sum()), "mesor": None, "amplitude": None, "acrophase_hour": None}
    time = pd.to_datetime(timestamp[valid])
    y = pd.to_numeric(values[valid]).to_numpy(dtype=float)
    hours = (time - time.min()).dt.total_seconds().to_numpy() / 3600
    omega = 2 * np.pi / 24
    design = np.column_stack([np.ones(len(hours)), np.cos(omega * hours), np.sin(omega * hours)])
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    amplitude = float(np.hypot(beta[1], beta[2]))
    phase_from_start = float(np.mod(np.arctan2(beta[2], beta[1]) / omega, 24))
    acrophase = float(np.mod(time.min().hour + time.min().minute / 60 + phase_from_start, 24))
    fitted = design @ beta
    variance = float(np.var(y))
    return {
        "n": int(len(y)),
        "mesor": float(beta[0]),
        "amplitude": amplitude,
        "acrophase_hour": acrophase,
        "variance_explained": float(1 - np.var(y - fitted) / variance) if variance > 0 else None,
    }


def generate_statistics(
    cow_id: str,
    processed_folder: Path,
    summary: pd.DataFrame,
    events: pd.DataFrame,
    bolus: pd.DataFrame | None,
) -> list[Path]:
    output_folder = processed_folder / "statistics"
    output_folder.mkdir(parents=True, exist_ok=True)
    summary = summary.copy()
    summary["timestamp"] = pd.to_datetime(summary["timestamp"], errors="coerce")
    summary["period"] = np.where(summary["timestamp"].dt.hour.between(6, 17), "day", "night")
    summary["valid_hours"] = summary["sample_count"].gt(0).astype(float) / 6
    contraction_daily = (
        summary.groupby([summary["timestamp"].dt.date.rename("date"), "period"])
        .agg(
            valid_hours=("valid_hours", "sum"),
            clean_candidate_count=("clean_candidate_peak_count", "sum"),
            strain_range_median=("strain_range", "median"),
            movement_fraction_median=("movement_fraction", "median"),
        )
        .reset_index()
    )
    contraction_daily["clean_candidates_per_valid_hour"] = (
        contraction_daily["clean_candidate_count"] / contraction_daily["valid_hours"].replace(0, np.nan)
    )
    contraction_path = output_folder / f"cow_{cow_id}_contraction_day_night_statistics.csv"
    contraction_daily.to_csv(contraction_path, index=False)

    report = {
        "cow_id": cow_id,
        "definitions": {"day": "06:00-17:59", "night": "18:00-05:59"},
        "interpretation": "Exploratory within-cow descriptive statistics; candidate peaks are not confirmed contractions.",
        "contraction_candidate_cosinor": _cosinor(
            summary["timestamp"], summary["clean_candidate_peak_count"]
        ),
        "event_count_by_label": events["event_label"].value_counts().to_dict() if not events.empty else {},
    }
    paths = [contraction_path]
    if bolus is not None and not bolus.empty:
        ten = bolus[bolus["record_type"] == "10min"].copy()
        ten["timestamp_corrected"] = pd.to_datetime(ten["timestamp_corrected"], errors="coerce")
        ten["period"] = np.where(ten["timestamp_corrected"].dt.hour.between(6, 17), "day", "night")
        bolus_daily = (
            ten.groupby([ten["timestamp_corrected"].dt.date.rename("date"), "period"])
            .agg(
                temperature_median=("temperature_for_analysis", "median"),
                temperature_mean=("temperature_for_analysis", "mean"),
                temperature_std=("temperature_for_analysis", "std"),
                activity_median=("activity", "median"),
                observations=("temperature_for_analysis", "count"),
            )
            .reset_index()
        )
        bolus_path = output_folder / f"cow_{cow_id}_bolus_day_night_statistics.csv"
        bolus_daily.to_csv(bolus_path, index=False)
        report["bolus_temperature_cosinor"] = _cosinor(
            ten["timestamp_corrected"], ten["temperature_for_analysis"]
        )
        paths.append(bolus_path)
    report_path = output_folder / f"cow_{cow_id}_rhythm_summary.json"
    report_path.write_text(json.dumps(report, indent=2))
    paths.append(report_path)
    return paths
