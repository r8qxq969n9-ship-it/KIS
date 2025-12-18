"""JWT authentication and token verification for Execution Server"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, DecodeError


class TokenVerificationError(Exception):
    """Base exception for token verification errors"""
    pass


class InvalidTokenSignatureError(TokenVerificationError):
    """Token signature is invalid"""
    pass


class TokenExpiredError(TokenVerificationError):
    """Token has expired"""
    pass


def verify_token(token: str, secret: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
        secret: JWT secret for verification
        
    Returns:
        Decoded token payload (claims)
        
    Raises:
        InvalidTokenSignatureError: If token signature is invalid
        TokenExpiredError: If token has expired
        TokenVerificationError: For other verification errors
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_exp": True}
        )
        return payload
    except ExpiredSignatureError as e:
        raise TokenExpiredError(f"Token has expired: {str(e)}") from e
    except DecodeError as e:
        raise InvalidTokenSignatureError(f"Token signature is invalid: {str(e)}") from e
    except InvalidTokenError as e:
        raise TokenVerificationError(f"Invalid token: {str(e)}") from e


def decode_token(token: str, secret: str) -> Dict[str, Any]:
    """
    Decode JWT token (alias for verify_token for clarity).
    
    Args:
        token: JWT token string
        secret: JWT secret for verification
        
    Returns:
        Decoded token payload (claims)
        
    Raises:
        TokenVerificationError: If token verification fails
    """
    return verify_token(token, secret)


def create_token(
    secret: str,
    jti: str,
    proposal_id: int,
    correlation_id: str,
    proposal_payload_hash: str,
    expires_in_seconds: int = 3600
) -> str:
    """
    Create JWT token.
    
    Args:
        secret: JWT secret for signing
        jti: Token JTI (JWT ID)
        proposal_id: Proposal ID
        correlation_id: Correlation ID
        proposal_payload_hash: Proposal payload hash
        expires_in_seconds: Token expiration time in seconds
        
    Returns:
        JWT token string
    """
    now = datetime.now(timezone.utc)
    exp = now.timestamp() + expires_in_seconds
    
    payload = {
        "jti": jti,
        "proposal_id": proposal_id,
        "correlation_id": correlation_id,
        "proposal_payload_hash": proposal_payload_hash,
        "iat": int(now.timestamp()),
        "exp": int(exp)
    }
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def calculate_token_hash(token: str) -> str:
    """
    Calculate SHA256 hash of token.
    
    Args:
        token: Token string
        
    Returns:
        SHA256 hash as hex string
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

