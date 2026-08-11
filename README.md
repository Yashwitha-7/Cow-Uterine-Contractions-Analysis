# Hoffmann Lab Cow Contraction Analysis

Local research application for ingesting cow contraction sensor and bolus data, reviewing suspected strain polarity reversals, and producing quality-controlled exploratory analyses.

## Analysis workflow

1. Upload contraction TXT files and optional bolus Excel data.
2. Review ingestion and timestamp QC.
3. Open **Polarity Review** and screen the cow.
4. Review every flagged continuous section as **Keep**, **Flip**, or **Uncertain**.
5. Use the hourly browser to inspect every recording hour manually.
6. Run **Reviewed Analysis** only after all flagged sections have decisions.
7. View or download regenerated figures and statistical results.

Candidate strain peaks are exploratory and are not confirmed physiological contractions.

## Data organization

```text
data/
  raw/cow_<id>/
    contractions/       immutable uploaded TXT files
    bolus/              immutable uploaded bolus files
  processed/cow_<id>/
    quality_control/    polarity screening, manifest, and saved decisions
    statistics/         day/night and 24-hour rhythm summaries
    figures/            regenerated PNG visualizations
    clocklab_exports/   ClockLab CSV/AWD exports
    *.csv               current compatible analysis datasets
  database/             local SQLite database
```

## Run locally

Terminal 1:

```bash
cd /Users/yashwitha/Documents/GitHub/Cow-Uterine-Contractions-Analysis/backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Terminal 2:

```bash
cd /Users/yashwitha/Documents/GitHub/Cow-Uterine-Contractions-Analysis/frontend
npm install
npm run dev
```

Open the local address printed by Vite, normally `http://localhost:5173`.

## Verification

```bash
cd /Users/yashwitha/Documents/GitHub/Cow-Uterine-Contractions-Analysis/backend
.venv/bin/python -m pytest tests -q

cd /Users/yashwitha/Documents/GitHub/Cow-Uterine-Contractions-Analysis/frontend
npm run lint
npm run build
```
