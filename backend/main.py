from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .business import (
    admin_dashboard,
    create_service,
    estimate_wait,
    join_queue,
    leave_queue,
    list_services,
    login_user,
    queue_for_admin,
    register_user,
    serve_next,
    update_service,
    user_dashboard,
    user_history,
    user_notifications,
    user_queue_status,
)
from .models import JoinQueueRequest, LoginRequest, RegisterRequest, ServiceCreateRequest, ServiceUpdateRequest
from .store import store

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="QueueSmart API", version="1.0.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        details.append(
            {
                "field": ".".join(str(part) for part in error["loc"] if part != "body"),
                "message": error["msg"],
                "type": error["type"],
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error": "Validation failed", "details": details},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token required")
    token = authorization.removeprefix("Bearer ").strip()
    user_id = store.sessions.get(token)
    user = store.find_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token")
    return user


def require_role(role: str):
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{role.title()} role required")
        return user

    return dependency


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "in-memory"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest) -> dict[str, Any]:
    user, token = register_user(data, store)
    return {"message": "Registration successful", "token": token, "user": user}


@app.post("/api/auth/login")
def login(data: LoginRequest) -> dict[str, Any]:
    user, token = login_user(data, store)
    return {"message": "Login successful", "token": token, "user": user}


@app.get("/api/services")
def services() -> dict[str, Any]:
    return {"services": list_services(store)}


@app.get("/api/services/{service_id}/estimate")
def service_estimate(service_id: int) -> dict[str, int]:
    return estimate_wait(service_id, store)


@app.post("/api/services", status_code=status.HTTP_201_CREATED)
def add_service(
    data: ServiceCreateRequest,
    admin: dict[str, Any] = Depends(require_role("administrator")),
) -> dict[str, Any]:
    return {"message": "Service created", "service": create_service(data, store)}


@app.put("/api/services/{service_id}")
def edit_service(
    service_id: int,
    data: ServiceUpdateRequest,
    admin: dict[str, Any] = Depends(require_role("administrator")),
) -> dict[str, Any]:
    return {"message": "Service updated", "service": update_service(service_id, data, store)}


@app.post("/api/queues/join", status_code=status.HTTP_201_CREATED)
def queue_join(
    data: JoinQueueRequest,
    user: dict[str, Any] = Depends(require_role("user")),
) -> dict[str, Any]:
    return {"message": "Queue joined", "queue_entry": join_queue(user, data, store)}


@app.delete("/api/queues/{service_id}/leave")
def queue_leave(
    service_id: int,
    user: dict[str, Any] = Depends(require_role("user")),
) -> dict[str, Any]:
    return {"message": "Queue left", "history": leave_queue(user, service_id, store)}


@app.get("/api/queues/status")
def queue_status(user: dict[str, Any] = Depends(require_role("user"))) -> dict[str, Any]:
    return {"queue_status": user_queue_status(user, store)}


@app.get("/api/admin/queues/{service_id}")
def admin_queue(
    service_id: int,
    admin: dict[str, Any] = Depends(require_role("administrator")),
) -> dict[str, Any]:
    return {"queue": queue_for_admin(service_id, store)}


@app.post("/api/admin/queues/{service_id}/serve-next")
def admin_serve_next(
    service_id: int,
    admin: dict[str, Any] = Depends(require_role("administrator")),
) -> dict[str, Any]:
    return {"message": "Next user served", **serve_next(service_id, store)}


@app.get("/api/notifications")
def notifications(user: dict[str, Any] = Depends(require_role("user"))) -> dict[str, Any]:
    return {"notifications": user_notifications(user, store)}


@app.get("/api/history")
def history(user: dict[str, Any] = Depends(require_role("user"))) -> dict[str, Any]:
    return {"history": user_history(user, store)}


@app.get("/api/dashboard/user")
def dashboard_user(user: dict[str, Any] = Depends(require_role("user"))) -> dict[str, Any]:
    return user_dashboard(user, store)


@app.get("/api/dashboard/admin")
def dashboard_admin(admin: dict[str, Any] = Depends(require_role("administrator"))) -> dict[str, Any]:
    return admin_dashboard(store)
