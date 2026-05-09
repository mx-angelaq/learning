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
# `allow_credentials=True` combined with `allow_origins=["*"]` is invalid per
# the CORS spec and silently rejected by browsers, so when the wildcard is in
# effect we drop credentials. The regex covers Vercel preview/production URLs
# whose hostnames change per-deploy.
if settings.CORS_ORIGINS == "*":
    cors_origins = ["*"]
    cors_credentials = False
else:
    cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    cors_credentials = True
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=cors_credentials,
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
