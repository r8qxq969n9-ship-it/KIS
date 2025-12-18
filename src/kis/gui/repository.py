"""Repository for Proposal and Approval data access"""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from kis.storage.models import Proposal, Approval, EventLog, ProposalStatus, ApprovalStatus


class ProposalRepository:
    """Repository for Proposal and Approval operations"""
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def get_proposals(self, status: Optional[str] = None) -> List[Proposal]:
        """
        Get proposals by status.
        
        Args:
            status: Proposal status filter (pending, approved, rejected, executed)
                   If None, defaults to 'pending'
        
        Returns:
            List of Proposal objects
        """
        if status is None:
            status = "pending"
        
        query = self.session.query(Proposal)
        
        if status:
            try:
                status_enum = ProposalStatus(status)
                query = query.filter(Proposal.status == status_enum)
            except ValueError:
                # Invalid status, return empty list
                return []
        
        return query.all()
    
    def get_proposal_by_id(self, proposal_id: int) -> Optional[Proposal]:
        """
        Get proposal by ID.
        
        Args:
            proposal_id: Proposal ID
        
        Returns:
            Proposal object or None if not found
        """
        return self.session.query(Proposal).filter_by(proposal_id=proposal_id).first()
    
    def approve_proposal(
        self,
        proposal_id: int,
        approved_by: str,
        token: str,
        token_jti: str,
        token_expires_at: datetime
    ) -> Approval:
        """
        Approve proposal and create approval record.
        
        Args:
            proposal_id: Proposal ID
            approved_by: Approver name
            token: Token string (원문, hash 계산용)
            token_jti: Token JTI
            token_expires_at: Token expiration time
        
        Returns:
            Created Approval object
        
        Raises:
            ValueError: If proposal is not in pending status
        """
        # Get proposal
        proposal = self.get_proposal_by_id(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError(f"Proposal {proposal_id} is not in pending status (current: {proposal.status})")
        
        # Calculate token hash
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        
        # Create approval record
        approval = Approval(
            proposal_id=proposal_id,
            status=ApprovalStatus.APPROVED,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc),
            token_hash=token_hash,
            token_jti=token_jti,
            token_expires_at=token_expires_at,
            token_used_at=None,
            rejection_reason=None
        )
        
        self.session.add(approval)
        
        # Update proposal status
        proposal.status = ProposalStatus.APPROVED
        
        self.session.commit()
        self.session.refresh(approval)
        
        return approval
    
    def reject_proposal(
        self,
        proposal_id: int,
        rejected_by: str,
        rejection_reason: str
    ) -> Approval:
        """
        Reject proposal and create approval record.
        
        Args:
            proposal_id: Proposal ID
            rejected_by: Rejector name
            rejection_reason: Rejection reason
        
        Returns:
            Created Approval object
        
        Raises:
            ValueError: If proposal is not in pending status
        """
        # Get proposal
        proposal = self.get_proposal_by_id(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError(f"Proposal {proposal_id} is not in pending status (current: {proposal.status})")
        
        # Create approval record (no token for rejected)
        approval = Approval(
            proposal_id=proposal_id,
            status=ApprovalStatus.REJECTED,
            approved_by=None,
            approved_at=None,
            token_hash=None,
            token_jti=None,
            token_expires_at=None,
            token_used_at=None,
            rejection_reason=rejection_reason
        )
        
        self.session.add(approval)
        
        # Update proposal status
        proposal.status = ProposalStatus.REJECTED
        
        self.session.commit()
        self.session.refresh(approval)
        
        return approval
    
    def log_approval_event(
        self,
        event_type: str,
        correlation_id: str,
        proposal_id: int,
        approval_id: int,
        approved_by: Optional[str] = None,
        rejected_by: Optional[str] = None,
        token_hash: Optional[str] = None
    ) -> None:
        """
        Log approval event to event_log.
        
        Args:
            event_type: Event type (approval_granted or approval_rejected)
            correlation_id: Correlation ID from proposal
            proposal_id: Proposal ID
            approval_id: Approval ID
            approved_by: Approver name (for approval_granted)
            rejected_by: Rejector name (for approval_rejected)
            token_hash: Token hash (for approval_granted)
        """
        payload = {
            "proposal_id": proposal_id,
            "approval_id": approval_id
        }
        
        if approved_by:
            payload["approved_by"] = approved_by
        if rejected_by:
            payload["rejected_by"] = rejected_by
        if token_hash:
            payload["token_hash"] = token_hash
        
        event = EventLog(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            correlation_id=correlation_id,
            actor="gui",
            payload_json=payload
        )
        
        self.session.add(event)
        self.session.commit()

