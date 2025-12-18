# KIS Trading System - Phase 0

Phase 0은 모의투자 환경에서 3단 아키텍처(Engine-GUI-Execution)의 기본 구조를 구축하고, 승인 기반 주문 실행 시스템의 핵심 메커니즘을 검증하는 단계입니다.

## 프로젝트 구조

```
KIS_trading/
├── src/
│   └── kis/
│       ├── __init__.py
│       └── storage/
│           ├── __init__.py
│           ├── models.py      # SQLAlchemy 모델 정의
│           └── init_db.py     # 데이터베이스 초기화 스크립트
├── tests/
│   ├── __init__.py
│   └── test_storage_init.py  # 데이터베이스 초기화 테스트
├── docs/
│   └── PHASE0_SPEC.md        # Phase 0 사양서
├── BACKLOG.md                # 백로그
├── requirements.txt          # Python 의존성
└── README.md                 # 이 파일
```

## 설치

### 1. Python 환경 설정

Python 3.8 이상이 필요합니다.

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

## 데이터베이스 초기화

### 기본 사용법 (SQLite)

```bash
python -m kis.storage.init_db
```

또는 Python 코드에서:

```python
from kis.storage.init_db import init_database

# SQLite 기본 사용
init_database()

# 또는 특정 데이터베이스 URL 지정
init_database("sqlite:///path/to/database.db")
```

### 환경변수로 데이터베이스 URL 지정

PostgreSQL 등 다른 데이터베이스를 사용하려면:

```bash
export DATABASE_URL="postgresql://user:password@localhost/kis_trading"
python -m kis.storage.init_db
```

### 멱등성 보장

`init_database()` 함수는 멱등성을 보장합니다. 여러 번 실행해도 안전하며:
- 테이블이 이미 존재하면 재생성하지 않습니다
- 스키마 버전이 이미 기록되어 있으면 중복 기록하지 않습니다
- 트리거가 이미 존재하면 재생성합니다

## 테스트 실행

### 모든 테스트 실행

```bash
pytest
```

### 특정 테스트 파일 실행

```bash
pytest tests/test_storage_init.py
```

### 상세 출력과 함께 실행

```bash
pytest -v
```

### 테스트 커버리지 확인

```bash
pytest --cov=src/kis/storage
```

## 데이터베이스 스키마

Phase 0에서는 다음 테이블이 생성됩니다:

- `event_log`: Append-only 이벤트 로그 (UPDATE/DELETE 불가)
- `snapshots`: 시장 데이터 스냅샷
- `proposals`: Proposal 정보
- `approvals`: 승인 정보 (token_hash만 저장, 원문 토큰 저장 금지)
- `orders`: 주문 정보
- `fills`: 체결 정보
- `system_state`: 시스템 상태 (kill_switch_status 포함)
- `schema_version`: 스키마 버전 추적

자세한 스키마 정의는 `docs/PHASE0_SPEC.md`의 "8. 데이터 스키마 초안" 섹션을 참조하세요.

## 주의사항

- **비밀정보 보호**: `.env` 파일이나 비밀키는 절대 커밋하지 마세요. `.gitignore`에 포함되어 있습니다.
- **데이터베이스 파일**: 로컬 SQLite 파일(`*.db`, `*.sqlite`)은 `.gitignore`에 포함되어 커밋되지 않습니다.
- **event_log 보호**: `event_log` 테이블은 append-only입니다. UPDATE나 DELETE 시도 시 데이터베이스 레벨에서 차단됩니다.

## 개발 가이드

### 모듈 임포트

```python
from kis.storage.models import EventLog, Proposal, Approval
from kis.storage.init_db import init_database
```

### 데이터베이스 세션 사용

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from kis.storage.models import EventLog

engine = create_engine("sqlite:///kis_trading.db")
Session = sessionmaker(bind=engine)
session = Session()

# 사용 예시
event = EventLog(
    event_type="test",
    correlation_id="test-1",
    actor="test",
    payload_json={"key": "value"}
)
session.add(event)
session.commit()
session.close()
```

## Phase 0 제약사항

- **실거래 금지**: Phase 0에서는 모의투자만 허용됩니다
- **외부 API 연동 금지**: 시장데이터 API 연동은 Phase 0에서 제외됩니다
- **최적화 금지**: 전략 최적화 및 튜닝은 제외됩니다

자세한 내용은 `docs/PHASE0_SPEC.md`를 참조하세요.

