# KIS Trading System - 운영 Runbook (Phase 0)

## 개요

이 문서는 KIS Trading System의 Phase 0 운영 절차를 정의합니다. **운영 안전장치 없이는 실거래 금지** 원칙을 구체적 절차와 체크리스트로 명시합니다.

## 중요 원칙

- **Phase 0에서는 절대 실거래하지 않습니다.** 모든 주문은 모의투자 환경에서만 실행됩니다.
- **승인 없이는 주문 불가**: Execution Server에서 승인 토큰 검증을 서버 레벨에서 강제합니다.
- **Kill switch 기본 ON**: 시스템 시작 시 Kill switch는 기본적으로 활성화(ACTIVE) 상태입니다.
- **event_log는 감사의 기준**: 모든 운영 이벤트는 append-only event_log에 기록되며, 삭제/수정이 불가능합니다.

---

## 1. 정상 운영 절차

### 1.1 데이터베이스 초기화

**목적**: 데이터베이스 스키마 생성 및 초기화

```bash
# macOS/Linux
PYTHONPATH=src python -m kis.storage.init_db

# Windows PowerShell
$env:PYTHONPATH="src"; python -m kis.storage.init_db
```

**확인 사항**:
- `kis_trading.db` 파일이 생성되었는지 확인
- 콘솔에 "Database initialized successfully" 메시지 확인

**주의사항**:
- 기존 DB 파일이 있으면 스키마 변경이 반영되지 않을 수 있습니다. 개발 단계에서는 기존 DB 파일을 삭제하고 재초기화하세요.

### 1.2 Engine 모듈 실행

**목적**: 시장 데이터 스냅샷 생성 및 Proposal 생성

```bash
# macOS/Linux
PYTHONPATH=src python -m kis.engine.run

# Windows PowerShell
$env:PYTHONPATH="src"; python -m kis.engine.run
```

**동작**:
1. `data/sample_snapshot.json` 파일 로드
2. `snapshots` 테이블에 스냅샷 저장
3. Phase 0 고정 파라미터를 만족하는 Proposal 생성
4. `proposals` 테이블에 Proposal 저장 (status: `pending`)
5. `event_log`에 `proposal_created` 이벤트 기록

**확인 사항**:
- 콘솔에 `proposal_id`와 `correlation_id` 출력 확인
- `proposals` 테이블에 새 레코드 생성 확인

### 1.3 GUI 서버 시작

**목적**: Proposal 조회 및 승인/거부 인터페이스 제공

```bash
# macOS/Linux
PYTHONPATH=src uvicorn kis.gui.app:app --port 8001 --reload

# Windows PowerShell
$env:PYTHONPATH="src"; uvicorn kis.gui.app:app --port 8001 --reload
```

**확인 사항**:
- 서버가 `http://localhost:8001`에서 시작되었는지 확인
- API 문서: `http://localhost:8001/docs` 접속 가능 확인

### 1.4 Execution 서버 시작

**목적**: 승인 토큰 검증 및 주문 실행 게이트

```bash
# macOS/Linux
export EXECUTION_JWT_SECRET="your-secret-key-here"
PYTHONPATH=src uvicorn kis.execution.app:app --port 8002 --reload

# Windows PowerShell
$env:EXECUTION_JWT_SECRET="your-secret-key-here"
$env:PYTHONPATH="src"
uvicorn kis.execution.app:app --port 8002 --reload
```

**주의사항**:
- `EXECUTION_JWT_SECRET` 환경변수는 반드시 설정해야 합니다. 이는 Execution Server만 알고 있는 비밀키입니다.
- GUI는 이 비밀키를 보유하지 않으며, 토큰 발급만 요청합니다.

**확인 사항**:
- 서버가 `http://localhost:8002`에서 시작되었는지 확인
- API 문서: `http://localhost:8002/docs` 접속 가능 확인

### 1.5 승인 흐름

**단계별 절차**:

1. **Proposal 조회**
   ```bash
   curl http://localhost:8001/proposals
   ```

