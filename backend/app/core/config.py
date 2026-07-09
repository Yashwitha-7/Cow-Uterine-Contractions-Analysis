from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central application settings.

    The project currently uses SQLite for local development.
    Later, DATABASE_URL can be changed to PostgreSQL without changing
    the application logic because database access goes through SQLAlchemy.
    """

    PROJECT_NAME: str = "Hoffmann Lab Cow Monitoring"
    API_PREFIX: str = "/api"

    BASE_DIR: Path = Path(__file__).resolve().parents[3]
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    DATABASE_DIR: Path = DATA_DIR / "database"

    DATABASE_URL: str = f"sqlite:///{DATABASE_DIR / 'hoffmann_lab.db'}"

    class Config:
        env_file = ".env"


settings = Settings()