"""
Database connection setup.

Uses SQLite by default so the app runs with zero external setup.
To move to PostgreSQL later (e.g. on Railway/Render/DigitalOcean), just change
DATABASE_URL to something like:
    postgresql://user:password@host:5432/endotrack
and add `psycopg2-binary` to requirements.txt. Nothing else in the app needs
to change because SQLAlchemy abstracts the driver.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./endotrack.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
