# QueueSmart - Final Project (Group 13)

QueueSmart is the completed COSC 4353 smart queue management application. This repository preserves the Assignment 2 plain HTML/CSS/JavaScript front end, the Assignment 3 FastAPI REST API structure, and the Assignment 4 SQLite/SQLAlchemy persistence layer. The final project adds administrator CSV reporting and a data-assisted **Suggested Best Time to Join a Queue** feature.

## Final-project requirements implemented

- Front end: user and administrator screens with responsive navigation.
- Backend APIs: authentication, profile, services, queues, wait estimates, notifications, history, and administrator operations.
- Database persistence: SQLite + SQLAlchemy with foreign keys, constraints, hashed passwords, and persistent session tokens.
- Reporting: administrator-only report preview and CSV export with users/history, service activity, and usage statistics.
- Smart feature: historical best-time recommendation with a current-load fallback.
- Unit/API/database tests and coverage configuration.
- Demo seed data and a sample generated CSV report.

## Project structure

```text
QueueSmart_Final_Group13/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── logic.py
│   └── schema.sql
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── assets/queuesmart-logo.svg
├── tests/
├── scripts/
│   ├── seed_demo.py
│   └── generate_sample_report.py
├── reports/sample_queue_report.csv
├── docs/
├── requirements.txt
└── README.md
```

## Run in VS Code / Terminal

Use Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows PowerShell
pip install -r requirements.txt
python scripts/seed_demo.py
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`.

Demo credentials after running the seed script:

- Administrator: `admin@queuesmart.local` / `Admin123!`
- User: `student@queuesmart.local` / `Student123!`

The database is created automatically at `backend/queuesmart.db` and is intentionally ignored by Git. Run `python scripts/seed_demo.py` again if you need to restore missing demo records; the script avoids duplicating its initial history dataset.

## Reporting demo

1. Sign in as the administrator.
2. Open **Reporting**.
3. Optionally set a date range or service filter.
4. Select **Generate Report** to display statistics, service activity, and customer participation history.
5. Select **Export CSV** to download the report.

The same data is available through:

- `GET /api/admin/reports/summary`
- `GET /api/admin/reports/export.csv`

## Smart-feature demo

1. Sign in as the regular user.
2. Open **User Dashboard**.
3. Select a service in **Join a Queue**.
4. Select **Suggest Best Time**.

QueueSmart analyzes served history by join hour and recommends the lowest historical wait/traffic window. The demo seed provides history so the historical logic is visible immediately.

## Tests and coverage

```bash
coverage erase
coverage run -m pytest
coverage report -m
```



