"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import init_db
from app.routers import (
    auth, tournaments, divisions, competitors,
    brackets, scheduling, audit, sync_routes, events,
    registrations
)

app = FastAPI(
    title="Kickboxing Tournament Tracker",
    description="Single-elimination kickboxing tournament management system",
    version="1.0.0",
)

# CORS
origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(tournaments.router)
app.include_router(divisions.router)
app.include_router(competitors.router)
app.include_router(brackets.router)
app.include_router(scheduling.router)
app.include_router(audit.router)
app.include_router(sync_routes.router)
app.include_router(events.router)
app.include_router(registrations.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "mode": settings.APP_MODE,
        "database": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql",
    }


# Serve frontend static files in production
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
