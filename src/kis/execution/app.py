"""FastAPI application for Execution Server"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from kis.storage.session import get_db_session
from kis.storage.models import ProposalStatus
from kis.execution.config import get_jwt_secret
from kis.execution.auth import (
    create_token,
    verify_token,
    calculate_token_hash,
    TokenVerificationError,
    InvalidTokenSignatureError,
    TokenExpiredError
)
from kis.execution.broker import BrokerClient, SpyBrokerClient
from kis.execution.repository import (
    get_kill_switch_status,
    get_approval_by_jti,
    mark_token_used,
    create_order,
    log_event,
    get_proposal_by_id
)
from kis.storage.models import KillSwitchStatus


app = FastAPI(title="KIS Trading System Execution Server", version="0.1.0")

# Broker client instance (can be replaced in tests)
broker_client: BrokerClient = SpyBrokerClient()


class IssueTokenRequest(BaseModel):
    """Request body for /issue_token"""
    proposal_id: int
    correlation_id: str
    proposal_payload_hash: str
    expires_in_seconds: int = 3600


class IssueTokenResponse(BaseModel):
    """Response for /issue_token"""
    token: str
    token_jti: str
    token_expires_at: str


class PlaceOrderRequest(BaseModel):
    """Request body for /place_order"""
    order_intent: Dict[str, Any]


class PlaceOrderResponse(BaseModel):
    """Response for /place_order"""
    order_id: int
    status: str


@app.post("/issue_token", response_model=IssueTokenResponse)
async def issue_token(
    request: IssueTokenRequest,
    db: Session = Depends(get_db_session)
):
    """
    Issue JWT token for approved proposal.
    
    This endpoint is called by GUI (P0-003) to request token issuance.
    In Phase 0, Execution Server also acts as Approval Service.
    
    Args:
        request: Token issuance request
        db: Database session
        
    Returns:
        Token response with token, token_jti, token_expires_at
        
    Raises:
        HTTPException: 404 if proposal not found, 400 if proposal not pending
    """
    # Get proposal
    proposal = get_proposal_by_id(db, request.proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {request.proposal_id} not found"
        )
    
    # Check proposal status (must be pending)
    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal {request.proposal_id} is not in pending status (current: {proposal.status})"
        )
    
    # Get JWT secret
    secret = get_jwt_secret()
    
    # Generate token JTI
    token_jti = str(uuid.uuid4())
    
    # Create token
    token = create_token(
        secret=secret,
        jti=token_jti,
        proposal_id=request.proposal_id,
        correlation_id=request.correlation_id,
        proposal_payload_hash=request.proposal_payload_hash,
        expires_in_seconds=request.expires_in_seconds
    )
    
    # Calculate expiration time
    expires_at = datetime.now(timezone.utc).timestamp() + request.expires_in_seconds
    token_expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
    
    return IssueTokenResponse(
        token=token,
        token_jti=token_jti,
        token_expires_at=token_expires_at
    )


def get_bearer_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db_session)
) -> str:
    """
    Extract Bearer token from Authorization header.
    
    Args:
        authorization: Authorization header value
        db: Database session (for event logging)
        
    Returns:
        Token string
        
    Raises:
        HTTPException: 401 if token is missing or invalid format
    """
    if not authorization:
        # Log event before raising exception
        log_event(
            db,
            "order_rejected",
            "unknown",
            {"reason": "Authorization header is required"}
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required"
        )
    
    if not authorization.startswith("Bearer "):
        log_event(
            db,
            "order_rejected",
            "unknown",
            {"reason": "Authorization header must start with 'Bearer '"}
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    if not token:
        log_event(
            db,
            "order_rejected",
            "unknown",
            {"reason": "Token is required"}
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is required"
        )
    
    return token


@app.post("/place_order", response_model=PlaceOrderResponse)
async def place_order(
    request: PlaceOrderRequest,
    token: str = Depends(get_bearer_token),
    db: Session = Depends(get_db_session)
):
    """
    Place order with broker (after approval token verification).
    
    Processing order (server-enforced):
    1. Kill switch check (if active -> 403 + broker calls == 0)
    2. JWT signature verification (if fails -> 401/403 + broker calls == 0)
    3. Token expiration check (if expired -> 403 + broker calls == 0)
    4. Approval record verification (token_hash, token_used_at, token_expires_at)
    5. On success: mark token used, log event, call broker, create order
    
    Args:
        request: Order request
        token: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Order response with order_id and status
        
    Raises:
        HTTPException: 403 if kill switch active, 401/403 if token invalid, 403 if token expired/used
    """
    # 1. Kill switch check (MUST be first - before any broker call)
    kill_switch_status = get_kill_switch_status(db)
    if kill_switch_status == KillSwitchStatus.ACTIVE:
        log_event(
            db,
            "order_blocked_killswitch",
            "unknown",  # correlation_id not available yet
            {
                "reason": "Kill switch is active",
                "kill_switch_status": kill_switch_status.value
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Order blocked: Kill switch is active"
        )
        # Broker call count remains 0 (never reached)
    
    # 2. JWT signature verification
    try:
        secret = get_jwt_secret()
        payload = verify_token(token, secret)
    except InvalidTokenSignatureError as e:
        # Try to decode token without verification to get correlation_id
        correlation_id = "unknown"
        try:
            import jwt as jwt_lib
            unverified = jwt_lib.decode(token, options={"verify_signature": False})
            correlation_id = unverified.get("correlation_id", "unknown")
        except Exception:
            pass
        
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Invalid token signature",
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token signature: {str(e)}"
        )
        # Broker call count remains 0
    except TokenExpiredError as e:
        correlation_id = "unknown"
        if payload:
            correlation_id = payload.get("correlation_id", "unknown")
        else:
            # Try to decode expired token to get correlation_id
            try:
                import jwt as jwt_lib
                unverified = jwt_lib.decode(token, options={"verify_signature": False, "verify_exp": False})
                correlation_id = unverified.get("correlation_id", "unknown")
            except Exception:
                pass
        
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Token expired",
                "error": str(e)
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token expired: {str(e)}"
        )
        # Broker call count remains 0
    except TokenVerificationError as e:
        correlation_id = "unknown"
        if payload:
            correlation_id = payload.get("correlation_id", "unknown")
        else:
            # Try to decode token to get correlation_id
            try:
                import jwt as jwt_lib
                unverified = jwt_lib.decode(token, options={"verify_signature": False})
                correlation_id = unverified.get("correlation_id", "unknown")
            except Exception:
                pass
        
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Token verification failed",
                "error": str(e)
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )
        # Broker call count remains 0
    
    # Extract claims
    token_jti = payload.get("jti")
    proposal_id = payload.get("proposal_id")
    correlation_id = payload.get("correlation_id", "unknown")
    proposal_payload_hash = payload.get("proposal_payload_hash")
    
    if not token_jti or not proposal_id:
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Missing required token claims",
                "token_jti": token_jti,
                "proposal_id": proposal_id
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims"
        )
        # Broker call count remains 0
    
    # 3. Get approval record
    approval = get_approval_by_jti(db, token_jti)
    if approval is None:
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Approval record not found",
                "token_jti": token_jti
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Approval record not found"
        )
        # Broker call count remains 0
    
    # 4. Verify token hash
    token_hash = calculate_token_hash(token)
    if approval.token_hash != token_hash:
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Token hash mismatch",
                "token_jti": token_jti
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token hash mismatch"
        )
        # Broker call count remains 0
    
    # 5. Check token expiration (from DB)
    now = datetime.now(timezone.utc)
    if approval.token_expires_at:
        # Ensure both are timezone-aware
        expires_at = approval.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            log_event(
                db,
                "order_rejected",
                correlation_id,
                {
                    "reason": "Token expired (from DB)",
                    "token_jti": token_jti
                }
            )
            db.commit()  # Commit event before raising exception
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token expired"
            )
            # Broker call count remains 0
    
    # 6. Check if token already used (1-time use)
    if approval.token_used_at is not None:
        log_event(
            db,
            "order_rejected",
            correlation_id,
            {
                "reason": "Token already used",
                "token_jti": token_jti,
                "token_used_at": approval.token_used_at.isoformat()
            }
        )
        db.commit()  # Commit event before raising exception
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token already used (one-time use only)"
        )
        # Broker call count remains 0
    
    # 7. All checks passed - proceed with order
    # Mark token as used (1-time use)
    mark_token_used(db, approval.approval_id)
    
    # Log order request
    log_event(
        db,
        "order_requested",
        correlation_id,
        {
            "proposal_id": proposal_id,
            "approval_id": approval.approval_id,
            "token_jti": token_jti
        }
    )
    
    # Call broker (this is where broker_client.place_order is called)
    broker_response = await broker_client.place_order(request.order_intent)
    
    # Create order record
    order = create_order(
        db,
        correlation_id=correlation_id,
        proposal_id=proposal_id,
        approval_id=approval.approval_id,
        order_data={
            **request.order_intent,
            "broker_response": broker_response
        }
    )
    
    return PlaceOrderResponse(
        order_id=order.order_id,
        status=order.status.value
    )

