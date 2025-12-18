"""Pydantic schemas for GUI API"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProposalResponse(BaseModel):
    """Proposal 조회 응답"""
    proposal_id: int
    created_at: datetime
    universe_snapshot_id: Optional[int]
    config_hash: str
    git_commit_sha: Optional[str]
    schema_version: str
    payload_json: Dict[str, Any]
    status: str

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    """승인 요청 body"""
    approved_by: str = Field(..., description="승인자 이름")
    expires_in_seconds: Optional[int] = Field(3600, description="토큰 만료 시간(초), 기본 3600")


class ApproveResponse(BaseModel):
    """승인 응답 (token 원문 포함, DB에는 저장 안 함)"""
    approval_id: int
    proposal_id: int
    token: str = Field(..., description="토큰 원문 (DB에는 저장되지 않음)")
    token_hash: str = Field(..., description="토큰 해시 (DB에 저장됨)")
    token_jti: str
    token_expires_at: datetime


class RejectRequest(BaseModel):
    """거부 요청 body"""
    rejected_by: str = Field(..., description="거부자 이름")
    rejection_reason: str = Field(..., description="거부 사유")


class RejectResponse(BaseModel):
    """거부 응답"""
    approval_id: int
    proposal_id: int
    status: str

