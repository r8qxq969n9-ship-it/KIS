"""Configuration for Execution Server"""

import os


def get_jwt_secret() -> str:
    """
    Get JWT secret from environment variable.
    
    Returns:
        JWT secret string
        
    Raises:
        ValueError: If EXECUTION_JWT_SECRET is not set
    """
    secret = os.getenv("EXECUTION_JWT_SECRET")
    if not secret:
        raise ValueError(
            "EXECUTION_JWT_SECRET environment variable is required. "
            "This secret is only known to Execution Server."
        )
    return secret

