"""Tests for database initialization and append-only event_log"""

import os
import tempfile
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from kis.storage.init_db import init_database
from kis.storage.models import (
    Base,
    EventLog,
    Snapshot,
    Proposal,
    Approval,
    Order,
    Fill,
    SystemState,
    SchemaVersion,
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{path}"
    
    yield db_url
    
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


def test_init_db_idempotency(temp_db):
    """Test that init_database can be called twice without errors"""
    # First call
    init_database(temp_db)
    
    # Second call should not fail
    init_database(temp_db)
    
    # Verify database exists and is accessible
    engine = create_engine(temp_db)
    inspector = inspect(engine)
    assert inspector is not None


def test_required_tables_exist(temp_db):
    """Test that all required tables exist after initialization"""
    init_database(temp_db)
    
    engine = create_engine(temp_db)
    inspector = inspect(engine)
    
    required_tables = [
        "event_log",
        "snapshots",
        "proposals",
        "approvals",
        "orders",
        "fills",
        "system_state",
        "schema_version",
    ]
    
    existing_tables = inspector.get_table_names()
    
    for table in required_tables:
        assert table in existing_tables, f"Table {table} should exist"


def test_schema_version_recorded(temp_db):
    """Test that schema_version is recorded after initialization"""
    init_database(temp_db)
    
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        schema_version = session.query(SchemaVersion).filter_by(schema_version="0.1.0").first()
        assert schema_version is not None, "Schema version 0.1.0 should be recorded"
        assert schema_version.schema_version == "0.1.0"
        assert schema_version.applied_at is not None
    finally:
        session.close()


def test_event_log_append_only(temp_db):
    """Test that event_log UPDATE and DELETE operations fail (append-only enforcement)"""
    init_database(temp_db)
    
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Insert a test event
        test_event = EventLog(
            timestamp="2024-01-01T00:00:00+00:00",
            event_type="test_event",
            correlation_id="test-correlation-1",
            actor="test",
            payload_json={"test": "data"}
        )
        session.add(test_event)
        session.commit()
        
        # Get the event_id
        event = session.query(EventLog).filter_by(correlation_id="test-correlation-1").first()
        assert event is not None
        event_id = event.event_id
        
        # Try to UPDATE - should fail
        with pytest.raises(OperationalError) as exc_info:
            session.query(EventLog).filter_by(event_id=event_id).update({
                "event_type": "modified"
            })
            session.commit()
        
        assert "UPDATE not allowed" in str(exc_info.value) or "append-only" in str(exc_info.value).lower()
        
        # Try to DELETE - should fail
        with pytest.raises(OperationalError) as exc_info:
            session.query(EventLog).filter_by(event_id=event_id).delete()
            session.commit()
        
        assert "DELETE not allowed" in str(exc_info.value) or "append-only" in str(exc_info.value).lower()
        
        # Verify the event still exists
        event_after = session.query(EventLog).filter_by(event_id=event_id).first()
        assert event_after is not None, "Event should still exist after failed UPDATE/DELETE"
        
    finally:
        session.close()