2. **Proposal 승인**
   ```bash
   curl -X POST "http://localhost:8001/proposals/1/approve" \
     -H "Content-Type: application/json" \
     -d '{"approved_by": "admin", "expires_in_seconds": 3600}'
   ```

   **동작**:
   - GUI가 Execution Server의 `/issue_token` 엔드포인트에 토큰 발급 요청
   - Execution Server가 JWT 토큰 생성 및 반환
   - GUI가 `approvals` 테이블에 `token_hash`만 저장 (원문 토큰은 저장하지 않음)
   - `proposals.status`를 `approved`로 업데이트
   - `event_log`에 `approval_granted` 이벤트 기록

3. **Proposal 거부 (선택)**
   ```bash
   curl -X POST "http://localhost:8001/proposals/1/reject" \
     -H "Content-Type: application/json" \
     -d '{"rejected_by": "admin", "rejection_reason": "Risk too high"}'
   ```

### 1.6 주문 요청 (모의투자 환경)

**주의**: Phase 0에서는 모의투자 환경만 사용합니다. 실제 브로커 API 호출은 발생하지 않습니다.

```bash
curl -X POST "http://localhost:8002/place_order" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"order_intent": {"symbol": "AAPL", "quantity": 10}}'
```

**처리 순서 (서버 강제)**:
1. Kill switch 확인 (active면 403 반환 + broker 호출 0회)
2. JWT 서명 검증 (실패시 401/403 반환 + broker 호출 0회)
3. 토큰 만료 확인 (만료시 403 반환 + broker 호출 0회)
4. Approval 레코드 검증 (token_hash, token_used_at, token_expires_at)
5. 성공시: token_used_at 업데이트, event_log 기록, broker 호출(모의), orders 생성

---

## 2. Kill switch 운영

### 2.1 기본 상태: ON (ACTIVE)

**중요**: Phase 0에서는 Kill switch가 **기본적으로 활성화(ACTIVE) 상태**입니다.

- 시스템 시작 시 `system_state` 테이블에 레코드가 없으면 기본값은 `ACTIVE`입니다.
- Kill switch가 ACTIVE 상태일 때는 모든 주문 요청이 403 Forbidden으로 거부됩니다.
- 브로커 API 호출은 절대 발생하지 않습니다 (서버 레벨 강제).

### 2.2 해제 조건

Kill switch를 해제(INACTIVE)하려면 다음 조건을 모두 만족해야 합니다:

1. **명시적 운영자 승인**: 운영자가 의도적으로 해제를 결정해야 합니다.
2. **해제 사유 기록**: 해제 사유를 반드시 기록해야 합니다.
3. **모의투자 환경 확인**: Phase 0에서는 모의투자 환경임을 확인해야 합니다.

### 2.3 해제 방법

아래 SQL 예시는 **SQLite 기준 예시**입니다. 운영 환경에서 PostgreSQL 등 다른 RDBMS를 사용할 수도 있으며,
이 경우에는 동일한 논리를 해당 DBMS의 SQL 문법에 맞게 변환해서 사용해야 합니다.

**SQL을 통한 해제 (SQLite 예시)**:

```sql
-- 1) system_state 테이블에 INACTIVE 레코드 추가
INSERT INTO system_state (
    timestamp,
    kill_switch_status,
    kill_switch_reason
) VALUES (
    datetime('now'),
    'inactive',
    '운영자 승인: 모의투자 환경에서 테스트 목적'
);

-- 2) event_log에 kill_switch_deactivated 이벤트 기록
INSERT INTO event_log (
    timestamp,
    event_type,
    correlation_id,
    payload_json
) VALUES (
    datetime('now'),
    'kill_switch_deactivated',
    'manual-kill-switch-change',
    json_object(
        'reason', '운영자 승인: 모의투자 환경에서 테스트 목적',
        'deactivated_by', 'admin'
    )
);
```

### 2.4 해제 사유 기록 위치

해제 사유는 다음 두 곳에 기록되어야 합니다:

1. **`system_state.kill_switch_reason`**: Kill switch 상태 변경 사유
2. **`event_log`**: `kill_switch_deactivated` 이벤트로 감사 추적

### 2.5 재활성화

언제든지 Kill switch를 다시 활성화할 수 있습니다:

```sql
INSERT INTO system_state (
    timestamp,
    kill_switch_status,
    kill_switch_reason
) VALUES (
    datetime('now'),
    'active',
    '운영자 결정: 안전을 위해 모든 거래 중단'
);
```

