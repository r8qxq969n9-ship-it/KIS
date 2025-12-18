"""Repository for Execution Server database operations"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from kis.storage.models import (
    SystemState,
    Approval,
    Order,
    EventLog,
    Proposal,
    KillSwitchStatus,
    OrderStatus
)


def get_kill_switch_status(session: Session) -> KillSwitchStatus:
    """
    Get latest kill switch status from system_state.
    
    Args:
        session: Database session
        
    Returns:
        Kill switch status (default: ACTIVE if no record exists)
    """
    latest_state = session.query(SystemState).order_by(
        SystemState.timestamp.desc()
    ).first()
    
    if latest_state:
        return latest_state.kill_switch_status
    else:
        # Conservative default: ACTIVE if no record exists
        return KillSwitchStatus.ACTIVE


def get_approval_by_jti(session: Session, token_jti: str) -> Optional[Approval]:
    """
    Get approval record by token JTI.
    
    Args:
        session: Database session
        token_jti: Token JTI (JWT ID)
        
    Returns:
        Approval object or None if not found
    """
    return session.query(Approval).filter_by(token_jti=token_jti).first()


def mark_token_used(session: Session, approval_id: int) -> None:
    """
    Mark token as used by setting token_used_at.
    
    Args:
        session: Database session
        approval_id: Approval ID
    """
    approval = session.query(Approval).filter_by(approval_id=approval_id).first()
    if approval:
        approval.token_used_at = datetime.now(timezone.utc)
        session.commit()


def create_order(
    session: Session,
    correlation_id: str,
    proposal_id: int,
    approval_id: int,
    order_data: dict
) -> Order:
    """
    Create order record in database.
    
    Args:
        session: Database session
        correlation_id: Correlation ID
        proposal_id: Proposal ID
        approval_id: Approval ID
        order_data: Order data dictionary
        
    Returns:
        Created Order object
    """
    order = Order(
        correlation_id=correlation_id,
        status=OrderStatus.PENDING,
        payload_json={
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            **order_data
        }
    )
    
    session.add(order)
    session.commit()
    session.refresh(order)
    
    return order


def log_event(
    session: Session,
    event_type: str,
    correlation_id: str,
    payload: dict
) -> None:
    """
    Log event to event_log.
    
    Args:
        session: Database session
        event_type: Event type
        correlation_id: Correlation ID
        payload: Event payload dictionary
    """
    event = EventLog(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        correlation_id=correlation_id,
        actor="execution_server",
        payload_json=payload
    )
    
    session.add(event)
    session.flush()  # Flush to ensure event is in session
    # Note: commit will be done by caller or separately to ensure persistence


def get_proposal_by_id(session: Session, proposal_id: int) -> Optional[Proposal]:
    """
    Get proposal by ID.
    
    Args:
        session: Database session
        proposal_id: Proposal ID
        
    Returns:
        Proposal object or None if not found
    """
    return session.query(Proposal).filter_by(proposal_id=proposal_id).first()

