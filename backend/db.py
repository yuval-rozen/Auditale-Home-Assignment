# backend/db.py
"""
backend/db.py

Database configuration and session management for the Customer Health App.

This module sets up the SQLAlchemy engine, session factory, and declarative base
for ORM models. It also defines a FastAPI dependency (`get_db`) that provides
a scoped database session to API request handlers.

Key features:
- Uses PostgreSQL (default connection string points to the `db` service in Docker).
- Connection is robust to transient DB restarts (`pool_pre_ping=True`).
- Compatible with SQLAlchemy 2.0 (`future=True`).
- Provides a clean session management pattern for FastAPI routes.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# -----------------------------------------------------------------------------
# Database URL configuration
# -----------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/healthdb",
)

# Robust to brief DB restarts; SQLAlchemy v2-compatible
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


# FastAPI dependency
def get_db():
    """
    Provide a SQLAlchemy database session to FastAPI request handlers.

    Usage in a FastAPI route:
        @app.get("/items/{item_id}")
        def read_item(item_id: int, db: Session = Depends(get_db)):
            return db.query(Item).filter(Item.id == item_id).first()

    Yields:
        Session: A SQLAlchemy session connected to the configured database.

    Ensures:
        - A session is opened when the request starts.
        - The session is closed automatically when the request ends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
