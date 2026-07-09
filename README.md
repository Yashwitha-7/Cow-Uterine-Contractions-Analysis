# Hoffmann Lab Cow Monitoring Data Portal

This project supports ingestion and storage of cow uterine contraction sensor data and bolus physiological data for the Hoffmann Lab uterine contraction analysis project.

## Phase 1 Scope

Phase 1 performs data ingestion and storage only:

- Upload contraction TXT files by cow ID
- Upload bolus Excel files by cow ID
- Store raw files separately
- Create standardized processed CSV files
- Store processed rows in SQLite
- Download processed CSV files

No signal correction, contraction detection, synchronization, or modeling is performed in Phase 1.

## Tech Stack

- Backend: Python, FastAPI
- Database: SQLite
- ORM: SQLAlchemy
- Migrations: Alembic, planned
- Data processing: pandas, numpy
- Frontend: React + Vite
- UI: Ant Design
- Version control: Git

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload