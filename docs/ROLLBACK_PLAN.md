# KIS Trading System - 롤백 계획 (Phase 0)

## 개요

이 문서는 KIS Trading System의 롤백 절차를 정의합니다. 코드 롤백, 데이터 롤백, 그리고 감사/재현성 유지 원칙을 다룹니다.

---

## 코드 롤백

### 커밋 히스토리 확인

롤백 전에 현재 상태와 이전 커밋을 확인합니다:

```bash
# 최근 커밋 히스토리 확인
git log --oneline -n 20

# 특정 커밋 상세 정보 확인
git show <commit-hash>
```

### 특정 커밋으로 되돌리기

**방법 1: checkout 사용 (임시 확인용)**

```bash
# 특정 커밋으로 이동 (detached HEAD 상태)
git checkout <commit-hash>

# 원래 브랜치로 복귀
git checkout main
```

**주의**: 이 방법은 임시 확인용이며, 변경사항을 커밋하지 않습니다.

**방법 2: reset 사용 (영구 롤백)**

```bash
# 특정 커밋으로 되돌리기 (변경사항 유지)
git reset --soft <commit-hash>

# 특정 커밋으로 되돌리기 (변경사항 삭제)
git reset --hard <commit-hash>
```

**주의**: `--hard` 옵션은 모든 변경사항을 삭제하므로 신중하게 사용해야 합니다.

**방법 3: revert 사용 (안전한 롤백)**

```bash
# 특정 커밋의 변경사항을 되돌리는 새 커밋 생성
git revert <commit-hash>
```

**장점**: 기존 히스토리를 유지하면서 변경사항을 되돌립니다.

### 태그 기준 롤백

릴리스 태그가 있는 경우:

```bash
# 태그 목록 확인
git tag

# 특정 태그로 되돌리기
git checkout <tag-name>
```

### 롤백 후 조치

1. **서비스 재시작**: 코드 변경사항 적용을 위해 모든 서비스 재시작
   - GUI 서버 재시작
   - Execution 서버 재시작
   - Engine 모듈 재실행 (필요시)

2. **기능 확인**: 롤백된 버전에서 정상 작동 확인

3. **문서 업데이트**: 롤백 사유 및 날짜를 문서에 기록

---

## 데이터 롤백

### SQLite 파일 백업

롤백 전에 반드시 데이터베이스 파일을 백업합니다:

```bash
# 백업 파일 생성
cp kis_trading.db kis_trading.db.backup.$(date +%Y%m%d_%H%M%S)

# 또는 특정 이름으로 백업
cp kis_trading.db kis_trading.db.backup
```

**백업 파일 명명 규칙**:
- `kis_trading.db.backup.YYYYMMDD_HHMMSS`: 타임스탬프 포함
- `kis_trading.db.backup`: 최신 백업

### SQLite 파일 복구

**단계별 절차**:

1. **모든 서비스 중지**: GUI, Execution 서버 중지

2. **현재 DB 파일 백업** (선택사항):
   ```bash
   cp kis_trading.db kis_trading.db.current.backup
   ```

3. **백업 파일로 교체**:
   ```bash
   cp kis_trading.db.backup kis_trading.db
   ```

4. **서비스 재시작**: GUI, Execution 서버 재시작

5. **데이터 확인**: 복구된 데이터가 정상인지 확인

### 스냅샷 재생성

데이터 롤백 후 새로운 스냅샷과 Proposal을 생성할 수 있습니다:

```bash
# Engine 모듈 재실행
PYTHONPATH=src python -m kis.engine.run
```

**주의**: 기존 snapshot/proposal은 유지되며, 새로운 레코드가 추가됩니다.

### 부분 롤백 원칙

운영(프로덕션) 환경에서는 **DELETE 기반 부분 롤백을 사용하지 않습니다.**

- 기본 원칙은 다음 두 가지 중 하나입니다.
  - **데이터**: DB 파일 백업 복구(또는 DB 스냅샷 복구)를 사용합니다.
  - **코드**: `git revert` 또는 `git reset` 등을 통한 커밋 단위 되돌림 + 서비스 재시작을 사용합니다.
- 운영 DB에서 테이블/레코드를 직접 `DELETE`하는 방식은 **데이터 일관성과 감사 추적을 훼손**하므로 금지합니다.

개발/테스트(로컬, 모의 DB) 환경에서만, 부득이하게 데이터 정리가 필요할 수 있습니다. 이 경우에도 다음 원칙을 반드시 지킵니다.

1. **모의/로컬 DB에서만 수행**: 운영 DB에는 절대 적용하지 않습니다.
2. **조치 전후 event_log 기록**: 부분 정리/리셋을 수행하기 전후에, 해당 조치의 이유와 범위를 `event_log`에 운영 이벤트로 남깁니다.
3. **데이터 일관성 확인**: `correlation_id`를 기준으로 관련 테이블 간 일관성을 다시 점검합니다.

예시(로컬 개발 DB 전용, 운영 금지):

```sql
-- [개발/테스트 전용] 예시: 특정 시점 이후 Proposal/Approval/Order 제거
-- event_log는 append-only이므로 삭제 금지
DELETE FROM proposals WHERE created_at > '<rollback_timestamp>';
DELETE FROM approvals WHERE created_at > '<rollback_timestamp>';
DELETE FROM orders    WHERE created_at > '<rollback_timestamp>';
```

**주의**:
- `event_log` 테이블은 append-only이므로 삭제할 수 없습니다.
- 부분 롤백(DELETE 기반 정리)은 오직 모의/로컬 DB에서만 사용하며, 항상 event_log에 조치 내역을 남겨야 합니다.

---

## 감사/재현성 유지

### event_log 보존

**중요**: `event_log`는 감사의 기준 기록입니다.

