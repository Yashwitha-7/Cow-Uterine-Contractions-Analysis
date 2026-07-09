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
    Standardizes column names by trimming extra spaces.

    This keeps the original scientific meaning of the column names while
    preventing small Excel formatting issues from breaking ingestion.
    """
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _find_header_row(file_path: Path, sheet_name: str) -> int:
    """
    Finds the row index containing the actual data header.

    The MagTags bolus export includes metadata rows before the real data table.
    In the current Cow 6263 file, the real header row contains:
        date, timestamp, pH, temperature °C, ...

    This function makes ingestion more robust by searching for the row that
    contains both 'date' and 'timestamp' instead of assuming the header is row 0.
    """
    preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=30)

    for row_index, row in preview.iterrows():
        values = [str(value).strip().lower() for value in row.dropna().tolist()]

        if "date" in values and "timestamp" in values:
            return int(row_index)

    raise ValueError(
        f"Could not find a valid header row in sheet '{sheet_name}'. "
        "Expected a row containing both 'date' and 'timestamp'."
    )


def _read_sheet_with_detected_header(file_path: Path, sheet_name: str) -> pd.DataFrame:
    """
    Reads one Excel sheet after automatically detecting the real header row.
    """
    header_row = _find_header_row(file_path, sheet_name)

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=header_row,
    )

    df = _clean_column_names(df)

    # Remove fully empty rows that may appear after the data table.
    df = df.dropna(how="all")

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
        raw = _read_sheet_with_detected_header(file_path, sheet_name)
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