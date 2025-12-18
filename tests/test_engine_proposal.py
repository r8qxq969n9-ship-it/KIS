"""Tests for Engine module - proposal generation"""

import os
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from kis.storage.init_db import init_database
from kis.storage.models import Snapshot, Proposal, EventLog, SchemaVersion, ProposalStatus
from kis.engine.sample_data import load_sample_snapshot
from kis.engine.proposal import create_proposal
from kis.engine.run import (
    save_snapshot,
    save_proposal,
    log_proposal_created,
    PHASE0_CONFIG
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{path}"
    
    # Initialize database
    init_database(db_url)
    
    yield db_url
    
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sample_snapshot_path():
    """Path to sample snapshot file"""
    return Path(__file__).parent.parent / "data" / "sample_snapshot.json"


@pytest.fixture
def sample_snapshot_data(sample_snapshot_path):
    """Load sample snapshot data"""
    return load_sample_snapshot(str(sample_snapshot_path))


def test_load_sample_snapshot_and_save(sample_snapshot_path, temp_db):
    """Test 1: 샘플 JSON 로드 및 snapshots 저장 성공"""
    # Load sample snapshot
    snapshot_data = load_sample_snapshot(str(sample_snapshot_path))
    
    # Verify loaded data
    assert 'asof' in snapshot_data
    assert 'source' in snapshot_data
    assert 'universe' in snapshot_data
    assert snapshot_data['source'] == 'sample'
    assert len(snapshot_data['universe']) > 0
    assert isinstance(snapshot_data['asof'], datetime)
    
    # Save to database
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        snapshot_id = save_snapshot(session, snapshot_data)
        assert snapshot_id > 0
        
        # Verify saved snapshot
        saved_snapshot = session.query(Snapshot).filter_by(snapshot_id=snapshot_id).first()
        assert saved_snapshot is not None
        assert saved_snapshot.source == 'sample'
        assert saved_snapshot.asof is not None
        assert saved_snapshot.payload_json is not None
        assert 'universe' in saved_snapshot.payload_json
        
    finally:
        session.close()


def test_proposal_constraints(sample_snapshot_data, temp_db):
    """Test 2: Proposal 생성 시 제약 통과 검증"""
    # Create proposal
    proposal_data = create_proposal(sample_snapshot_data, PHASE0_CONFIG)
    
    # Verify structure
    assert 'positions' in proposal_data
    assert 'constraints_check' in proposal_data
    assert 'correlation_id' in proposal_data
    
    positions = proposal_data['positions']
    constraints = proposal_data['constraints_check']
    
    # Verify positions <= 20
    assert len(positions) <= 20, f"Expected <= 20 positions, got {len(positions)}"
    
    # Verify each weight <= 0.08
    for pos in positions:
        assert pos['weight'] <= 0.08, f"Position {pos['symbol']} has weight {pos['weight']} > 0.08"
    
    # Calculate actual weights
    total_weight = sum(p['weight'] for p in positions)
    kr_weight_sum = sum(p['weight'] for p in positions if p['market'] == 'KR')
    us_weight_sum = sum(p['weight'] for p in positions if p['market'] == 'US')
    max_weight = max(p['weight'] for p in positions)
    
    # Verify KR weight sum = 0.4 (허용오차 1e-9)
    assert abs(kr_weight_sum - 0.4) < 1e-9, f"KR weight sum should be 0.4, got {kr_weight_sum}"
    
    # Verify US weight sum = 0.6 (허용오차 1e-9)
    assert abs(us_weight_sum - 0.6) < 1e-9, f"US weight sum should be 0.6, got {us_weight_sum}"
    
    # Verify total weight = 1.0 (허용오차 1e-9)
    assert abs(total_weight - 1.0) < 1e-9, f"Total weight should be 1.0, got {total_weight}"
    
    # Verify max weight <= 0.08
    assert max_weight <= 0.08, f"Max weight should be <= 0.08, got {max_weight}"
    
    # Verify constraints_check passed
    assert constraints['passed'] is True, "Constraints check should pass"
    assert constraints['actual_positions'] == len(positions)
    assert abs(constraints['actual_kr_weight'] - 0.4) < 1e-9
    assert abs(constraints['actual_us_weight'] - 0.6) < 1e-9
    assert abs(constraints['actual_total_weight'] - 1.0) < 1e-9


def test_proposal_save_fields(sample_snapshot_data, temp_db):
    """Test 3: proposals 테이블 저장 및 필드 존재 확인"""
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Save snapshot first
        snapshot_id = save_snapshot(session, sample_snapshot_data)
        
        # Create proposal
        proposal_data = create_proposal(sample_snapshot_data, PHASE0_CONFIG)
        
        # Save proposal
        proposal_id = save_proposal(session, proposal_data, snapshot_id, PHASE0_CONFIG)
        assert proposal_id > 0
        
        # Verify saved proposal
        saved_proposal = session.query(Proposal).filter_by(proposal_id=proposal_id).first()
        assert saved_proposal is not None
        
        # Verify required fields exist
        assert saved_proposal.universe_snapshot_id == snapshot_id
        assert saved_proposal.config_hash is not None
        assert len(saved_proposal.config_hash) == 64  # SHA256 hex length
        assert saved_proposal.git_commit_sha is not None
        assert saved_proposal.schema_version is not None
        assert saved_proposal.schema_version == "0.1.0"  # From init_db
        assert saved_proposal.status == ProposalStatus.PENDING
        
        # Verify payload_json
        assert saved_proposal.payload_json is not None
        assert 'positions' in saved_proposal.payload_json
        assert 'constraints_check' in saved_proposal.payload_json
        assert 'correlation_id' in saved_proposal.payload_json
        
        # Verify correlation_id matches
        assert saved_proposal.payload_json['correlation_id'] == proposal_data['correlation_id']
        
    finally:
        session.close()


def test_event_log_proposal_created(sample_snapshot_data, temp_db):
    """Test 4: event_log에 proposal_created 이벤트 기록 확인"""
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Save snapshot
        snapshot_id = save_snapshot(session, sample_snapshot_data)
        
        # Create and save proposal
        proposal_data = create_proposal(sample_snapshot_data, PHASE0_CONFIG)
        proposal_id = save_proposal(session, proposal_data, snapshot_id, PHASE0_CONFIG)
        
        # Log event
        log_proposal_created(
            session,
            proposal_id,
            snapshot_id,
            proposal_data['correlation_id'],
            proposal_data['constraints_check']['passed']
        )
        
        # Verify event logged
        events = session.query(EventLog).filter_by(
            event_type="proposal_created",
            correlation_id=proposal_data['correlation_id']
        ).all()
        
        assert len(events) >= 1, "At least one proposal_created event should be logged"
        
        # Verify event details
        event = events[0]
        assert event.actor == "engine"
        assert event.correlation_id == proposal_data['correlation_id']
        assert event.payload_json is not None
        assert event.payload_json['proposal_id'] == proposal_id
        assert event.payload_json['snapshot_id'] == snapshot_id
        assert event.payload_json['constraints_passed'] == proposal_data['constraints_check']['passed']
        
    finally:
        session.close()


def test_proposal_insufficient_stocks():
    """Test 5: 부족 데이터 케이스 에러 테스트 (KR < 5 또는 US < 8)"""
    # Test with insufficient KR stocks
    insufficient_kr_snapshot = {
        'asof': datetime.now(timezone.utc),
        'source': 'test',
        'universe': [
            {"symbol": "005930.KS", "market": "KR", "score": 100},
            {"symbol": "000660.KS", "market": "KR", "score": 99},
            {"symbol": "035420.KS", "market": "KR", "score": 98},
            {"symbol": "051910.KS", "market": "KR", "score": 97},
            # Only 4 KR stocks (need 5)
            {"symbol": "AAPL", "market": "US", "score": 100},
            {"symbol": "MSFT", "market": "US", "score": 99},
            {"symbol": "GOOGL", "market": "US", "score": 98},
            {"symbol": "AMZN", "market": "US", "score": 97},
            {"symbol": "NVDA", "market": "US", "score": 96},
            {"symbol": "META", "market": "US", "score": 95},
            {"symbol": "TSLA", "market": "US", "score": 94},
            {"symbol": "BRK.B", "market": "US", "score": 93},
        ]
    }
    
    with pytest.raises(ValueError, match="Insufficient KR stocks"):
        create_proposal(insufficient_kr_snapshot, PHASE0_CONFIG)
    
    # Test with insufficient US stocks
    insufficient_us_snapshot = {
        'asof': datetime.now(timezone.utc),
        'source': 'test',
        'universe': [
            {"symbol": "005930.KS", "market": "KR", "score": 100},
            {"symbol": "000660.KS", "market": "KR", "score": 99},
            {"symbol": "035420.KS", "market": "KR", "score": 98},
            {"symbol": "051910.KS", "market": "KR", "score": 97},
            {"symbol": "006400.KS", "market": "KR", "score": 96},
            {"symbol": "AAPL", "market": "US", "score": 100},
            {"symbol": "MSFT", "market": "US", "score": 99},
            {"symbol": "GOOGL", "market": "US", "score": 98},
            {"symbol": "AMZN", "market": "US", "score": 97},
            {"symbol": "NVDA", "market": "US", "score": 96},
            {"symbol": "META", "market": "US", "score": 95},
            {"symbol": "TSLA", "market": "US", "score": 94},
            # Only 7 US stocks (need 8)
        ]
    }
    
    with pytest.raises(ValueError, match="Insufficient US stocks"):
        create_proposal(insufficient_us_snapshot, PHASE0_CONFIG)

