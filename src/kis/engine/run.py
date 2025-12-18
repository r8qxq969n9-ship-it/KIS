"""CLI entry point for Engine module - snapshot creation and proposal generation"""

import json
import os
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from kis.storage.init_db import init_database, DATABASE_URL
from kis.storage.models import Snapshot, Proposal, EventLog, SchemaVersion, ProposalStatus
from kis.engine.sample_data import load_sample_snapshot
from kis.engine.proposal import create_proposal


# Phase 0 고정 파라미터 (config_hash 계산용)
PHASE0_CONFIG = {
    "max_positions": 20,
    "max_weight_per_position": 0.08,
    "kr_target_weight": 0.4,
    "us_target_weight": 0.6,
    "phase": 0
}


def get_git_commit_sha() -> str:
    """
    Get current git commit SHA.
    
    Returns:
        Git commit SHA string, or "unknown" if git command fails
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def get_config_hash(config: Dict[str, Any]) -> str:
    """
    Calculate SHA256 hash of sorted JSON config.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        SHA256 hash as hex string (64 characters)
    """
    # Sort keys for deterministic hash
    sorted_config = json.dumps(config, sort_keys=True)
    return hashlib.sha256(sorted_config.encode('utf-8')).hexdigest()


def get_schema_version(session) -> str:
    """
    Get latest schema version from database.
    
    Args:
        session: SQLAlchemy session
        
    Returns:
        Schema version string (e.g., "0.1.0")
    """
    schema_version = session.query(SchemaVersion).order_by(
        SchemaVersion.applied_at.desc()
    ).first()
    
    if schema_version:
        return schema_version.schema_version
    else:
        # Fallback to default if no version found
        return "0.1.0"


def save_snapshot(session, snapshot_data: Dict[str, Any]) -> int:
    """
    Save snapshot to database.
    
    Args:
        session: SQLAlchemy session
        snapshot_data: Snapshot data dict with 'asof', 'source', 'universe'
        
    Returns:
        snapshot_id
    """
    # Ensure asof is timezone-aware UTC
    asof = snapshot_data['asof']
    if isinstance(asof, str):
        if asof.endswith('Z'):
            asof = asof[:-1] + '+00:00'
        asof = datetime.fromisoformat(asof)
    if asof.tzinfo is None:
        asof = asof.replace(tzinfo=timezone.utc)
    elif asof.tzinfo != timezone.utc:
        asof = asof.astimezone(timezone.utc)
    
    # Store original JSON as payload
    # Convert datetime back to ISO string for JSON serialization
    payload_data = snapshot_data.copy()
    if isinstance(payload_data['asof'], datetime):
        payload_data['asof'] = payload_data['asof'].isoformat()
    
    snapshot = Snapshot(
        asof=asof,
        source=snapshot_data['source'],
        payload_json=payload_data
    )
    
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    
    return snapshot.snapshot_id


def save_proposal(
    session,
    proposal_data: Dict[str, Any],
    snapshot_id: int,
    config: Dict[str, Any]
) -> int:
    """
    Save proposal to database.
    
    Args:
        session: SQLAlchemy session
        proposal_data: Proposal data dict with 'positions', 'constraints_check', 'correlation_id'
        snapshot_id: Related snapshot ID
        config: Configuration dict for config_hash calculation
        
    Returns:
        proposal_id
    """
    config_hash = get_config_hash(config)
    git_commit_sha = get_git_commit_sha()
    schema_version = get_schema_version(session)
    
    proposal = Proposal(
        universe_snapshot_id=snapshot_id,
        config_hash=config_hash,
        git_commit_sha=git_commit_sha,
        schema_version=schema_version,
        payload_json=proposal_data,
        status=ProposalStatus.PENDING
    )
    
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    
    return proposal.proposal_id


def log_proposal_created(
    session,
    proposal_id: int,
    snapshot_id: int,
    correlation_id: str,
    constraints_passed: bool
) -> None:
    """
    Log proposal_created event to event_log.
    
    Args:
        session: SQLAlchemy session
        proposal_id: Created proposal ID
        snapshot_id: Related snapshot ID
        correlation_id: Correlation ID from proposal
        constraints_passed: Whether constraints check passed
    """
    event = EventLog(
        timestamp=datetime.now(timezone.utc),
        event_type="proposal_created",
        correlation_id=correlation_id,
        actor="engine",
        payload_json={
            "proposal_id": proposal_id,
            "snapshot_id": snapshot_id,
            "constraints_passed": constraints_passed
        }
    )
    
    session.add(event)
    session.commit()


def main():
    """Main CLI entry point"""
    try:
        # 1. 샘플 데이터 로드
        sample_file = Path(__file__).parent.parent.parent.parent / "data" / "sample_snapshot.json"
        if not sample_file.exists():
            print(f"Error: Sample snapshot file not found: {sample_file}")
            return 1
        
        print(f"Loading sample snapshot from: {sample_file}")
        snapshot_data = load_sample_snapshot(str(sample_file))
        print(f"Loaded snapshot with {len(snapshot_data['universe'])} stocks")
        
        # 2. DB 초기화
        database_url = os.getenv("DATABASE_URL", DATABASE_URL)
        print(f"Initializing database: {database_url}")
        init_database(database_url)
        
        # 3. DB 세션 생성
        engine = create_engine(database_url, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # 4. Snapshot 저장
            print("Saving snapshot to database...")
            snapshot_id = save_snapshot(session, snapshot_data)
            print(f"Snapshot saved with ID: {snapshot_id}")
            
            # 5. Proposal 생성
            print("Creating proposal...")
            proposal_data = create_proposal(snapshot_data, PHASE0_CONFIG)
            print(f"Proposal created with {len(proposal_data['positions'])} positions")
            print(f"  KR positions: {sum(1 for p in proposal_data['positions'] if p['market'] == 'KR')}")
            print(f"  US positions: {sum(1 for p in proposal_data['positions'] if p['market'] == 'US')}")
            print(f"  Constraints passed: {proposal_data['constraints_check']['passed']}")
            
            # 6. Proposal 저장
            print("Saving proposal to database...")
            proposal_id = save_proposal(session, proposal_data, snapshot_id, PHASE0_CONFIG)
            print(f"Proposal saved with ID: {proposal_id}")
            
            # 7. Event log 기록
            print("Logging proposal_created event...")
            log_proposal_created(
                session,
                proposal_id,
                snapshot_id,
                proposal_data['correlation_id'],
                proposal_data['constraints_check']['passed']
            )
            print("Event logged successfully")
            
            # 8. 결과 출력
            print("\n" + "="*50)
            print("Proposal generation completed successfully!")
            print("="*50)
            print(f"Proposal ID: {proposal_id}")
            print(f"Correlation ID: {proposal_data['correlation_id']}")
            print(f"Snapshot ID: {snapshot_id}")
            print("="*50)
            
            return 0
            
        except ValueError as e:
            print(f"\nError: {e}")
            return 1
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            session.close()
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

