"""
Database connection setup.

Uses SQLite by default so the app runs with zero external setup. To use
PostgreSQL instead, create a `.env` file (see `.env.example`) with:
    DATABASE_URL=postgresql://user:password@localhost:5432/endotrack
Nothing else in the app needs to change -- SQLAlchemy abstracts the driver,
and every existing query, model, and endpoint works unmodified against
Postgres.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()  # reads a .env file in the working directory, if present

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

