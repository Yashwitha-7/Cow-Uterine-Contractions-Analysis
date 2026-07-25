from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.cow import Cow


FIGURE_DPI = 180
BIN_MINUTES = 10
BINS_PER_DAY = int(24 * 60 / BIN_MINUTES)


def _get_cow_calving_time(db: Session, cow_id: str):
    cow = db.get(Cow, cow_id)
    if cow is None:
        return None
    return cow.calving_datetime


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path, low_memory=False)


def _prepare_figures_folder(processed_folder: Path) -> Path:
    figures_folder = processed_folder / "figures"
    figures_folder.mkdir(parents=True, exist_ok=True)
    return figures_folder


def _save_current_figure(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close()


def _time_tick_setup(ax):
    ticks = np.arange(0, 25, 2)
    labels = [f"{int(t):02d}:00" for t in ticks]
    ax.set_xlim(0, 24)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=45, ha="right")


def _calving_hour_if_same_day(calving_time, date_value):
    if calving_time is None:
        return None

    calving = pd.to_datetime(calving_time)
    date_value = pd.to_datetime(date_value).date()

    if calving.date() != date_value:
        return None

    return calving.hour + calving.minute / 60 + calving.second / 3600


def _add_calving_marker_to_daily_axis(ax, calving_time, date_value):
    calving_hour = _calving_hour_if_same_day(calving_time, date_value)

    if calving_hour is None:
        return

    ax.axvline(
        calving_hour,
        linestyle="--",
        linewidth=1.8,
        color="red",
        label="Calving time",
    )


def _format_datetime_axis(ax):
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(True, alpha=0.25)


def _add_calving_marker_datetime(ax, calving_time):
    if calving_time is None:
        return

    ax.axvline(
        pd.to_datetime(calving_time),
        linestyle="--",
        linewidth=1.8,
        color="red",
        label="Calving time",
    )


def _make_daily_matrix(
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str,
    require_samples: bool = False,
) -> tuple[pd.DataFrame, list[str], np.ndarray]:
    data = df.copy()
    data[timestamp_col] = pd.to_datetime(data[timestamp_col], errors="coerce")
    data = data.dropna(subset=[timestamp_col])

    if require_samples and "has_contraction_samples" in data.columns:
        data = data[data["has_contraction_samples"].astype(bool)]

    data["date"] = data[timestamp_col].dt.date
    data["minute_of_day"] = (
        data[timestamp_col].dt.hour * 60 + data[timestamp_col].dt.minute
    )

    all_bins = np.arange(0, 24 * 60, BIN_MINUTES)

    matrix = (
        data.pivot_table(
            index="date",
            columns="minute_of_day",
            values=value_col,
            aggfunc="mean",
        )
        .reindex(columns=all_bins)
        .sort_index()
    )

    date_labels = [str(item) for item in matrix.index]
    values = matrix.to_numpy(dtype=float)

    return matrix, date_labels, values


def _plot_actogram_core(
    cow_id: str,
    values: np.ndarray,
    date_labels: list[str],
    title: str,
    colorbar_label: str,
    output_path: Path,
    calving_time=None,
):
    plt.figure(figsize=(16, max(4.5, 0.7 * len(date_labels))))
    ax = plt.gca()

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")

    masked = np.ma.masked_invalid(values)

    image = ax.imshow(
        masked,
        aspect="auto",
        interpolation="nearest",
        origin="upper",
        cmap=cmap,
    )

    ax.set_title(title)
    ax.set_ylabel("Date")
    ax.set_xlabel("Time of day")

    ax.set_yticks(np.arange(len(date_labels)))
    ax.set_yticklabels(date_labels)

    hour_ticks = np.arange(0, BINS_PER_DAY + 1, 6)
    hour_labels = [f"{hour:02d}:00" for hour in range(0, 25)]

    ax.set_xticks(hour_ticks)
    ax.set_xticklabels(hour_labels, rotation=45, ha="right")

    if calving_time is not None:
        calving = pd.to_datetime(calving_time)
        calving_date = str(calving.date())
        calving_bin = (calving.hour * 60 + calving.minute) / BIN_MINUTES

        if calving_date in date_labels:
            row_idx = date_labels.index(calving_date)
            ax.plot(
                [calving_bin, calving_bin],
                [row_idx - 0.45, row_idx + 0.45],
                linestyle="--",
                linewidth=2.0,
                color="red",
            )
            ax.text(
                calving_bin + 1,
                row_idx,
                "Calving",
                color="red",
                fontsize=8,
                va="center",
            )

    cbar = plt.colorbar(image, ax=ax)
    cbar.set_label(colorbar_label)

    ax.text(
        0,
        len(date_labels) + 0.45,
        "White areas indicate no samples / missing data for that time window.",
        fontsize=8,
        ha="left",
        va="center",
    )

    _save_current_figure(output_path)


