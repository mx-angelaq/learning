"""Database setup supporting SQLite (local) and PostgreSQL (hosted)."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# Enable WAL mode for SQLite for better concurrent reads
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables, then run any pending data migrations."""
    from app.models import db_models  # noqa: F401
    from app.migrations.kg_to_lbs import migrate as migrate_kg_to_lbs

    # Self-heal kg-era databases before create_all, so an ALTER COLUMN runs
    # against the existing schema. create_all is a no-op for already-existing
    # tables, so order only matters when columns differ.
    migrate_kg_to_lbs(engine)
    Base.metadata.create_all(bind=engine)
