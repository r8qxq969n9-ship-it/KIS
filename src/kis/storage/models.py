"""SQLAlchemy models for KIS Trading System storage"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class ProposalStatus(str, enum.Enum):
    """Proposal status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ApprovalStatus(str, enum.Enum):
    """Approval status enumeration"""
    APPROVED = "approved"
    REJECTED = "rejected"


class OrderStatus(str, enum.Enum):
    """Order status enumeration"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class KillSwitchStatus(str, enum.Enum):
    """Kill switch status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class EventLog(Base):
    """Append-only event log table"""
    __tablename__ = "event_log"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    event_type = Column(String(100), nullable=False)
    correlation_id = Column(String(100), nullable=False, index=True)
    actor = Column(String(50), nullable=False)
    payload_json = Column(JSON, nullable=False)
    prev_hash = Column(String(64), nullable=True)
    hash = Column(String(64), nullable=True)


class Snapshot(Base):
    """Market data snapshot table"""
    __tablename__ = "snapshots"

    snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    asof = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(100), nullable=False)
    payload_json = Column(JSON, nullable=False)


class Proposal(Base):
    """Proposal table"""
    __tablename__ = "proposals"

    proposal_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    universe_snapshot_id = Column(Integer, ForeignKey("snapshots.snapshot_id"), nullable=True)
    config_hash = Column(String(64), nullable=False)
    git_commit_sha = Column(String(40), nullable=True)
    schema_version = Column(String(20), nullable=False)
    payload_json = Column(JSON, nullable=False)
    status = Column(SQLEnum(ProposalStatus), nullable=False, default=ProposalStatus.PENDING)

    # Relationships
    snapshot = relationship("Snapshot", foreign_keys=[universe_snapshot_id])


class Approval(Base):
    """Approval table - token_hash only, no raw token storage"""
    __tablename__ = "approvals"

    approval_id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("proposals.proposal_id"), nullable=False)
    token_hash = Column(String(64), nullable=False, index=True)  # Hash only, no raw token
    token_expires_at = Column(DateTime(timezone=True), nullable=False)
    token_used_at = Column(DateTime(timezone=True), nullable=True)
    token_jti = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(SQLEnum(ApprovalStatus), nullable=False)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    proposal = relationship("Proposal", foreign_keys=[proposal_id])


class Order(Base):
    """Order table"""
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    broker_order_id = Column(String(100), nullable=True)
    payload_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Fill(Base):
    """Fill (execution) table"""
    __tablename__ = "fills"

    fill_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    correlation_id = Column(String(100), nullable=False, index=True)
    broker_fill_id = Column(String(100), nullable=False)
    payload_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    order = relationship("Order", foreign_keys=[order_id])


class SystemState(Base):
    """System state table - includes kill switch status"""
    __tablename__ = "system_state"

    state_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    kill_switch_status = Column(SQLEnum(KillSwitchStatus), nullable=False, default=KillSwitchStatus.ACTIVE)
    kill_switch_reason = Column(Text, nullable=True)
    portfolio_value = Column(String(50), nullable=True)
    current_mdd = Column(String(50), nullable=True)
    active_positions = Column(Integer, nullable=True, default=0)


class SchemaVersion(Base):
    """Schema version tracking table"""
    __tablename__ = "schema_version"

    schema_version = Column(String(20), primary_key=True)
    applied_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    description = Column(Text, nullable=True)