def plot_contraction_actogram(
    cow_id: str,
    processed_folder: Path,
    db: Session,
    value_col: str,
    title_label: str,
    output_suffix: str,
) -> Path:
    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"
    summary = _load_csv(summary_path)

    if value_col not in summary.columns:
        raise ValueError(f"{value_col} column not found in 10-minute summary.")

    _, date_labels, values = _make_daily_matrix(
        summary,
        timestamp_col="timestamp",
        value_col=value_col,
        require_samples=True,
    )

    calving_time = _get_cow_calving_time(db, cow_id)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_actogram_{output_suffix}.png"
    )

    _plot_actogram_core(
        cow_id=cow_id,
        values=values,
        date_labels=date_labels,
        title=f"Cow {cow_id}: 24-hour Actogram — {title_label}",
        colorbar_label=title_label,
        output_path=output_path,
        calving_time=calving_time,
    )

    return output_path


def plot_bolus_temperature_actogram(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    bolus_path = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"
    bolus = _load_csv(bolus_path)

    bolus = bolus[bolus["record_type"] == "10min"].copy()
    bolus["timestamp_corrected"] = pd.to_datetime(
        bolus["timestamp_corrected"],
        errors="coerce",
    )
    bolus = bolus.dropna(subset=["timestamp_corrected"])

    if "temperature_for_analysis" not in bolus.columns:
        raise ValueError("temperature_for_analysis column not found.")

    _, date_labels, values = _make_daily_matrix(
        bolus,
        timestamp_col="timestamp_corrected",
        value_col="temperature_for_analysis",
        require_samples=False,
    )

    calving_time = _get_cow_calving_time(db, cow_id)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_bolus_temperature_actogram.png"
    )

    _plot_actogram_core(
        cow_id=cow_id,
        values=values,
        date_labels=date_labels,
        title=(
            f"Cow {cow_id}: Drink-Cycle-Corrected Bolus Temperature "
            "24-hour Actogram"
        ),
        colorbar_label="Bolus temperature (°C)",
        output_path=output_path,
        calving_time=calving_time,
    )

    return output_path


