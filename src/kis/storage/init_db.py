"""Database initialization script with idempotency guarantee"""

import os
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from kis.storage.models import Base, SchemaVersion

# Default to SQLite, but allow DATABASE_URL override for Postgres
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///kis_trading.db")


def create_event_log_triggers(engine):
    """Create append-only triggers for event_log table (SQLite)"""
    # Check if triggers already exist
    inspector = inspect(engine)
    
    # SQLite-specific: Create triggers to prevent UPDATE/DELETE on event_log
    trigger_sql = """
    -- Drop existing triggers if they exist (idempotent)
    DROP TRIGGER IF EXISTS prevent_event_log_update;
    DROP TRIGGER IF EXISTS prevent_event_log_delete;
    
    -- Create trigger to prevent UPDATE
    CREATE TRIGGER prevent_event_log_update
    BEFORE UPDATE ON event_log
    BEGIN
        SELECT RAISE(ABORT, 'event_log is append-only: UPDATE not allowed');
    END;
    
    -- Create trigger to prevent DELETE
    CREATE TRIGGER prevent_event_log_delete
    BEFORE DELETE ON event_log
    BEGIN
        SELECT RAISE(ABORT, 'event_log is append-only: DELETE not allowed');
    END;
    """
    
    with engine.connect() as conn:
        conn.execute(text(trigger_sql))
        conn.commit()


def init_database(database_url: Optional[str] = None) -> None:
    """
    Initialize database with idempotency guarantee.
    
    This function can be called multiple times safely:
    - Creates tables if they don't exist
    - Creates triggers if they don't exist
    - Records schema version if not already recorded
    
    Args:
        database_url: Optional database URL. If not provided, uses DATABASE_URL env var or SQLite default.
    """
    db_url = database_url or DATABASE_URL
    
    # Create engine
    engine = create_engine(db_url, echo=False)
    
    # Create all tables (idempotent - won't recreate if they exist)
    Base.metadata.create_all(engine)
    
    # Create event_log append-only triggers (SQLite)
    if db_url.startswith("sqlite"):
        create_event_log_triggers(engine)
    
    # Record schema version (idempotent)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if schema version already exists
        current_version = "0.1.0"
        existing = session.query(SchemaVersion).filter_by(schema_version=current_version).first()
        
        if not existing:
            schema_version = SchemaVersion(
                schema_version=current_version,
                applied_at=datetime.now(timezone.utc),
                description="Phase 0 initial schema with append-only event_log"
            )
            session.add(schema_version)
            session.commit()
            print(f"Schema version {current_version} recorded.")
        else:
            print(f"Schema version {current_version} already exists.")
    
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    
    print(f"Database initialized successfully at: {db_url}")


if __name__ == "__main__":
    init_database()

