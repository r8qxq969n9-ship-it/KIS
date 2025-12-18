"""Tests for Execution Server approval gate"""

import os
import tempfile
import pytest
import hashlib
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from kis.storage.init_db import init_database
from kis.storage.models import (
    Proposal,
    Approval,
    Order,
    EventLog,
    SystemState,
    ProposalStatus,
    ApprovalStatus,
    KillSwitchStatus
)
from kis.execution.app import app, broker_client as app_broker_client
from kis.execution.broker import SpyBrokerClient
from kis.execution.auth import create_token, calculate_token_hash
from kis.execution.config import get_jwt_secret
from kis.storage.session import get_db_session


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
def test_proposal(temp_db):
    """Create a test proposal in the database"""
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        proposal = Proposal(
            created_at=datetime.now(timezone.utc),
            universe_snapshot_id=1,
            config_hash="test_hash",
            git_commit_sha="test_sha",
            schema_version="0.1.0",
            payload_json={
                "positions": [],
                "constraints_check": {"passed": True},
                "correlation_id": "test-correlation-123"
            },
            status=ProposalStatus.PENDING
        )
        session.add(proposal)
        session.commit()
        session.refresh(proposal)
        return proposal
    finally:
        session.close()


@pytest.fixture
def test_approval(temp_db, test_proposal):
    """Create a test approval with token in the database"""
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Create token
        secret = "test-secret-key-12345"
        token_jti = "test-jti-12345"
        token = create_token(
            secret=secret,
            jti=token_jti,
            proposal_id=test_proposal.proposal_id,
            correlation_id="test-correlation-123",
            proposal_payload_hash="test-hash",
            expires_in_seconds=3600
        )
        token_hash = calculate_token_hash(token)
        
        approval = Approval(
            proposal_id=test_proposal.proposal_id,
            status=ApprovalStatus.APPROVED,
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
            token_hash=token_hash,
            token_jti=token_jti,
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=3600),
            token_used_at=None,
            rejection_reason=None
        )
        session.add(approval)
        session.commit()
        session.refresh(approval)
        
        return {
            "approval": approval,
            "token": token,
            "token_jti": token_jti,
            "secret": secret
        }
    finally:
        session.close()


@pytest.fixture
def client(temp_db):
    """Create FastAPI test client with database dependency override"""
    # Override database dependency
    def override_get_db():
        engine = create_engine(temp_db)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()
    
    app.dependency_overrides[get_db_session] = override_get_db
    
    # Replace broker client with spy
    import kis.execution.app as execution_app
    spy_broker = SpyBrokerClient()
    original_broker = execution_app.broker_client
    execution_app.broker_client = spy_broker
    
    yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()
    execution_app.broker_client = original_broker


def test_no_token(client, test_proposal, temp_db):
    """Test 1: 토큰 없음 -> 401/403 + broker calls == 0 + event_log 기록"""
    import kis.execution.app as execution_app
    spy = execution_app.broker_client
    spy.reset()
    
    # Try to place order without token
    response = client.post(
        "/place_order",
        json={"order_intent": {"symbol": "AAPL", "quantity": 10}}
    )
    
    assert response.status_code in [401, 403]
    assert spy.call_count == 0  # Broker never called
    
    # Verify event_log
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        events = session.query(EventLog).filter_by(
            event_type="order_rejected"
        ).all()
        assert len(events) >= 1
    finally:
        session.close()