**주의**: `get_kill_switch_status()` 함수는 가장 최근 `system_state` 레코드를 조회하므로, 새로운 ACTIVE 레코드를 추가하면 즉시 활성화됩니다.

---

## 3. 장애 대응

### 3.1 데이터 결측

**증상**: snapshot 또는 proposal이 부족하여 Proposal 생성 실패

**조치**:
1. `data/sample_snapshot.json` 파일 확인
2. Engine 모듈 재실행: `PYTHONPATH=src python -m kis.engine.run`
3. `event_log`에서 `proposal_created` 이벤트 확인

### 3.2 DB 잠김

**증상**: SQLite 파일이 잠겨 있어 접근 불가

**조치**:
1. 모든 서비스(GUI, Execution) 종료
2. 잠금 파일 확인: `kis_trading.db-journal` 파일 삭제 (주의: 트랜잭션 중이면 안전하지 않을 수 있음)
3. 필요시 서비스 재시작

### 3.3 토큰 발급 실패

**증상**: GUI에서 Proposal 승인 시 502/503 오류

**조치**:
1. Execution 서버 로그 확인
2. `EXECUTION_JWT_SECRET` 환경변수 확인
3. Execution 서버 재시작
4. `event_log`에서 `approval_granted` 이벤트 확인

### 3.4 승인/주문 실패

**증상**: Proposal 승인 또는 주문 실행 실패

**조치**:
1. `event_log` 테이블에서 관련 이벤트 확인:
   ```sql
   SELECT * FROM event_log 
   WHERE correlation_id = '<correlation_id>' 
   ORDER BY timestamp DESC;
   ```
2. `proposals` 테이블에서 Proposal 상태 확인
3. `approvals` 테이블에서 승인 레코드 확인
4. Execution 서버 로그에서 상세 오류 확인

### 3.5 event_log 기록 누락

**증상**: 예상한 이벤트가 event_log에 기록되지 않음

**조치**:
1. DB 연결 확인: 서비스가 올바른 DB 파일에 연결되어 있는지 확인
2. 로그 레벨 확인: Python 로그 레벨이 적절히 설정되어 있는지 확인
3. 트랜잭션 확인: `db.commit()`이 호출되었는지 확인
4. 수동 확인: `event_log` 테이블을 직접 조회하여 기록 여부 확인

---

## 4. 재시작 절차

### 4.1 Engine 재시작

Engine 모듈은 독립적으로 실행되며, 재실행 시 새로운 snapshot과 proposal을 생성합니다.

```bash
PYTHONPATH=src python -m kis.engine.run
```

**주의**: 기존 snapshot/proposal은 유지되며, 새로운 레코드가 추가됩니다.

### 4.2 GUI 재시작

FastAPI 서버를 재시작합니다:

```bash
# 서버 중지: Ctrl+C
# 재시작
PYTHONPATH=src uvicorn kis.gui.app:app --port 8001 --reload
```

**확인 사항**: 서버가 정상적으로 시작되었는지 확인 (`http://localhost:8001/docs`)

### 4.3 Execution 재시작

FastAPI 서버를 재시작합니다:

```bash
# 서버 중지: Ctrl+C
# 재시작
export EXECUTION_JWT_SECRET="your-secret-key-here"
PYTHONPATH=src uvicorn kis.execution.app:app --port 8002 --reload
```

**확인 사항**:
- `EXECUTION_JWT_SECRET` 환경변수 설정 확인
- 서버가 정상적으로 시작되었는지 확인 (`http://localhost:8002/docs`)

---

## 5. 롤백 절차

### 5.1 코드 롤백

**특정 커밋으로 되돌리기**:

```bash
# 커밋 히스토리 확인
git log --oneline

# 특정 커밋으로 되돌리기
git checkout <commit-hash>

# 또는 특정 태그로 되돌리기
git checkout <tag-name>
```

**주의**: 코드 롤백 후에는 서비스를 재시작해야 변경사항이 적용됩니다.

### 5.2 DB 백업/교체

**백업**:

```bash
# SQLite 파일 백업
cp kis_trading.db kis_trading.db.backup
```

**복구**:

```bash
# 백업 파일로 교체
cp kis_trading.db.backup kis_trading.db
```