def plot_double_candidate_peak_actogram(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"
    summary = _load_csv(summary_path)

    if "candidate_peak_count" not in summary.columns:
        raise ValueError("candidate_peak_count column not found.")

    _, date_labels, values = _make_daily_matrix(
        summary,
        timestamp_col="timestamp",
        value_col="candidate_peak_count",
        require_samples=True,
    )

    if len(date_labels) < 2:
        raise ValueError("Need at least two days for 48-hour actogram.")

    double_rows = []
    double_labels = []

    for idx in range(len(date_labels) - 1):
        double_rows.append(np.concatenate([values[idx], values[idx + 1]]))
        double_labels.append(f"{date_labels[idx]} + {date_labels[idx + 1]}")

    double_values = np.vstack(double_rows)

    plt.figure(figsize=(18, max(4.5, 0.75 * len(double_labels))))
    ax = plt.gca()

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")

    image = ax.imshow(
        np.ma.masked_invalid(double_values),
        aspect="auto",
        interpolation="nearest",
        origin="upper",
        cmap=cmap,
    )

    ax.set_title(
        f"Cow {cow_id}: 48-hour Double-Plotted Actogram — Candidate Peak Count"
    )
    ax.set_ylabel("Date pair")
    ax.set_xlabel("Time across 48 hours")

    ax.set_yticks(np.arange(len(double_labels)))
    ax.set_yticklabels(double_labels)

    hour_ticks = np.arange(0, 48 * 6 + 1, 12)
    hour_labels = [f"{hour:02d}:00" for hour in range(0, 49, 2)]

    ax.set_xticks(hour_ticks)
    ax.set_xticklabels(hour_labels, rotation=45, ha="right")

    ax.axvline(BINS_PER_DAY, linewidth=1.2, color="black")

    calving_time = _get_cow_calving_time(db, cow_id)

    if calving_time is not None:
        calving = pd.to_datetime(calving_time)
        calving_date = str(calving.date())
        calving_bin = (calving.hour * 60 + calving.minute) / BIN_MINUTES

        for row_idx, label in enumerate(double_labels):
            first_date, second_date = label.split(" + ")

            if calving_date == first_date:
                x_value = calving_bin
            elif calving_date == second_date:
                x_value = BINS_PER_DAY + calving_bin
            else:
                continue

            ax.plot(
                [x_value, x_value],
                [row_idx - 0.45, row_idx + 0.45],
                linestyle="--",
                linewidth=2,
                color="red",
            )
            ax.text(
                x_value + 1,
                row_idx,
                "Calving",
                color="red",
                fontsize=8,
                va="center",
            )

    cbar = plt.colorbar(image, ax=ax)
    cbar.set_label("Candidate peak count per 10 min")

    output_path = (
        processed_folder
        / "figures"
        / f"cow_{cow_id}_double_actogram_candidate_peak_count.png"
    )
    _save_current_figure(output_path)

    return output_path


def plot_full_clean_corrected_strain_trace(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    preprocessed_path = processed_folder / f"cow_{cow_id}_contractions_preprocessed.csv"
    df = _load_csv(preprocessed_path)

    df["timestamp_corrected"] = pd.to_datetime(
        df["timestamp_corrected"],
        errors="coerce",
    )
    df = df.dropna(subset=["timestamp_corrected"]).sort_values("timestamp_corrected")

    if "strain_orientation_corrected" not in df.columns:
        raise ValueError("strain_orientation_corrected column not found.")

    plot_df = df.copy()

    if len(plot_df) > 30000:
        step = int(np.ceil(len(plot_df) / 30000))
        plot_df = plot_df.iloc[::step, :]

    calving_time = _get_cow_calving_time(db, cow_id)

    plt.figure(figsize=(16, 5))
    ax = plt.gca()

    ax.plot(
        plot_df["timestamp_corrected"],
        plot_df["strain_orientation_corrected"],
        linewidth=0.5,
        label="Baseline-centered strain (no automatic polarity flip)",
    )

    _add_calving_marker_datetime(ax, calving_time)

    ax.set_title(f"Cow {cow_id}: Full Baseline-Centered Contraction Strain Trace")
    ax.set_xlabel("Time")
    ax.set_ylabel("Baseline-centered strain")
    _format_datetime_axis(ax)
    ax.legend(loc="upper right", fontsize=8)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_full_clean_corrected_strain_trace.png"
    )
    _save_current_figure(output_path)

    return output_path


def _plot_daily_rows_from_dataframe(
    cow_id: str,
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str,
    title: str,
    y_label: str,
    output_path: Path,
    calving_time=None,
):
    data = df.copy()
    data[timestamp_col] = pd.to_datetime(data[timestamp_col], errors="coerce")
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna(subset=[timestamp_col])
    data = data.sort_values(timestamp_col)

    data["date"] = data[timestamp_col].dt.date
    data["hour_decimal"] = (
        data[timestamp_col].dt.hour
        + data[timestamp_col].dt.minute / 60
        + data[timestamp_col].dt.second / 3600
    )

    dates = sorted(data["date"].dropna().unique())

    fig_height = max(4, 1.8 * len(dates))
    fig, axes = plt.subplots(
        len(dates),
        1,
        figsize=(16, fig_height),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    axes = axes.flatten()

    for ax, date_value in zip(axes, dates):
        group = data[data["date"] == date_value].copy()

        ax.plot(
            group["hour_decimal"],
            group[value_col],
            linewidth=1.0,
        )

        _add_calving_marker_to_daily_axis(ax, calving_time, date_value)

        ax.text(
            0.005,
            0.90,
            str(date_value),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=8,
        )
        ax.grid(True, alpha=0.25)
        _time_tick_setup(ax)

    axes[0].set_title(title)
    axes[-1].set_xlabel("Time of day")
    fig.text(0.001, 0.5, y_label, rotation=90, va="center")

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        axes[0].legend(loc="upper right", fontsize=8)

    _save_current_figure(output_path)


def plot_daily_contraction_strain_rows(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"
    summary = _load_csv(summary_path)

    if "has_contraction_samples" in summary.columns:
        summary = summary[summary["has_contraction_samples"].astype(bool)]

    if "strain_mean" not in summary.columns:
        raise ValueError("strain_mean column not found.")

    calving_time = _get_cow_calving_time(db, cow_id)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_daily_contraction_strain_rows.png"
    )

    _plot_daily_rows_from_dataframe(
        cow_id=cow_id,
        df=summary,
        timestamp_col="timestamp",
        value_col="strain_mean",
        title=f"Cow {cow_id}: Daily 10-minute Contraction Strain",
        y_label="10-minute mean baseline-centered strain",
        output_path=output_path,
        calving_time=calving_time,
    )

    return output_path


def plot_daily_bolus_temperature_rows(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    bolus_path = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"
    bolus = _load_csv(bolus_path)

    bolus = bolus[bolus["record_type"] == "10min"].copy()

    if "temperature_for_analysis" not in bolus.columns:
        raise ValueError("temperature_for_analysis column not found.")

    calving_time = _get_cow_calving_time(db, cow_id)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_daily_bolus_temperature_rows.png"
    )

    _plot_daily_rows_from_dataframe(
        cow_id=cow_id,
        df=bolus,
        timestamp_col="timestamp_corrected",
        value_col="temperature_for_analysis",
        title=f"Cow {cow_id}: Daily Drink-Cycle-Corrected Bolus Temperature",
        y_label="Bolus temperature (°C)",
        output_path=output_path,
        calving_time=calving_time,
    )

    return output_path


def plot_daily_motion_sensor_rows(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"
    summary = _load_csv(summary_path)

    required = {"timestamp", "acc_magnitude_mean", "gyro_magnitude_mean"}

    missing = required - set(summary.columns)
    if missing:
        raise ValueError(f"Missing columns for motion plot: {missing}")

    if "has_contraction_samples" in summary.columns:
        summary = summary[summary["has_contraction_samples"].astype(bool)]

    summary["timestamp"] = pd.to_datetime(summary["timestamp"], errors="coerce")
    summary = summary.dropna(subset=["timestamp"]).sort_values("timestamp")
    summary["date"] = summary["timestamp"].dt.date
    summary["hour_decimal"] = (
        summary["timestamp"].dt.hour + summary["timestamp"].dt.minute / 60
    )

    dates = sorted(summary["date"].dropna().unique())
    calving_time = _get_cow_calving_time(db, cow_id)

    fig_height = max(4, 1.8 * len(dates))
    fig, axes = plt.subplots(
        len(dates),
        2,
        figsize=(18, fig_height),
        sharex=True,
        sharey="col",
        squeeze=False,
    )

    for row_idx, date_value in enumerate(dates):
        group = summary[summary["date"] == date_value]

        ax_acc = axes[row_idx, 0]
        ax_gyro = axes[row_idx, 1]

        ax_acc.plot(group["hour_decimal"], group["acc_magnitude_mean"], linewidth=1.0)
        ax_gyro.plot(group["hour_decimal"], group["gyro_magnitude_mean"], linewidth=1.0)

        _add_calving_marker_to_daily_axis(ax_acc, calving_time, date_value)
        _add_calving_marker_to_daily_axis(ax_gyro, calving_time, date_value)

        ax_acc.text(
            0.01,
            0.90,
            str(date_value),
            transform=ax_acc.transAxes,
            ha="left",
            va="top",
            fontsize=8,
        )

        ax_acc.set_title("Accelerometer magnitude" if row_idx == 0 else "")
        ax_gyro.set_title("Gyroscope magnitude" if row_idx == 0 else "")

        ax_acc.grid(True, alpha=0.25)
        ax_gyro.grid(True, alpha=0.25)

        _time_tick_setup(ax_acc)
        _time_tick_setup(ax_gyro)

    axes[-1, 0].set_xlabel("Time of day")
    axes[-1, 1].set_xlabel("Time of day")

    fig.suptitle(f"Cow {cow_id}: Daily Motion Sensor Summary", y=1.01)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_daily_motion_sensor_rows.png"
    )
    _save_current_figure(output_path)

    return output_path


def plot_parallel_bolus_contraction_daily(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> Path:
    bolus_path = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"
    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"

    bolus = _load_csv(bolus_path)
    summary = _load_csv(summary_path)

    bolus = bolus[bolus["record_type"] == "10min"].copy()
    bolus["timestamp_corrected"] = pd.to_datetime(
        bolus["timestamp_corrected"],
        errors="coerce",
    )
    bolus["temperature_for_analysis"] = pd.to_numeric(
        bolus["temperature_for_analysis"],
        errors="coerce",
    )
    bolus = bolus.dropna(subset=["timestamp_corrected"])

    summary["timestamp"] = pd.to_datetime(summary["timestamp"], errors="coerce")
    summary["strain_mean"] = pd.to_numeric(summary["strain_mean"], errors="coerce")
    summary = summary.dropna(subset=["timestamp"])

    if "has_contraction_samples" in summary.columns:
        summary = summary[summary["has_contraction_samples"].astype(bool)]

    bolus["date"] = bolus["timestamp_corrected"].dt.date
    bolus["hour_decimal"] = (
        bolus["timestamp_corrected"].dt.hour
        + bolus["timestamp_corrected"].dt.minute / 60
    )

    summary["date"] = summary["timestamp"].dt.date
    summary["hour_decimal"] = (
        summary["timestamp"].dt.hour + summary["timestamp"].dt.minute / 60
    )

    all_dates = sorted(set(bolus["date"].dropna()) | set(summary["date"].dropna()))
    calving_time = _get_cow_calving_time(db, cow_id)

    fig_height = max(5, 1.8 * len(all_dates))
    fig, axes = plt.subplots(
        len(all_dates),
        2,
        figsize=(18, fig_height),
        sharex=True,
        sharey="col",
        squeeze=False,
    )

    for row_idx, date_value in enumerate(all_dates):
        b = bolus[bolus["date"] == date_value]
        c = summary[summary["date"] == date_value]

        ax_bolus = axes[row_idx, 0]
        ax_strain = axes[row_idx, 1]

        if not b.empty:
            ax_bolus.plot(
                b["hour_decimal"],
                b["temperature_for_analysis"],
                linewidth=1.0,
            )

        if not c.empty:
            ax_strain.plot(
                c["hour_decimal"],
                c["strain_mean"],
                linewidth=1.0,
            )

        _add_calving_marker_to_daily_axis(ax_bolus, calving_time, date_value)
        _add_calving_marker_to_daily_axis(ax_strain, calving_time, date_value)

        ax_bolus.text(
            0.01,
            0.90,
            str(date_value),
            transform=ax_bolus.transAxes,
            ha="left",
            va="top",
            fontsize=8,
        )

        if row_idx == 0:
            ax_bolus.set_title("Drink-cycle-corrected bolus temperature (°C)")
            ax_strain.set_title("10-minute contraction strain")

        ax_bolus.grid(True, alpha=0.25)
        ax_strain.grid(True, alpha=0.25)

        _time_tick_setup(ax_bolus)
        _time_tick_setup(ax_strain)

    axes[-1, 0].set_xlabel("Time of day")
    axes[-1, 1].set_xlabel("Time of day")

    fig.suptitle(
        f"Cow {cow_id}: Parallel Daily Bolus Temperature and Contraction Strain",
        y=1.01,
    )

    output_path = (
        processed_folder
        / "figures"
        / f"cow_{cow_id}_parallel_bolus_contraction_daily.png"
    )
    _save_current_figure(output_path)

    return output_path


def plot_signal_correction_review(
    cow_id: str,
    processed_folder: Path,
) -> Path:
    preprocessed_path = processed_folder / f"cow_{cow_id}_contractions_preprocessed.csv"
    df = _load_csv(preprocessed_path)

    df["timestamp_corrected"] = pd.to_datetime(
        df["timestamp_corrected"],
        errors="coerce",
    )
    df = df.dropna(subset=["timestamp_corrected"])

    required_cols = {
        "source_file",
        "strain",
        "strain_centered_file",
        "strain_orientation_corrected",
        "possible_inverted_signal",
        "file_type",
    }

    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for correction review: {missing}")

    selected_files = []

    inverted_files = (
        df[df["possible_inverted_signal"].astype(bool)]["source_file"]
        .drop_duplicates()
        .head(3)
        .tolist()
    )

    normal_files = (
        df[~df["possible_inverted_signal"].astype(bool)]["source_file"]
        .drop_duplicates()
        .head(3)
        .tolist()
    )

    partial_files = (
        df[df["file_type"].astype(str).str.contains("partial", na=False)][
            "source_file"
        ]
        .drop_duplicates()
        .head(3)
        .tolist()
    )

    for item in inverted_files + normal_files + partial_files:
        if item not in selected_files:
            selected_files.append(item)

    selected_files = selected_files[:8]

    if not selected_files:
        raise ValueError("No files available for signal correction review.")

    fig_height = max(6, 2.2 * len(selected_files))
    plt.figure(figsize=(16, fig_height))

    for idx, source_file in enumerate(selected_files, start=1):
        group = df[df["source_file"] == source_file].copy()
        group = group.sort_values("timestamp_corrected")

        ax = plt.subplot(len(selected_files), 1, idx)

        x = group["timestamp_corrected"]

        ax.plot(x, group["strain"], linewidth=0.6, label="Raw strain")
        ax.plot(
            x,
            group["strain_centered_file"],
            linewidth=0.6,
            label="File-centered strain",
        )
        ax.plot(
            x,
            group["strain_orientation_corrected"],
            linewidth=0.8,
            label="Analysis strain (polarity flip not applied)",
        )

        possible_inverted = bool(group["possible_inverted_signal"].iloc[0])
        file_type = group["file_type"].iloc[0]

        ax.set_title(
            f"{source_file} | possible_inversion_flag={possible_inverted} "
            f"(not applied) | file_type={file_type}",
            fontsize=9,
        )
        ax.grid(True, alpha=0.25)

        if idx == 1:
            ax.legend(loc="upper right", fontsize=7)

    output_path = (
        processed_folder / "figures" / f"cow_{cow_id}_signal_correction_review.png"
    )
    _save_current_figure(output_path)

    return output_path


def generate_all_visualizations(
    cow_id: str,
    processed_folder: Path,
    db: Session,
) -> list[dict]:
    _prepare_figures_folder(processed_folder)

    outputs: list[Path] = []

    summary_path = processed_folder / f"cow_{cow_id}_contractions_10min_summary.csv"
    preprocessed_path = processed_folder / f"cow_{cow_id}_contractions_preprocessed.csv"
    bolus_path = processed_folder / f"cow_{cow_id}_bolus_preprocessed.csv"

    if not summary_path.exists():
        raise FileNotFoundError("contractions_10min_summary.csv not found. Run Phase 3 first.")

    if not preprocessed_path.exists():
        raise FileNotFoundError("contractions_preprocessed.csv not found. Run Phase 3 first.")

    # Clean contraction strain figures.
    outputs.append(plot_full_clean_corrected_strain_trace(cow_id, processed_folder, db))
    outputs.append(plot_daily_contraction_strain_rows(cow_id, processed_folder, db))

    # Main contraction actograms.
    outputs.append(
        plot_contraction_actogram(
            cow_id=cow_id,
            processed_folder=processed_folder,
            db=db,
            value_col="candidate_peak_count",
            title_label="All candidate peak count per 10 min",
            output_suffix="candidate_peak_count",
        )
    )

    summary = _load_csv(summary_path)

    if "clean_candidate_peak_count" in summary.columns:
        outputs.append(
            plot_contraction_actogram(
                cow_id=cow_id,
                processed_folder=processed_folder,
                db=db,
                value_col="clean_candidate_peak_count",
                title_label="Clean contraction-candidate peak count per 10 min",
                output_suffix="clean_candidate_peak_count",
            )
        )

    outputs.append(
        plot_contraction_actogram(
            cow_id=cow_id,
            processed_folder=processed_folder,
            db=db,
            value_col="strain_range",
            title_label="Baseline-centered strain range per 10 min",
            output_suffix="strain_range",
        )
    )

    outputs.append(
        plot_contraction_actogram(
            cow_id=cow_id,
            processed_folder=processed_folder,
            db=db,
            value_col="movement_fraction",
            title_label="Movement fraction per 10 min",
            output_suffix="movement_fraction",
        )
    )

    outputs.append(plot_double_candidate_peak_actogram(cow_id, processed_folder, db))

    # Use accelerometer and gyroscope summaries.
    outputs.append(plot_daily_motion_sensor_rows(cow_id, processed_folder, db))

    # QC figure for negative/inverted signal handling.
    outputs.append(plot_signal_correction_review(cow_id, processed_folder))

    # Bolus figures only if bolus preprocessing exists.
    if bolus_path.exists():
        outputs.append(plot_bolus_temperature_actogram(cow_id, processed_folder, db))
        outputs.append(plot_daily_bolus_temperature_rows(cow_id, processed_folder, db))
        outputs.append(plot_parallel_bolus_contraction_daily(cow_id, processed_folder, db))

    results = []

    for path in outputs:
        results.append(
            {
                "file_name": path.name,
                "file_path": str(path),
                "size_bytes": path.stat().st_size,
            }
        )

    return results
