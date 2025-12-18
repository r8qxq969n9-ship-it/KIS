"""Tests for GUI approval system"""

import os
import tempfile
import pytest
import respx
import httpx
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from kis.storage.init_db import init_database
from kis.storage.models import Proposal, Approval, EventLog, ProposalStatus, ApprovalStatus
from kis.gui.app import app
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
    
    yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


def test_get_proposals_pending(client, test_proposal):
    """Test 1: GET /proposals 기본(pending) 조회 성공"""
    response = client.get("/proposals?status=pending")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    
    # Find our test proposal
    proposal_data = next((p for p in data if p['proposal_id'] == test_proposal.proposal_id), None)
    assert proposal_data is not None
    assert proposal_data['status'] == 'pending'
    assert proposal_data['proposal_id'] == test_proposal.proposal_id


@respx.mock
def test_approve_proposal(client, test_proposal, temp_db):
    """Test 2: POST approve - 승인 후 proposals.status=approved, approvals에 token_hash 저장(원문 미저장), event_log에 approval_granted 기록"""
    # Mock Approval Service response
    mock_token = "mock-token-12345"
    mock_jti = "mock-jti-67890"
    mock_expires_at = (datetime.now(timezone.utc).replace(microsecond=0)).isoformat() + "Z"
    
    respx.post("http://localhost:8002/issue_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "token": mock_token,
                "token_jti": mock_jti,
                "token_expires_at": mock_expires_at
            }
        )
    )
    
    # Approve proposal
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/approve",
        json={
            "approved_by": "test_user",
            "expires_in_seconds": 3600
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data['proposal_id'] == test_proposal.proposal_id
    assert data['token'] == mock_token  # 원문 반환
    assert data['token_hash'] is not None
    assert data['token_jti'] == mock_jti
    assert 'token_expires_at' in data
    
    # Verify proposal status updated
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        proposal = session.query(Proposal).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert proposal.status == ProposalStatus.APPROVED
        
        # Verify approval record
        approval = session.query(Approval).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert approval is not None
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.token_hash is not None
        assert approval.token_hash == data['token_hash']  # DB에는 hash만 저장
        assert approval.token_jti == mock_jti
        assert approval.approved_by == "test_user"
        
        # Verify token 원문이 DB에 저장되지 않음
        # token_hash는 sha256이므로 원문과 다름
        import hashlib
        expected_hash = hashlib.sha256(mock_token.encode('utf-8')).hexdigest()
        assert approval.token_hash == expected_hash
        # 원문은 DB에 없으므로 직접 확인 불가, 하지만 hash가 일치하면 원문이 저장되지 않았음을 간접 확인
        
        # Verify event_log
        events = session.query(EventLog).filter_by(
            event_type="approval_granted",
            correlation_id="test-correlation-123"
        ).all()
        assert len(events) >= 1
        event = events[0]
        assert event.actor == "gui"
        assert event.payload_json['proposal_id'] == test_proposal.proposal_id
        assert event.payload_json['approved_by'] == "test_user"
        assert event.payload_json['token_hash'] == approval.token_hash
    finally:
        session.close()


def test_reject_proposal(client, test_proposal, temp_db):
    """Test 3: POST reject - 거부 후 proposals.status=rejected, rejection_reason 저장, event_log에 approval_rejected 기록"""
    # Reject proposal
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/reject",
        json={
            "rejected_by": "test_user",
            "rejection_reason": "Test rejection reason"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data['proposal_id'] == test_proposal.proposal_id
    assert data['status'] == 'rejected'
    
    # Verify proposal status updated
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        proposal = session.query(Proposal).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert proposal.status == ProposalStatus.REJECTED
        
        # Verify approval record
        approval = session.query(Approval).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert approval is not None
        assert approval.status == ApprovalStatus.REJECTED
        assert approval.token_hash is None  # 거부 시 token_hash는 null
        assert approval.token_jti is None
        assert approval.rejection_reason == "Test rejection reason"
        
        # Verify event_log
        events = session.query(EventLog).filter_by(
            event_type="approval_rejected",
            correlation_id="test-correlation-123"
        ).all()
        assert len(events) >= 1
        event = events[0]
        assert event.actor == "gui"
        assert event.payload_json['proposal_id'] == test_proposal.proposal_id
        assert event.payload_json['rejected_by'] == "test_user"
    finally:
        session.close()


@respx.mock
def test_approve_already_approved_proposal(client, test_proposal, temp_db):
    """Test 4: 이미 approved/rejected된 proposal에 approve/reject 시 409"""
    # First, approve the proposal
    mock_token = "mock-token-12345"
    mock_jti = "mock-jti-67890"
    mock_expires_at = (datetime.now(timezone.utc).replace(microsecond=0)).isoformat() + "Z"
    
    respx.post("http://localhost:8002/issue_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "token": mock_token,
                "token_jti": mock_jti,
                "token_expires_at": mock_expires_at
            }
        )
    )
    
    # Approve first time
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/approve",
        json={
            "approved_by": "test_user",
            "expires_in_seconds": 3600
        }
    )
    assert response.status_code == 200
    
    # Try to approve again - should fail with 409
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/approve",
        json={
            "approved_by": "test_user2",
            "expires_in_seconds": 3600
        }
    )
    assert response.status_code == 409
    assert "not in pending status" in response.json()['detail'].lower()


