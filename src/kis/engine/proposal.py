"""Proposal generation logic for Engine module"""

import uuid
from typing import Dict, Any, List


# Phase 0 고정 파라미터
MAX_POSITIONS = 20
MAX_WEIGHT_PER_POSITION = 0.08
KR_TARGET_WEIGHT = 0.4
US_TARGET_WEIGHT = 0.6

# 기본 선택 수량 (제약 만족을 위한 최소값)
MIN_KR_POSITIONS = 5
MIN_US_POSITIONS = 8


def create_proposal(universe_snapshot: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a proposal from universe snapshot data.
    
    Phase 0 알고리즘:
    - KR 5개, US 8개 선택 (총 13개)
    - KR: 40%를 5개로 동일가중 분배 (각 8%)
    - US: 60%를 8개로 동일가중 분배 (각 7.5%)
    - 제약: 최대 20종목, 종목당 최대 8%, KR/US 40/60
    
    Args:
        universe_snapshot: Snapshot data containing 'universe' list
        config: Optional configuration dict (for future use)
        
    Returns:
        Proposal payload dict with:
        - positions: List of {symbol, market, weight}
        - constraints_check: Dict with constraint validation results
        - correlation_id: UUID4 string
        
    Raises:
        ValueError: If universe has insufficient stocks (KR < 5 or US < 8)
    """
    if config is None:
        config = {}
    
    universe = universe_snapshot.get('universe', [])
    
    # 1. universe를 market별로 분리
    kr_stocks = [s for s in universe if s.get('market') == 'KR']
    us_stocks = [s for s in universe if s.get('market') == 'US']
    
    # 2. 에러 처리: 최소 수량 확인
    if len(kr_stocks) < MIN_KR_POSITIONS:
        raise ValueError(
            f"Insufficient KR stocks: {len(kr_stocks)} < {MIN_KR_POSITIONS}. "
            f"Need at least {MIN_KR_POSITIONS} KR stocks to satisfy 40% allocation with 8% cap."
        )
    if len(us_stocks) < MIN_US_POSITIONS:
        raise ValueError(
            f"Insufficient US stocks: {len(us_stocks)} < {MIN_US_POSITIONS}. "
            f"Need at least {MIN_US_POSITIONS} US stocks to satisfy 60% allocation with 8% cap."
        )
    
    # 3. 각 market별로 score 내림차순 정렬 (없으면 symbol 정렬)
    def sort_key(stock):
        score = stock.get('score')
        if score is not None:
            return (-score, stock.get('symbol', ''))
        return (0, stock.get('symbol', ''))
    
    kr_sorted = sorted(kr_stocks, key=sort_key)
    us_sorted = sorted(us_stocks, key=sort_key)
    
    # 4. 기본 선택: KR 5개, US 8개
    selected_kr = kr_sorted[:MIN_KR_POSITIONS]
    selected_us = us_sorted[:MIN_US_POSITIONS]
    
    # 5. 가중치 계산
    # KR: 40%를 5개로 동일가중 분배 → 각 8% (0.08)
    kr_weight_per_stock = KR_TARGET_WEIGHT / MIN_KR_POSITIONS
    
    # US: 60%를 8개로 동일가중 분배 → 각 7.5% (0.075)
    us_weight_per_stock = US_TARGET_WEIGHT / MIN_US_POSITIONS
    
    # 6. positions 생성
    positions = []
    
    for stock in selected_kr:
        positions.append({
            'symbol': stock['symbol'],
            'market': 'KR',
            'weight': kr_weight_per_stock
        })
    
    for stock in selected_us:
        positions.append({
            'symbol': stock['symbol'],
            'market': 'US',
            'weight': us_weight_per_stock
        })
    
    # 7. 제약 검증
    total_positions = len(positions)
    total_weight = sum(p['weight'] for p in positions)
    kr_weight_sum = sum(p['weight'] for p in positions if p['market'] == 'KR')
    us_weight_sum = sum(p['weight'] for p in positions if p['market'] == 'US')
    max_weight = max(p['weight'] for p in positions)
    
    constraints_passed = (
        total_positions <= MAX_POSITIONS and
        max_weight <= MAX_WEIGHT_PER_POSITION and
        abs(kr_weight_sum - KR_TARGET_WEIGHT) < 1e-9 and
        abs(us_weight_sum - US_TARGET_WEIGHT) < 1e-9 and
        abs(total_weight - 1.0) < 1e-9
    )
    
    constraints_check = {
        'max_positions': MAX_POSITIONS,
        'max_weight': MAX_WEIGHT_PER_POSITION,
        'kr_weight': KR_TARGET_WEIGHT,
        'us_weight': US_TARGET_WEIGHT,
        'passed': constraints_passed,
        'actual_positions': total_positions,
        'actual_max_weight': max_weight,
        'actual_kr_weight': kr_weight_sum,
        'actual_us_weight': us_weight_sum,
        'actual_total_weight': total_weight
    }
    
    # 8. correlation_id 생성
    correlation_id = str(uuid.uuid4())
    
    return {
        'positions': positions,
        'constraints_check': constraints_check,
        'correlation_id': correlation_id
    }

