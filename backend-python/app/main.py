from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import close_db, connect_db
from app.routes.auth_routes import router as auth_router
from app.routes.job_routes import router as job_router
from app.routes.resume_routes import router as resume_router

app = FastAPI(title="Resume Ranker Backend", version="1.0.0")
UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

if settings.cors_origin_list == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"error": "Invalid request payload."})


@app.exception_handler(Exception)
async def generic_exception_handler(_, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.on_event("startup")
def on_startup() -> None:
    connect_db()


@app.on_event("shutdown")
def on_shutdown() -> None:
    close_db()


@app.get("/api/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "resume-ranker-backend",
        "auth": "enabled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(job_router)