def test_invalid_token_signature(client, test_proposal, test_approval, temp_db):
    """Test 2: 토큰 위변조(서명 불일치) -> 401/403 + broker calls == 0 + event_log 기록"""
    import kis.execution.app as execution_app
    spy = execution_app.broker_client
    spy.reset()
    
    # Set kill switch to inactive
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        kill_switch = SystemState(
            timestamp=datetime.now(timezone.utc),
            kill_switch_status=KillSwitchStatus.INACTIVE,
            kill_switch_reason=None
        )
        session.add(kill_switch)
        session.commit()
    finally:
        session.close()
    
    # Use wrong secret to create invalid token
    wrong_secret = "wrong-secret"
    invalid_token = create_token(
        secret=wrong_secret,
        jti="invalid-jti-123",
        proposal_id=test_proposal.proposal_id,
        correlation_id="test-correlation-123",
        proposal_payload_hash="test-hash",
        expires_in_seconds=3600
    )
    
    # Set correct secret for server
    os.environ["EXECUTION_JWT_SECRET"] = test_approval["secret"]
    
    try:
        response = client.post(
            "/place_order",
            json={"order_intent": {"symbol": "AAPL", "quantity": 10}},
            headers={"Authorization": f"Bearer {invalid_token}"}
        )
        
        assert response.status_code in [401, 403]
        assert spy.call_count == 0  # Broker never called
        
        # Verify event_log
        engine = create_engine(temp_db)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            events = session.query(EventLog).filter_by(
                event_type="order_rejected"
            ).all()
            assert len(events) >= 1
            # Check that reason mentions signature
            assert any("signature" in str(e.payload_json).lower() for e in events)
        finally:
            session.close()
    finally:
        if "EXECUTION_JWT_SECRET" in os.environ:
            del os.environ["EXECUTION_JWT_SECRET"]


