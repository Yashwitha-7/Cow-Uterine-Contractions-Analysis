from pathlib import Path

import numpy as np
import pandas as pd

from app.services.contraction_ingest import combine_contraction_files
from app.services.phase3_processing import preprocess_contractions


def _write_sensor_file(path: Path, rows: int) -> None:
    header = "Time Acc.X Acc.Y Acc.Z G.X G.Y G.Z Strain Sensor\n"
    values = "\n".join(
        f"1 2 3 0.1 0.2 0.3 {i % 7} 0 0 0" for i in range(rows)
    )
    path.write_text(header + values + "\n")


def test_partial_file_period_is_capped_at_next_boundary(tmp_path):
    first = tmp_path / "260101000000.txt"
    second = tmp_path / "260101010000.txt"
    third = tmp_path / "260101014500.txt"
    _write_sensor_file(first, 2000)
    _write_sensor_file(second, 1590)
    _write_sensor_file(third, 2000)

    combined, timing = combine_contraction_files("test", [first, second, third])
    timestamps = pd.to_datetime(combined["timestamp"])

    assert timestamps.is_monotonic_increasing
    assert not timestamps.duplicated().any()
    second_timing = timing.loc[timing["source_file"] == second.name].iloc[0]
    assert second_timing["sample_period_source"] == "adjusted_to_next_file_boundary"


def test_preprocessing_does_not_bridge_recording_gaps_or_auto_flip(tmp_path):
    source = tmp_path / "processed.csv"
    output = tmp_path / "preprocessed.csv"
    timestamps = list(pd.date_range("2026-01-01", periods=20, freq="2s"))
    timestamps += list(pd.date_range("2026-01-01 01:00", periods=20, freq="2s"))
    strain = np.r_[np.arange(20), -np.arange(20)]

    pd.DataFrame(
        {
            "timestamp": timestamps,
            "source_file": ["a.txt"] * 20 + ["b.txt"] * 20,
            "sample_index": list(range(20)) * 2,
            "estimated_sample_period_seconds": [2.0] * 40,
            "acc_x": [1.0] * 40,
            "acc_y": [2.0] * 40,
            "acc_z": [3.0] * 40,
            "gyro_x": [0.1] * 40,
            "gyro_y": [0.2] * 40,
            "gyro_z": [0.3] * 40,
            "strain": strain,
            "movement_flag": [0] * 40,
        }
    ).to_csv(source, index=False)

    result = preprocess_contractions("test", source, output)

    assert result["continuous_segment_id"].nunique() == 2
    assert not result["orientation_flip_applied"].any()
    assert np.allclose(
        result["strain_orientation_corrected"],
        result["strain_centered_file"],
    )
