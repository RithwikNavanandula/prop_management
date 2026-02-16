# Property Management V2

## Requirements
- Python 3.11+
- `pip`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally
```bash
uvicorn app.main:app --reload
```

App: `http://127.0.0.1:8000`

## Seed sample data
```bash
python scripts/seed_data.py
```

Default admin:
- username: `admin`
- password: `admin123`

## Portals
- `/portal/tenant`
- `/portal/owner`
- `/portal/vendor`
