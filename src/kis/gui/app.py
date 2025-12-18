"""FastAPI application for GUI approval system"""

from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from kis.storage.session import get_db_session
from kis.storage.models import ProposalStatus
from kis.gui.schemas import (
    ProposalResponse,
    ApproveRequest,
    ApproveResponse,
    RejectRequest,
    RejectResponse
)
from kis.gui.repository import ProposalRepository
from kis.gui.token_client import TokenClient


app = FastAPI(title="KIS Trading System GUI", version="0.1.0")


@app.get("/proposals", response_model=List[ProposalResponse])
async def get_proposals(
    status: Optional[str] = "pending",
    db: Session = Depends(get_db_session)
):
    """
    Get proposals by status.
    
    Args:
        status: Proposal status filter (pending, approved, rejected, executed)
               Default: pending
        db: Database session
    
    Returns:
        List of proposals
    """
    repo = ProposalRepository(db)
    proposals = repo.get_proposals(status)
    return proposals


@app.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db_session)
):
    """
    Get proposal by ID.
    
    Args:
        proposal_id: Proposal ID
        db: Database session
    
    Returns:
        Proposal object
    
    Raises:
        HTTPException: 404 if proposal not found
    """
    repo = ProposalRepository(db)
    proposal = repo.get_proposal_by_id(proposal_id)
    
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found"
        )
    
    return proposal


@app.post("/proposals/{proposal_id}/approve", response_model=ApproveResponse)
async def approve_proposal(
    proposal_id: int,
    request: ApproveRequest,
    db: Session = Depends(get_db_session)
):
    """
    Approve proposal and request token issuance.
    
    Args:
        proposal_id: Proposal ID
        request: Approve request body
        db: Database session
    
    Returns:
        Approval response with token (원문, DB에는 저장 안 함)
    
    Raises:
        HTTPException: 404 if proposal not found, 409 if not pending
    """
    repo = ProposalRepository(db)
    
    # Get proposal
    proposal = repo.get_proposal_by_id(proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found"
        )
    
    # Check if proposal is pending
    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal {proposal_id} is not in pending status (current: {proposal.status})"
        )
    
    # Request token issuance from Approval Service
    token_client = TokenClient()
    try:
        correlation_id = proposal.payload_json.get('correlation_id', '')
        token_result = await token_client.issue_token(
            proposal_id=proposal_id,
            correlation_id=correlation_id,
            proposal_payload_json=proposal.payload_json,
            expires_in_seconds=request.expires_in_seconds
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to request token issuance: {str(e)}"
        )
    finally:
        await token_client.close()
    
    # Parse token_expires_at
    token_expires_at_str = token_result['token_expires_at']
    if isinstance(token_expires_at_str, str):
        # Parse ISO8601 string
        # Handle 'Z' suffix (UTC)
        if token_expires_at_str.endswith('Z'):
            # Remove Z, and if there's already a timezone offset, remove it first
            base_str = token_expires_at_str[:-1]
            # Check if it already has timezone offset (+XX:XX or -XX:XX)
            if '+' in base_str:
                # Remove existing timezone offset
                base_str = base_str.rsplit('+', 1)[0]
            elif base_str.count('-') > 2:
                # Has timezone offset with -, find last - before timezone
                parts = base_str.rsplit('-', 1)
                if len(parts) == 2 and ':' in parts[1]:
                    base_str = parts[0]
            token_expires_at_str = base_str + '+00:00'
        # If already has timezone offset, use as is
        elif '+' in token_expires_at_str or (token_expires_at_str.count('-') > 2 and 'T' in token_expires_at_str):
            # Already has timezone, use as is
            pass
        else:
            # No timezone info, assume UTC
            token_expires_at_str = token_expires_at_str + '+00:00'
        token_expires_at = datetime.fromisoformat(token_expires_at_str)
    else:
        token_expires_at = token_expires_at_str
    
    # Approve proposal (stores token_hash only, not token 원문)
    approval = repo.approve_proposal(
        proposal_id=proposal_id,
        approved_by=request.approved_by,
        token=token_result['token'],
        token_jti=token_result['token_jti'],
        token_expires_at=token_expires_at
    )
    
    # Log approval event
    repo.log_approval_event(
        event_type="approval_granted",
        correlation_id=correlation_id,
        proposal_id=proposal_id,
        approval_id=approval.approval_id,
        approved_by=request.approved_by,
        token_hash=approval.token_hash
    )
    
    # Return response with token 원문 (not stored in DB)
    return ApproveResponse(
        approval_id=approval.approval_id,
        proposal_id=proposal_id,
        token=token_result['token'],  # 원문 반환 (DB에는 저장 안 함)
        token_hash=approval.token_hash,
        token_jti=approval.token_jti,
        token_expires_at=token_expires_at
    )


@app.post("/proposals/{proposal_id}/reject", response_model=RejectResponse)
async def reject_proposal(
    proposal_id: int,
    request: RejectRequest,
    db: Session = Depends(get_db_session)
):
    """
    Reject proposal.
    
    Args:
        proposal_id: Proposal ID
        request: Reject request body
        db: Database session
    
    Returns:
        Rejection response
    
    Raises:
        HTTPException: 404 if proposal not found, 409 if not pending
    """
    repo = ProposalRepository(db)
    
    # Get proposal
    proposal = repo.get_proposal_by_id(proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found"
        )
    
    # Check if proposal is pending
    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal {proposal_id} is not in pending status (current: {proposal.status})"
        )
    
    # Reject proposal
    approval = repo.reject_proposal(
        proposal_id=proposal_id,
        rejected_by=request.rejected_by,
        rejection_reason=request.rejection_reason
    )
    
    # Log rejection event
    correlation_id = proposal.payload_json.get('correlation_id', '')
    repo.log_approval_event(
        event_type="approval_rejected",
        correlation_id=correlation_id,
        proposal_id=proposal_id,
        approval_id=approval.approval_id,
        rejected_by=request.rejected_by
    )
    
    return RejectResponse(
        approval_id=approval.approval_id,
        proposal_id=proposal_id,
        status=approval.status.value
    )

