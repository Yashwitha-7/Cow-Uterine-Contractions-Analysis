from pathlib import Path

import pandas as pd


TEN_MIN_RENAME_MAP = {
    "date": "date",
    "timestamp": "timestamp",
    "pH": "ph",
    "temperature °C": "temperature_c",
    "activity": "activity",
    "Temp Without Drinkcycles": "temp_without_drinkcycles",
    "Normal temperature": "normal_temperature",
    "Heat index": "heat_index",
    "rumination min/24h": "rumination_min_24h",
}

DAILY_RENAME_MAP = {
    "date": "date",
    "timestamp": "timestamp",
    "water_intake in l": "water_intake_l",
}


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trims spaces from column names while preserving original meaning.
    """
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def read_bolus_excel(cow_id: str, file_path: Path) -> pd.DataFrame:
    """
    Reads a bolus Excel file and stores both sheets in one standardized bolus table.

    Sheet 1:
        10-minute physiological records

    Sheet 2:
        Daily summary records, including water intake

    Both are returned in one DataFrame using:
        record_type = "10min" or "daily"
    """
    excel = pd.ExcelFile(file_path)
    frames: list[pd.DataFrame] = []

    for sheet_name in excel.sheet_names:
        raw = pd.read_excel(file_path, sheet_name=sheet_name)
        raw = _clean_column_names(raw)

        lower_sheet = sheet_name.lower()

        if "10min" in lower_sheet:
            df = raw.rename(columns=TEN_MIN_RENAME_MAP)
            df["record_type"] = "10min"

            required = ["timestamp"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"Missing columns in sheet {sheet_name}: {missing}")

        elif "daily" in lower_sheet:
            df = raw.rename(columns=DAILY_RENAME_MAP)
            df["record_type"] = "daily"

            required = ["timestamp"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"Missing columns in sheet {sheet_name}: {missing}")

        else:
            # Unknown sheet names are skipped in Phase 1.
            # Later, we can log this into QC if needed.
            continue

        df["cow_id"] = cow_id
        df["source_file"] = file_path.name
        df["source_sheet"] = sheet_name
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        frames.append(df)

    if not frames:
        raise ValueError("No usable bolus sheets were found.")

    combined = pd.concat(frames, ignore_index=True)

    output_columns = [
        "cow_id",
        "timestamp",
        "record_type",
        "source_file",
        "source_sheet",
        "ph",
        "temperature_c",
        "activity",
        "temp_without_drinkcycles",
        "normal_temperature",
        "heat_index",
        "rumination_min_24h",
        "water_intake_l",
    ]

    for col in output_columns:
        if col not in combined.columns:
            combined[col] = None

    return combined[output_columns]