**주의**: DB 파일 교체 시 모든 서비스를 중지한 후 진행해야 합니다.

### 5.3 스냅샷 재생성

Engine 모듈을 재실행하여 새로운 snapshot과 proposal을 생성합니다:

```bash
PYTHONPATH=src python -m kis.engine.run
```

---

## 6. 실거래 전환 금지 조건

### 6.1 Phase 0 제한사항

**Phase 0에서는 실거래/실주문/실 브로커 API 호출을 포함한 모든 실거래 행위가 전면 금지되며, Spy/Mock/모의 환경에서의 주문 흐름 검증만 허용됩니다.**

### 6.2 Phase 1 게이트 조건 (향후)

실거래 전환(Phase 1+)은 아래와 같은 **체크리스트를 충족한 경우에만** 가능하며, 이 문서에서는 원칙만 정의합니다.

- Kill switch 기본 상태를 OFF로 두되, 비상 시 즉시 ON으로 전환 가능한 절차 확보
- 실거래 전환/해제를 위한 다단계 운영자 승인 프로세스 구축
- 실시간 모니터링 및 알림 시스템, 장애 대응 Runbook 정비
- 충분한 기간의 백테스트/리허설 거래 검증 및 리스크 검토
- 관련 법규 준수 및 법무/컴플라이언스 부서의 사전 승인

---

## 7. 데이터 저장 및 감사

### 7.1 저장되는 데이터

다음 데이터가 데이터베이스에 저장됩니다:

- **스냅샷**: `snapshots` 테이블에 시장 데이터 스냅샷 저장
- **파라미터**: Proposal 생성 시 사용된 파라미터가 `proposals.config_hash`에 저장
- **Proposal**: `proposals` 테이블에 모든 생성된 Proposal 저장
- **승인**: `approvals` 테이블에 모든 승인/거부 결정 저장 (token_hash만 저장)
- **주문**: `orders` 테이블에 모든 주문 요청 저장
- **체결 결과**: `fills` 테이블에 모든 체결 결과 저장 (향후 구현)

### 7.2 event_log의 역할

**event_log는 감사의 기준 기록입니다.**

- **append-only**: event_log 테이블은 삭제/수정이 불가능합니다 (데이터베이스 레벨 제약).
- **모든 운영 이벤트 기록**: Proposal 생성, 승인, 주문, Kill switch 변경 등 모든 주요 이벤트가 기록됩니다.
- **correlation_id로 추적**: `correlation_id`를 통해 Proposal → 승인 → 주문 → 체결을 연결할 수 있습니다.
- **재현성 보장**: event_log를 통해 특정 시점의 시스템 상태를 재현할 수 있습니다.

### 7.3 재현성 보장

다음 정보가 저장되어 재현성을 보장합니다:

- `git_commit_sha`: 코드 버전 추적
- `schema_version`: 데이터베이스 스키마 버전
- `config_hash`: 사용된 파라미터 해시
- `correlation_id`: 이벤트 간 상관관계 추적

---

## 8. 체크리스트

### 8.1 시스템 시작 전

- [ ] 데이터베이스 초기화 완료
- [ ] `EXECUTION_JWT_SECRET` 환경변수 설정 확인
- [ ] Kill switch 상태 확인 (기본 ACTIVE)
- [ ] 모든 서비스 포트 확인 (GUI: 8001, Execution: 8002)

### 8.2 운영 중

- [ ] event_log 정상 기록 확인
- [ ] Proposal 승인 프로세스 정상 작동 확인
- [ ] 주문 실행 시 Kill switch 검증 확인
- [ ] 모의투자 환경 확인 (실거래 API 호출 없음)

### 8.3 실거래 전환 전 (Phase 1+)

- [ ] Kill switch 기본 OFF 설정
- [ ] 운영자 승인 프로세스 구축
- [ ] 모니터링 시스템 구축
- [ ] 백테스트 검증 완료
- [ ] 법적 검토 완료

---

## 9. 연락처 및 참고 자료

- **사양서**: `docs/PHASE0_SPEC.md`
- **알림 가이드**: `docs/ALERTS.md`
- **롤백 계획**: `docs/ROLLBACK_PLAN.md`
- **README**: `README.md`