def test_expired_token(client, test_proposal, test_approval, temp_db):
    """Test 3: 토큰 만료(expired) -> 403 + broker calls == 0 + event_log 기록"""
    import kis.execution.app as execution_app
    spy = execution_app.broker_client
    spy.reset()
    
    # Set kill switch to inactive
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        kill_switch = SystemState(
            timestamp=datetime.now(timezone.utc),
            kill_switch_status=KillSwitchStatus.INACTIVE,
            kill_switch_reason=None
        )
        session.add(kill_switch)
        session.commit()
    finally:
        session.close()
    
    # Create expired token
    secret = test_approval["secret"]
    expired_token = create_token(
        secret=secret,
        jti="expired-jti",
        proposal_id=test_proposal.proposal_id,
        correlation_id="test-correlation-123",
        proposal_payload_hash="test-hash",
        expires_in_seconds=-1  # Already expired
    )
    
    # Create approval for expired token
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        expired_hash = calculate_token_hash(expired_token)
        expired_approval = Approval(
            proposal_id=test_proposal.proposal_id,
            status=ApprovalStatus.APPROVED,
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
            token_hash=expired_hash,
            token_jti="expired-jti",
            token_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            token_used_at=None,
            rejection_reason=None
        )
        session.add(expired_approval)
        session.commit()
    finally:
        session.close()
    
    os.environ["EXECUTION_JWT_SECRET"] = secret
    
    try:
        response = client.post(
            "/place_order",
            json={"order_intent": {"symbol": "AAPL", "quantity": 10}},
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 403
        assert spy.call_count == 0  # Broker never called
        
        # Verify event_log - refresh session to see committed events
        engine = create_engine(temp_db)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            # Query all events (may need to refresh to see committed events)
            all_events = session.query(EventLog).all()
            # If no events found, try querying with filter
            if len(all_events) == 0:
                # Wait a bit and retry (for async commit)
                import time
                time.sleep(0.1)
                all_events = session.query(EventLog).all()
            assert len(all_events) >= 1, f"Expected at least 1 event, got {len(all_events)}. All events: {[e.event_type for e in all_events]}"
            # Check that reason mentions expired
            event_payloads = [str(e.payload_json).lower() for e in all_events]
            assert any("expired" in p for p in event_payloads), f"Event payloads: {event_payloads}"
        finally:
            session.close()
    finally:
        if "EXECUTION_JWT_SECRET" in os.environ:
            del os.environ["EXECUTION_JWT_SECRET"]


def test_token_reuse(client, test_proposal, test_approval, temp_db):
    """Test 4: 토큰 재사용(첫 성공 후 동일 토큰으로 2회 호출) -> 두 번째는 403 + broker calls 증가 없음(총 1회) + event_log 기록"""
    import kis.execution.app as execution_app
    spy = execution_app.broker_client
    spy.reset()
    
    # Set kill switch to inactive
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        kill_switch = SystemState(
            timestamp=datetime.now(timezone.utc),
            kill_switch_status=KillSwitchStatus.INACTIVE,
            kill_switch_reason=None
        )
        session.add(kill_switch)
        session.commit()
    finally:
        session.close()
    
    os.environ["EXECUTION_JWT_SECRET"] = test_approval["secret"]
    
    try:
        # First call - should succeed
        response1 = client.post(
            "/place_order",
            json={"order_intent": {"symbol": "AAPL", "quantity": 10}},
            headers={"Authorization": f"Bearer {test_approval['token']}"}
        )
        
        assert response1.status_code == 200
        assert spy.call_count == 1  # First call succeeded
        
        # Second call with same token - should fail
        response2 = client.post(
            "/place_order",
            json={"order_intent": {"symbol": "MSFT", "quantity": 5}},
            headers={"Authorization": f"Bearer {test_approval['token']}"}
        )
        
        assert response2.status_code == 403
        assert spy.call_count == 1  # No additional call (still 1)
        
        # Verify event_log
        engine = create_engine(temp_db)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            events = session.query(EventLog).filter_by(
                event_type="order_rejected"
            ).all()
            assert len(events) >= 1
            assert any("already used" in str(e.payload_json).lower() for e in events)
        finally:
            session.close()
    finally:
        if "EXECUTION_JWT_SECRET" in os.environ:
            del os.environ["EXECUTION_JWT_SECRET"]


def test_kill_switch_active(client, test_proposal, test_approval, temp_db):
    """Test 5: kill_switch active -> 403 + broker calls == 0 + event_log 기록 (토큰 유효하더라도)"""
    import kis.execution.app as execution_app
    spy = execution_app.broker_client
    spy.reset()
    
    # Set kill switch to active
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        kill_switch = SystemState(
            timestamp=datetime.now(timezone.utc),
            kill_switch_status=KillSwitchStatus.ACTIVE,
            kill_switch_reason="Test kill switch"
        )
        session.add(kill_switch)
        session.commit()
    finally:
        session.close()
    
    os.environ["EXECUTION_JWT_SECRET"] = test_approval["secret"]
    
    try:
        response = client.post(
            "/place_order",
            json={"order_intent": {"symbol": "AAPL", "quantity": 10}},
            headers={"Authorization": f"Bearer {test_approval['token']}"}
        )
        
        assert response.status_code == 403
        assert "kill switch" in response.json()['detail'].lower()
        assert spy.call_count == 0  # Broker never called (kill switch checked first)
        
        # Verify event_log
        engine = create_engine(temp_db)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            events = session.query(EventLog).filter_by(
                event_type="order_blocked_killswitch"
            ).all()
            assert len(events) >= 1
        finally:
            session.close()
    finally:
        if "EXECUTION_JWT_SECRET" in os.environ:
            del os.environ["EXECUTION_JWT_SECRET"]


def test_success_case(client, test_proposal, test_approval, temp_db):
    """Test 6: 성공 케이스 -> 200 + broker calls == 1 + approvals.token_used_at이 set됨 + orders row 생성"""
    import kis.execution.app as execution_app
    spy = execution_app.broker_client
    spy.reset()
    
    # Set kill switch to inactive
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        kill_switch = SystemState(
            timestamp=datetime.now(timezone.utc),
            kill_switch_status=KillSwitchStatus.INACTIVE,
            kill_switch_reason=None
        )
        session.add(kill_switch)
        session.commit()
    finally:
        session.close()
    
    os.environ["EXECUTION_JWT_SECRET"] = test_approval["secret"]
    
    try:
        response = client.post(
            "/place_order",
            json={"order_intent": {"symbol": "AAPL", "quantity": 10}},
            headers={"Authorization": f"Bearer {test_approval['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "order_id" in data
        assert "status" in data
        assert spy.call_count == 1  # Broker called exactly once
        
        # Verify approval.token_used_at is set
        engine = create_engine(temp_db)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            approval = session.query(Approval).filter_by(
                approval_id=test_approval["approval"].approval_id
            ).first()
            assert approval.token_used_at is not None
            
            # Verify order was created
            order = session.query(Order).filter_by(
                order_id=data["order_id"]
            ).first()
            assert order is not None
            assert order.correlation_id == "test-correlation-123"
            
            # Verify event_log
            events = session.query(EventLog).filter_by(
                event_type="order_requested",
                correlation_id="test-correlation-123"
            ).all()
            assert len(events) >= 1
        finally:
            session.close()
    finally:
        if "EXECUTION_JWT_SECRET" in os.environ:
            del os.environ["EXECUTION_JWT_SECRET"]