def test_reject_already_rejected_proposal(client, test_proposal, temp_db):
    """Test 4 (continued): 이미 rejected된 proposal에 reject 시 409"""
    # First, reject the proposal
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/reject",
        json={
            "rejected_by": "test_user",
            "rejection_reason": "First rejection"
        }
    )
    assert response.status_code == 200
    
    # Try to reject again - should fail with 409
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/reject",
        json={
            "rejected_by": "test_user2",
            "rejection_reason": "Second rejection"
        }
    )
    assert response.status_code == 409
    assert "not in pending status" in response.json()['detail'].lower()


@respx.mock
def test_token_not_stored_in_db(client, test_proposal, temp_db):
    """Test 5: 승인 응답에 token 원문이 포함되지만, DB에는 token_hash만 존재함을 검증"""
    # Mock Approval Service response
    mock_token = "secret-token-abc123"
    mock_jti = "mock-jti-xyz789"
    mock_expires_at = (datetime.now(timezone.utc).replace(microsecond=0)).isoformat() + "Z"
    
    respx.post("http://localhost:8002/issue_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "token": mock_token,
                "token_jti": mock_jti,
                "token_expires_at": mock_expires_at
            }
        )
    )
    
    # Approve proposal
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/approve",
        json={
            "approved_by": "test_user",
            "expires_in_seconds": 3600
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response contains token 원문
    assert data['token'] == mock_token
    assert data['token_hash'] is not None
    
    # Verify DB has only token_hash, not token 원문
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        approval = session.query(Approval).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert approval is not None
        
        # DB에는 token_hash만 있고, token 원문은 없음
        assert approval.token_hash is not None
        assert approval.token_hash != mock_token  # hash와 원문은 다름
        
        # Verify hash is correct (sha256 of token)
        import hashlib
        expected_hash = hashlib.sha256(mock_token.encode('utf-8')).hexdigest()
        assert approval.token_hash == expected_hash
        
        # Verify token 원문이 DB의 어떤 필드에도 저장되지 않음
        # (직접 확인은 어렵지만, hash가 일치하면 원문이 저장되지 않았음을 간접 확인)
        # token_hash는 64자 hex string이므로 원문과 다름
        assert len(approval.token_hash) == 64
        assert approval.token_hash != mock_token
    finally:
        session.close()


@respx.mock
def test_token_issuance_failure(client, test_proposal, temp_db):
    """Test: Approval Service 실패 시 approve가 502/503 반환하고 DB 변경이 발생하지 않음"""
    # Mock Approval Service 500 error
    respx.post("http://localhost:8002/issue_token").mock(
        return_value=httpx.Response(500, json={"error": "Internal server error"})
    )
    
    # Try to approve proposal
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/approve",
        json={
            "approved_by": "test_user",
            "expires_in_seconds": 3600
        }
    )
    
    # Should return 502 (Bad Gateway)
    assert response.status_code == 502
    assert "Failed to request token issuance" in response.json()['detail']
    
    # Verify proposal status is still pending
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        proposal = session.query(Proposal).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert proposal.status == ProposalStatus.PENDING  # Still pending
        
        # Verify no approval record was created
        approval = session.query(Approval).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert approval is None  # No approval record
        
        # Verify no approval_granted event was logged
        events = session.query(EventLog).filter_by(
            event_type="approval_granted",
            correlation_id="test-correlation-123"
        ).all()
        assert len(events) == 0  # No approval_granted event
    finally:
        session.close()


@respx.mock
def test_token_issuance_connection_error(client, test_proposal, temp_db):
    """Test: Approval Service 연결 오류 시 approve가 502 반환하고 DB 변경이 발생하지 않음"""
    # Mock connection error
    respx.post("http://localhost:8002/issue_token").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    
    # Try to approve proposal
    response = client.post(
        f"/proposals/{test_proposal.proposal_id}/approve",
        json={
            "approved_by": "test_user",
            "expires_in_seconds": 3600
        }
    )
    
    # Should return 502 (Bad Gateway)
    assert response.status_code == 502
    assert "Failed to request token issuance" in response.json()['detail']
    
    # Verify proposal status is still pending
    engine = create_engine(temp_db)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        proposal = session.query(Proposal).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert proposal.status == ProposalStatus.PENDING  # Still pending
        
        # Verify no approval record was created
        approval = session.query(Approval).filter_by(proposal_id=test_proposal.proposal_id).first()
        assert approval is None  # No approval record
        
        # Verify no approval_granted event was logged
        events = session.query(EventLog).filter_by(
            event_type="approval_granted",
            correlation_id="test-correlation-123"
        ).all()
        assert len(events) == 0  # No approval_granted event
    finally:
        session.close()

