# QueueSmart - Assignment 4

QueueSmart is a FastAPI, SQLite, HTML, CSS, and JavaScript queue-management application. This version extends the Assignment 2 front end and Assignment 3 REST APIs with a real relational database.

## Project Structure

```text
backend/   FastAPI routes, SQLAlchemy models, SQLite configuration, validation, security, schema
frontend/  Assignment 2-style screens, custom SVG logo, CSS, JavaScript API integration
tests/     Unit/API/database persistence tests
docs/      Assignment 4 submission document, schema copy, and coverage evidence
```

## Database

- SQLite file: `backend/queuesmart.db` (created automatically)
- ORM: SQLAlchemy 2
- Schema SQL: `backend/schema.sql`
- Passwords: salted PBKDF2-SHA256 hashes; plain-text passwords are never stored
- Foreign-key enforcement: enabled with `PRAGMA foreign_keys=ON`

## Run in VS Code / Terminal

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`.

Demo accounts:

- User: `user@queuesmart.example` / `User123!`
- Administrator: `admin@queuesmart.example` / `Admin123!`

## Run Tests and Coverage

```bash
coverage erase
coverage run -m pytest
coverage report -m
```

The included test suite checks authentication, database constraints, service persistence, queue persistence, notifications, history, role authorization, and front-end serving.


