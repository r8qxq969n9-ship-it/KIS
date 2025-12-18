#!/bin/bash
# KIS Trading System - 로컬 개발 환경 실행 스크립트
# Phase 0: 모의투자 환경

set -e

echo "=========================================="
echo "KIS Trading System - 로컬 개발 환경 실행"
echo "=========================================="
echo ""

# 환경변수 확인
if [ -z "$PYTHONPATH" ]; then
    export PYTHONPATH=src
    echo "✓ PYTHONPATH 설정: $PYTHONPATH"
else
    echo "✓ PYTHONPATH 이미 설정됨: $PYTHONPATH"
fi

if [ -z "$EXECUTION_JWT_SECRET" ]; then
    echo "⚠ 경고: EXECUTION_JWT_SECRET 환경변수가 설정되지 않았습니다."
    echo "  Execution 서버 실행 전에 다음 명령어로 설정하세요:"
    echo "  export EXECUTION_JWT_SECRET='your-secret-key-here'"
    echo ""
fi

echo ""
echo "다음 서비스를 실행할 수 있습니다:"
echo ""
echo "1. 데이터베이스 초기화:"
echo "   PYTHONPATH=src python -m kis.storage.init_db"
echo ""
echo "2. Engine 모듈 실행 (snapshot + Proposal 생성):"
echo "   PYTHONPATH=src python -m kis.engine.run"
echo ""
echo "3. GUI 서버 시작 (포트 8001):"
echo "   PYTHONPATH=src uvicorn kis.gui.app:app --port 8001 --reload"
echo ""
echo "4. Execution 서버 시작 (포트 8002):"
echo "   export EXECUTION_JWT_SECRET='your-secret-key-here'"
echo "   PYTHONPATH=src uvicorn kis.execution.app:app --port 8002 --reload"
echo ""
echo "=========================================="
echo "각 서비스는 별도 터미널에서 실행하세요."
echo "=========================================="

