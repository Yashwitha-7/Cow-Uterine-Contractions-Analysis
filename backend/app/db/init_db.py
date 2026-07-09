from app.db.session import Base, engine
from app import models  # noqa: F401


def init_db() -> None:
    """
    Creates database tables for local development.

    In production or later project phases, Alembic migrations should be used
    instead of automatic table creation.
    """
    Base.metadata.create_all(bind=engine)