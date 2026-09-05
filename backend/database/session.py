"""
SQLAlchemy Engine & Session Management for RecoverAI.
Supports SQLite out-of-the-box and PostgreSQL seamlessly.
"""

import os
import shutil
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from backend.config import settings

db_url = settings.DATABASE_URL

# Handle Vercel serverless read-only filesystem
is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") or os.environ.get("LAMBDA_TASK_ROOT"))

if is_vercel and db_url.startswith("sqlite"):
    tmp_db = "/tmp/recoverai.db"
    if not os.path.exists(tmp_db):
        candidates = [
            "recoverai.db",
            "/var/task/recoverai.db",
            os.path.join(os.getcwd(), "recoverai.db"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "recoverai.db")
        ]
        for cand in candidates:
            if os.path.exists(cand):
                try:
                    shutil.copyfile(cand, tmp_db)
                    break
                except Exception:
                    pass
    db_url = f"sqlite:///{tmp_db}"

# Configure SQLite specific engine options if using sqlite
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(
    db_url,
    echo=settings.ECHO_SQL,
    connect_args=connect_args,
)

if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            if not is_vercel:
                cursor.execute("PRAGMA journal_mode=WAL")
            else:
                cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        finally:
            cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base class for all RecoverAI models."""
    pass

def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and ensures clean closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Initialize database tables."""
    # Import all models to ensure they register with Base.metadata before creation
    import backend.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    if db_url.startswith("sqlite"):
        with engine.begin() as conn:
            try:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
                conn.exec_driver_sql("PRAGMA busy_timeout=30000;")
            except Exception:
                pass

