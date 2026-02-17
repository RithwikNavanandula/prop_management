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

## UI regression check
```bash
python scripts/ui_regression_check.py
```

## Deploy to Fly.io
1. Install and login:
```bash
fly auth login
```
2. Create app (first time only) and keep the generated app name in `fly.toml`:
```bash
fly launch --no-deploy
```
3. Create a persistent volume for SQLite/uploads:
```bash
fly volumes create propman_data --region ord --size 10
```
4. Set production secret:
```bash
fly secrets set SECRET_KEY="replace-with-a-long-random-secret"
```
5. Deploy:
```bash
fly deploy
```

Notes:
- `fly.toml` is configured to use SQLite at `/data/property_mgmt.db` and uploads at `/data/uploads` via mounted volume.
- Update `app = "prop-management-v2"` in `fly.toml` if that Fly app name is already taken.
