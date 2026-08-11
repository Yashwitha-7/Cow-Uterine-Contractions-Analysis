from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, peak_widths


def _rolling_window_samples(sample_period_seconds: float, window_seconds: float) -> int:
    samples = int(round(window_seconds / sample_period_seconds))
    return max(samples, 3)


def _add_continuous_segment_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Split rows whenever time reverses or a real recording gap occurs."""
    out = df.sort_values(["timestamp_corrected", "source_file", "sample_index"]).copy()
    elapsed = out["timestamp_corrected"].diff().dt.total_seconds()
    local_period = out["estimated_sample_period_seconds"].ffill().bfill()
    # Normal adjacent samples should be close to one local sample period.
    # A generous five-period limit tolerates jitter without bridging outages.
    discontinuity = elapsed.isna() | (elapsed <= 0) | (elapsed > 5 * local_period)
    out["continuous_segment_id"] = discontinuity.cumsum().astype(int)
    return out


def _rolling_by_segment(
    df: pd.DataFrame,
    value_column: str,
    window_seconds: float,
    statistic: str,
) -> pd.Series:
    result = pd.Series(np.nan, index=df.index, dtype=float)
    for _, group in df.groupby("continuous_segment_id", sort=False):
        period = float(group["estimated_sample_period_seconds"].median())
        window = _rolling_window_samples(period, window_seconds)
        rolling = group[value_column].rolling(window, center=True, min_periods=3)
        result.loc[group.index] = getattr(rolling, statistic)().to_numpy()
    return result


def preprocess_contractions(
    cow_id: str,
    processed_csv_path: Path,
    output_path: Path,
    patch_offset_minutes: float = 0.0,
) -> pd.DataFrame:
    df = pd.read_csv(processed_csv_path, low_memory=False)

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["timestamp_raw"] = df["timestamp"]
    df["timestamp_corrected"] = df["timestamp_raw"] + pd.to_timedelta(
        patch_offset_minutes,
        unit="m",
    )

    numeric_cols = [
        "acc_x",
        "acc_y",
        "acc_z",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "strain",
        "movement_flag",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp"]).copy()
    df = _add_continuous_segment_ids(df)

    df["acc_magnitude"] = np.sqrt(
        df["acc_x"] ** 2 + df["acc_y"] ** 2 + df["acc_z"] ** 2
    )
    df["gyro_magnitude"] = np.sqrt(
        df["gyro_x"] ** 2 + df["gyro_y"] ** 2 + df["gyro_z"] ** 2
    )

    df["strain_centered_file"] = (
        df["strain"] - df.groupby("source_file")["strain"].transform("median")
    )

    orientation_rows = []

    for source_file, group in df.groupby("source_file", sort=False):
        centered = group["strain_centered_file"].dropna()

        if centered.empty:
            possible_inverted = False
        else:
            positive_score = centered.quantile(0.95)
            negative_score = abs(centered.quantile(0.05))
            possible_inverted = bool(negative_score > positive_score * 1.35)

        orientation_rows.append(
            {
                "source_file": source_file,
                "possible_inverted_signal": possible_inverted,
            }
        )

    orientation_df = pd.DataFrame(orientation_rows)
    df = df.merge(orientation_df, on="source_file", how="left")

    df["strain_orientation_corrected"] = np.where(
        False,
        -df["strain_centered_file"],
        df["strain_centered_file"],
    )
    # The skew-based orientation result is retained for human review, but is
    # not automatically applied: skew alone cannot establish sensor polarity.
    df["orientation_flip_applied"] = False

    df["acc_rolling_std_30s"] = _rolling_by_segment(
        df, "acc_magnitude", 30, "std"
    )
    df["gyro_rolling_std_30s"] = _rolling_by_segment(
        df, "gyro_magnitude", 30, "std"
    )

    df["movement_score"] = (
        df["acc_rolling_std_30s"].fillna(0)
        + df["gyro_rolling_std_30s"].fillna(0)
    )

    df["movement_artifact_flag"] = df["movement_flag"].eq(5)
    for _, group in df.groupby("continuous_segment_id", sort=False):
        score = group["movement_score"].dropna()
        if score.empty:
            continue
        median = float(score.median())
        mad = float((score - median).abs().median())
        # A robust absolute-within-segment rule does not force an arbitrary
        # percentage of every recording to be labelled as movement.
        threshold = median + max(6 * mad, 1e-9)
        df.loc[group.index, "movement_artifact_flag"] |= (
            df.loc[group.index, "movement_score"] > threshold
        )

    df["strain_rolling_std_30s"] = _rolling_by_segment(
        df, "strain", 30, "std"
    )

    df["flat_signal_flag"] = df["strain_rolling_std_30s"] < 0.05

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    return df


def detect_contraction_events(
    cow_id: str,
    preprocessed_df: pd.DataFrame,
    output_path: Path,
) -> pd.DataFrame:
    df = preprocessed_df.copy()
    df = df.sort_values("timestamp_corrected").reset_index(drop=True)

    df["strain_smooth"] = _rolling_by_segment(
        df, "strain_orientation_corrected", 10, "median"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    event_id = 0

    for segment_id, group in df.groupby("continuous_segment_id", sort=False):
        group = group.reset_index()
        sample_period = float(group["estimated_sample_period_seconds"].median())
        signal = group["strain_smooth"].fillna(0).to_numpy()
        mad = np.median(np.abs(signal - np.median(signal)))
        peaks, properties = find_peaks(
            signal,
            prominence=max(3 * mad, 1.0),
            distance=_rolling_window_samples(sample_period, 45),
            width=_rolling_window_samples(sample_period, 10),
        )
        if len(peaks) == 0:
            continue
        widths = peak_widths(signal, peaks, rel_height=0.5)[0]
        near_peak_samples = _rolling_window_samples(sample_period, 10)

        for position, peak_index in enumerate(peaks):
            event_id += 1
            left = max(0, peak_index - near_peak_samples)
            right = min(len(group), peak_index + near_peak_samples + 1)
            neighborhood = group.iloc[left:right]

            movement_near = bool(neighborhood["movement_artifact_flag"].any())
            flat_near = bool(neighborhood["flat_signal_flag"].any())
            uncertain_polarity = bool(
                "polarity_review_status" in neighborhood
                and neighborhood["polarity_review_status"].eq("uncertain").any()
            )
            if uncertain_polarity:
                label = "uncertain_polarity_region"
            elif flat_near:
                label = "bad_signal_region"
            elif movement_near:
                label = "movement_associated_peak"
            else:
                label = "candidate_contraction"

            rows.append(
                {
                    "cow_id": cow_id,
                    "event_id": event_id,
                    "continuous_segment_id": int(segment_id),
                    "peak_time": group.loc[peak_index, "timestamp_corrected"],
                    "source_file": group.loc[peak_index, "source_file"],
                    "peak_amplitude": float(group.loc[peak_index, "strain_orientation_corrected"]),
                    "prominence": float(properties["prominences"][position]),
                    "width_seconds": float(widths[position] * sample_period),
                    "movement_flag_near_peak": int(neighborhood["movement_flag"].eq(5).any()),
                    "movement_score_near_peak": float(neighborhood["movement_score"].max()),
                    "flat_signal_near_peak": int(flat_near),
                    "event_label": label,
                }
            )

    event_columns = [
        "cow_id", "event_id", "continuous_segment_id", "peak_time",
        "source_file", "peak_amplitude", "prominence", "width_seconds",
        "movement_flag_near_peak", "movement_score_near_peak",
        "flat_signal_near_peak", "event_label",
    ]
    events = pd.DataFrame(rows, columns=event_columns)
    events.to_csv(output_path, index=False)

    return events


def create_contraction_10min_summary(
    cow_id: str,
    preprocessed_df: pd.DataFrame,
    events_df: pd.DataFrame,
    output_path: Path,
) -> pd.DataFrame:
    df = preprocessed_df.copy()
    df["timestamp_corrected"] = pd.to_datetime(df["timestamp_corrected"], errors="coerce")
    df = df.dropna(subset=["timestamp_corrected"])
    df = df.set_index("timestamp_corrected").sort_index()

    summary = df.resample("10min").agg(
        strain_mean=("strain_orientation_corrected", "mean"),
        strain_max=("strain_orientation_corrected", "max"),
        strain_min=("strain_orientation_corrected", "min"),
        strain_std=("strain_orientation_corrected", "std"),
        movement_fraction=("movement_artifact_flag", "mean"),
        acc_magnitude_mean=("acc_magnitude", "mean"),
        gyro_magnitude_mean=("gyro_magnitude", "mean"),
        flat_signal_fraction=("flat_signal_flag", "mean"),
        sample_count=("strain", "count"),
    )

    summary["strain_range"] = summary["strain_max"] - summary["strain_min"]
    summary["has_contraction_samples"] = summary["sample_count"] > 0

    summary = summary.reset_index().rename(
        columns={"timestamp_corrected": "timestamp"}
    )

    if not events_df.empty:
        events = events_df.copy()
        events["peak_time"] = pd.to_datetime(events["peak_time"], errors="coerce")
        events = events.dropna(subset=["peak_time"])
        events = events.set_index("peak_time").sort_index()

        event_counts = events.resample("10min").size().rename("candidate_peak_count")

        candidate_only = (
            events[events["event_label"] == "candidate_contraction"]
            .resample("10min")
            .size()
            .rename("clean_candidate_peak_count")
        )

        summary = summary.merge(
            event_counts.reset_index().rename(columns={"peak_time": "timestamp"}),
            on="timestamp",
            how="left",
        )
        summary = summary.merge(
            candidate_only.reset_index().rename(columns={"peak_time": "timestamp"}),
            on="timestamp",
            how="left",
        )
    else:
        summary["candidate_peak_count"] = 0
        summary["clean_candidate_peak_count"] = 0

    summary["candidate_peak_count"] = (
        summary["candidate_peak_count"].fillna(0).astype(int)
    )
    summary["clean_candidate_peak_count"] = (
        summary["clean_candidate_peak_count"].fillna(0).astype(int)
    )

    summary.insert(0, "cow_id", cow_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    return summary


def preprocess_bolus(
    cow_id: str,
    bolus_csv_path: Path,
    output_path: Path,
    bolus_offset_minutes: float = 0.0,
) -> pd.DataFrame:
    df = pd.read_csv(bolus_csv_path)

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["timestamp_raw"] = df["timestamp"]
    df["timestamp_corrected"] = df["timestamp_raw"] + pd.to_timedelta(
        bolus_offset_minutes,
        unit="m",
    )

    for col in [
        "temperature_c",
        "activity",
        "temp_without_drinkcycles",
        "normal_temperature",
        "heat_index",
        "rumination_min_24h",
        "water_intake_l",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    ten = df[df["record_type"] == "10min"].copy()
    ten = ten.sort_values("timestamp_corrected")

    ten["temperature_for_analysis"] = ten["temp_without_drinkcycles"].combine_first(
        ten["temperature_c"]
    )

    ten["temp_rolling_mean_1h"] = (
        ten["temperature_for_analysis"].rolling(6, min_periods=1).mean()
    )
    ten["temp_rolling_mean_3h"] = (
        ten["temperature_for_analysis"].rolling(18, min_periods=1).mean()
    )
    ten["activity_rolling_mean_1h"] = (
        ten["activity"].rolling(6, min_periods=1).mean()
    )

    ten["date_only"] = ten["timestamp_corrected"].dt.date
    ten["daily_temp_median"] = ten.groupby("date_only")[
        "temperature_for_analysis"
    ].transform("median")
    ten["temp_deviation_from_daily_median"] = (
        ten["temperature_for_analysis"] - ten["daily_temp_median"]
    )

    daily = df[df["record_type"] == "daily"].copy()

    out = pd.concat([ten, daily], ignore_index=True, sort=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    return out


def merge_bolus_and_contractions_10min(
    cow_id: str,
    bolus_preprocessed_df: pd.DataFrame,
    contraction_summary_df: pd.DataFrame,
    all_bolus_output_path: Path,
    overlap_output_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Creates two merged outputs:
    1. all_bolus: full bolus timeline with contraction columns where available
    2. overlap_only: only rows where bolus and contraction samples both exist
    """
    bolus = bolus_preprocessed_df[
        bolus_preprocessed_df["record_type"] == "10min"
    ].copy()

    bolus["timestamp"] = pd.to_datetime(
        bolus["timestamp_corrected"],
        errors="coerce",
    )
    bolus = bolus.dropna(subset=["timestamp"]).sort_values("timestamp")
    bolus["has_bolus_data"] = True

    contractions = contraction_summary_df.copy()
    contractions["timestamp"] = pd.to_datetime(
        contractions["timestamp"],
        errors="coerce",
    )
    contractions = contractions.dropna(subset=["timestamp"]).sort_values("timestamp")
    contractions["has_contraction_data"] = True
    contractions["has_contraction_samples"] = (
        contractions["sample_count"].fillna(0) > 0
    )

    merged_all = pd.merge_asof(
        bolus,
        contractions,
        on="timestamp",
        direction="nearest",
        tolerance=pd.Timedelta("5min"),
        suffixes=("_bolus", "_contractions"),
    )

    merged_all["has_contraction_data"] = (
        merged_all["has_contraction_data"].fillna(False).astype(bool)
    )
    merged_all["has_contraction_samples"] = (
        merged_all["has_contraction_samples"].fillna(False).astype(bool)
    )
    merged_all["is_overlap_window"] = (
        merged_all["has_bolus_data"] & merged_all["has_contraction_samples"]
    )

    merged_all.insert(0, "merged_cow_id", cow_id)

    merged_overlap = merged_all[merged_all["is_overlap_window"]].copy()

    all_bolus_output_path.parent.mkdir(parents=True, exist_ok=True)
    merged_all.to_csv(all_bolus_output_path, index=False)
    merged_overlap.to_csv(overlap_output_path, index=False)

    return merged_all, merged_overlap
