"""Sample data loader for Engine module"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def load_sample_snapshot(file_path: str) -> Dict[str, Any]:
    """
    Load sample snapshot data from JSON file.
    
    Args:
        file_path: Path to the sample snapshot JSON file
        
    Returns:
        Dictionary containing snapshot data with parsed asof datetime
        
    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the JSON is invalid or missing required fields
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Sample snapshot file not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate required fields
    if 'asof' not in data:
        raise ValueError("Missing required field: 'asof'")
    if 'source' not in data:
        raise ValueError("Missing required field: 'source'")
    if 'universe' not in data:
        raise ValueError("Missing required field: 'universe'")
    
    # Parse asof to UTC datetime
    # ISO 8601 format: "2025-12-18T00:00:00Z"
    try:
        asof_str = data['asof']
        if asof_str.endswith('Z'):
            asof_str = asof_str[:-1] + '+00:00'
        data['asof'] = datetime.fromisoformat(asof_str)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid asof format: {data['asof']}") from e
    
    return data

