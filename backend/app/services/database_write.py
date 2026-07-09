import pandas as pd
from sqlalchemy.orm import Session

from app.models.bolus import BolusRecord
from app.models.contraction import ContractionRecord


def insert_contraction_records(db: Session, df: pd.DataFrame) -> int:
    """
    Inserts processed contraction rows into the database.
    """
    records = [
        ContractionRecord(
            cow_id=row["cow_id"],
            timestamp=row["timestamp"],
            source_file=row["source_file"],
            file_order=int(row["file_order"]),
            sample_index=int(row["sample_index"]),
            global_sample_index=int(row["global_sample_index"]),
            acc_x=row["acc_x"],
            acc_y=row["acc_y"],
            acc_z=row["acc_z"],
            gyro_x=row["gyro_x"],
            gyro_y=row["gyro_y"],
            gyro_z=row["gyro_z"],
            strain=row["strain"],
            movement_flag=row["movement_flag"],
            unknown_1=row["unknown_1"],
            unknown_2=row["unknown_2"],
        )
        for _, row in df.iterrows()
    ]

    db.bulk_save_objects(records)
    db.commit()

    return len(records)


def insert_bolus_records(db: Session, df: pd.DataFrame) -> int:
    """
    Inserts processed bolus rows into the database.

    Includes both 10-minute and daily sheet rows.
    """
    records = [
        BolusRecord(
            cow_id=row["cow_id"],
            timestamp=row["timestamp"],
            record_type=row["record_type"],
            source_file=row["source_file"],
            source_sheet=row["source_sheet"],
            ph=row["ph"],
            temperature_c=row["temperature_c"],
            activity=row["activity"],
            temp_without_drinkcycles=row["temp_without_drinkcycles"],
            normal_temperature=row["normal_temperature"],
            heat_index=row["heat_index"],
            rumination_min_24h=row["rumination_min_24h"],
            water_intake_l=row["water_intake_l"],
        )
        for _, row in df.iterrows()
        if pd.notna(row["timestamp"])
    ]

    db.bulk_save_objects(records)
    db.commit()

    return len(records)