"""Database session utilities for FastAPI"""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from kis.storage.init_db import DATABASE_URL


# Global engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine"""
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL", DATABASE_URL)
        _engine = create_engine(database_url, echo=False)
    return _engine


def get_session_factory():
    """Get or create session factory"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session.
    
    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db_session)):
            ...
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

