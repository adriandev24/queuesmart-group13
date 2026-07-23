# QueueSmart - Assignment 3

QueueSmart is a smart queue management web application. This Assignment 3 version extends the Assignment 2 front end with a FastAPI back end, REST API integration, validation, role handling, in-memory storage, notifications, history, wait-time estimation, and unit tests.

## Required Assignment 3 Features

- User registration and login authentication
- User and administrator roles
- Create, update, and list services
- Join and leave queues
- Administrator queue view and serve-next action
- Queue ordering by priority and arrival order
- Wait-time estimation using `position x expected duration`
- Join and almost-ready notifications
- Queue participation history
- Required-field, type, and length validation
- Front-end calls to backend APIs
- In-memory data only; no persistent database
- Unit tests covering business logic and validation

## Technology

- Front end: HTML5, CSS3, and JavaScript
- Back end: Python 3 and FastAPI
- Server: Uvicorn
- Validation: Pydantic models
- Tests: pytest and FastAPI TestClient
- Coverage: coverage.py

## Project Structure

```text
QueueSmart_Assignment3_Group13/
├── backend/
│   ├── business.py
│   ├── main.py
│   ├── models.py
│   ├── security.py
│   └── store.py
├── frontend/
│   ├── assets/queuesmart-logo.svg
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── tests/
├── requirements.txt
├── pytest.ini
└── README.md
```

## Run the Application

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`.

FastAPI's generated API documentation is available at `http://127.0.0.1:8000/docs`.

## Demo Accounts

- User: `user@queuesmartapp.com` / `UserPass123`
- Administrator: `admin@queuesmartapp.com` / `AdminPass123`

## Run Tests and Coverage

```bash
coverage erase
coverage run -m pytest
coverage report -m
```

Verified result for this package: **25 tests passed and 95% backend code coverage**.

## Main REST Endpoints

| Method | Endpoint | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | Public | Register an account |
| POST | `/api/auth/login` | Public | Authenticate and receive a session token |
| GET | `/api/services` | Public | List services and queue lengths |
| GET | `/api/services/{id}/estimate` | Public | Return backend wait estimate |
| POST | `/api/services` | Administrator | Create a service |
| PUT | `/api/services/{id}` | Administrator | Update a service |
| POST | `/api/queues/join` | User | Join a queue |
| DELETE | `/api/queues/{service_id}/leave` | User | Leave a queue |
| GET | `/api/queues/status` | User | View current queue status |
| GET | `/api/admin/queues/{service_id}` | Administrator | View an ordered queue |
| POST | `/api/admin/queues/{service_id}/serve-next` | Administrator | Serve the next user |
| GET | `/api/notifications` | User | View notifications |
| GET | `/api/history` | User | View queue history |

## Storage Note

All data is held in Python lists and dictionaries while the server is running. Restarting the server resets the sample data. No database or external email/SMS service is implemented because Assignment 3 explicitly defers persistence and permits notifications to be returned to the front end.