- **append-only**: event_log 테이블은 삭제/수정이 불가능합니다 (데이터베이스 레벨 제약).
- **모든 운영 이벤트 기록**: Proposal 생성, 승인, 주문, Kill switch 변경 등 모든 주요 이벤트가 기록됩니다.
- **correlation_id로 추적**: `correlation_id`를 통해 Proposal → 승인 → 주문 → 체결을 연결할 수 있습니다.

**event_log 조회 예시**:

```sql
-- 특정 correlation_id의 모든 이벤트 조회
SELECT * FROM event_log 
WHERE correlation_id = '<correlation_id>' 
ORDER BY timestamp ASC;

-- 특정 시간 범위의 이벤트 조회
SELECT * FROM event_log 
WHERE timestamp BETWEEN '<start_time>' AND '<end_time>' 
ORDER BY timestamp ASC;

-- 특정 이벤트 타입 조회
SELECT * FROM event_log 
WHERE event_type = '<event_type>' 
ORDER BY timestamp DESC;
```

### 스냅샷 보존

`snapshots` 테이블에 모든 시점의 시장 데이터 스냅샷이 보관됩니다:

```sql
-- 모든 스냅샷 조회
SELECT snapshot_id, asof, source, created_at 
FROM snapshots 
ORDER BY created_at DESC;

-- 특정 시점의 스냅샷 조회
SELECT * FROM snapshots 
WHERE asof = '<timestamp>';
```

### Proposal 보존

`proposals` 테이블에 모든 생성된 Proposal이 보관됩니다:

```sql
-- 모든 Proposal 조회
SELECT proposal_id, created_at, status, correlation_id 
FROM proposals 
ORDER BY created_at DESC;

-- 특정 Proposal의 상세 정보 조회
SELECT * FROM proposals 
WHERE proposal_id = <proposal_id>;
```

### 승인/주문 기록 보존

`approvals` 및 `orders` 테이블에 모든 승인/주문 이력이 보관됩니다:

```sql
-- 모든 승인 조회
SELECT approval_id, proposal_id, status, approved_at, rejected_at 
FROM approvals 
ORDER BY approved_at DESC;

-- 모든 주문 조회
SELECT order_id, correlation_id, status, created_at 
FROM orders 
ORDER BY created_at DESC;
```

### 재현성 보장 정보

다음 정보가 저장되어 재현성을 보장합니다:

- **git_commit_sha**: 코드 버전 추적
- **schema_version**: 데이터베이스 스키마 버전
- **config_hash**: 사용된 파라미터 해시
- **correlation_id**: 이벤트 간 상관관계 추적

**재현성 확인 예시**:

```sql
-- 특정 Proposal의 재현성 정보 확인
SELECT 
    proposal_id,
    git_commit_sha,
    schema_version,
    config_hash,
    correlation_id,
    created_at
FROM proposals 
WHERE proposal_id = <proposal_id>;
```

---

## 롤백 체크리스트

### 롤백 전

- [ ] 롤백 사유 명확히 문서화
- [ ] 현재 상태 백업 (코드: git commit, 데이터: DB 파일 복사)
- [ ] 롤백 대상 커밋/데이터 확인
- [ ] 영향 범위 분석 (어떤 기능/데이터가 영향받는지)

### 롤백 중

- [ ] 모든 서비스 중지
- [ ] 코드 롤백 실행
- [ ] 데이터 롤백 실행 (필요시)
- [ ] 롤백 완료 확인

### 롤백 후

- [ ] 서비스 재시작
- [ ] 기능 정상 작동 확인
- [ ] 데이터 일관성 확인
- [ ] event_log에 롤백 이벤트 기록 (선택사항)
- [ ] 롤백 사유 및 날짜 문서화

---

## 롤백 시나리오

### 시나리오 1: 최근 커밋으로 롤백

**상황**: 최근 커밋에서 버그 발견, 이전 커밋으로 롤백 필요

**절차**:
1. 현재 커밋 확인: `git log --oneline -n 5`
2. 이전 커밋으로 롤백: `git reset --hard <previous-commit>`
3. 서비스 재시작
4. 기능 확인

### 시나리오 2: 특정 기능 롤백

**상황**: 특정 기능만 롤백하고 나머지는 유지

**절차**:
1. 해당 기능의 커밋 확인: `git log --oneline --grep="<feature-name>"`
2. revert 사용: `git revert <commit-hash>`
3. 서비스 재시작
4. 기능 확인

### 시나리오 3: 데이터 롤백

**상황**: 잘못된 데이터가 입력되어 특정 시점으로 롤백 필요

**절차**:
1. 모든 서비스 중지
2. DB 파일 백업: `cp kis_trading.db kis_trading.db.current.backup`
3. 백업 파일로 교체: `cp kis_trading.db.backup kis_trading.db`
4. 서비스 재시작
5. 데이터 확인

---

## 주의사항

### event_log는 롤백 불가

- `event_log` 테이블은 append-only이므로 삭제/수정이 불가능합니다.
- 롤백 시에도 `event_log`는 유지되며, 이를 통해 롤백 이전 상태를 추적할 수 있습니다.

### 데이터 일관성

- 롤백 후 데이터 일관성을 반드시 확인해야 합니다.
- `correlation_id`를 통해 관련 레코드 간 일관성을 확인할 수 있습니다.

### 백업 정책

- 정기적으로 데이터베이스 파일을 백업하는 것을 권장합니다.
- 중요 변경 전에는 반드시 백업을 수행하세요.

---

## 참고 자료

- **Runbook**: `docs/RUNBOOK.md`
- **알림 가이드**: `docs/ALERTS.md`
- **사양서**: `docs/PHASE0_SPEC.md`

