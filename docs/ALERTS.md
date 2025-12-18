# KIS Trading System - 알림 가이드 (Phase 0)

## 개요

이 문서는 KIS Trading System의 알림 트리거와 대응 절차를 정의합니다. Phase 0에서는 로그 기반 알림을 사용하며, 향후 Slack/Email 연동은 Phase 1+에서 구현됩니다.

---

## 알림 채널

### Phase 0: 로그 기반 + 수동 확인

- **로그 파일**: 각 서비스의 콘솔 출력 및 로그 파일 확인
- **수동 확인**: 운영자가 정기적으로 로그를 확인하여 이상 징후 파악
- **event_log 조회**: 데이터베이스의 `event_log` 테이블을 직접 조회하여 이벤트 확인

### 향후: Slack/Email 연동 (Phase 1+)

- **Slack 알림**: 실시간 알림을 Slack 채널로 전송
- **Email 알림**: 중요 이벤트를 Email로 전송
- **알림 집계**: 알림 빈도 및 패턴 분석

---

## 알림 트리거 정의

### 1. Kill switch active 상태에서 주문 요청 발생

**트리거 조건**:
- `order_blocked_killswitch` 이벤트가 `event_log`에 기록됨

**확인 방법**:
```sql
SELECT * FROM event_log 
WHERE event_type = 'order_blocked_killswitch' 
ORDER BY timestamp DESC 
LIMIT 10;
```

**대응 절차**:
1. Kill switch 상태 확인: `system_state` 테이블에서 최신 상태 확인
2. 의도된 동작인지 확인: 운영자가 의도적으로 Kill switch를 활성화했는지 확인
3. 필요시 해제: 모의투자 환경에서 테스트 목적이면 해제 절차 진행 (RUNBOOK.md 참조)

**로그 메시지 예시**:
```
[ERROR] Order blocked: Kill switch is active
```

---

### 2. order_rejected_* 이벤트 연속 발생

**트리거 조건**:
- 일정 시간 내 `order_rejected_*` 이벤트가 N회 이상 발생 (예: 5분 내 10회 이상)

**확인 방법**:
```sql
-- 최근 5분 내 거부 이벤트 확인
SELECT event_type, COUNT(*) as count
FROM event_log
WHERE event_type LIKE 'order_rejected%'
  AND timestamp > datetime('now', '-5 minutes')
GROUP BY event_type;
```

**대응 절차**:
1. 거부 원인 분석: `event_log.payload_json`에서 `reason` 필드 확인
2. 일반적인 원인:
   - `invalid_signature`: 토큰 서명 불일치 → JWT_SECRET 확인
   - `expired`: 토큰 만료 → 토큰 재발급 필요
   - `already used`: 토큰 재사용 시도 → 정상 동작 (1회성 토큰)
   - `Approval record not found`: 승인 레코드 누락 → 승인 프로세스 확인
3. 근본 원인 해결: 위 원인에 따라 적절한 조치 수행

**로그 메시지 예시**:
```
[WARNING] Order rejected: Invalid token signature
[WARNING] Order rejected: Token expired
```

---

### 3. DB 초기화 실패

**트리거 조건**:
- `init_db` 실행 시 예외 발생 또는 오류 메시지 출력

**확인 방법**:
- 콘솔 출력에서 오류 메시지 확인
- Python 예외 스택 트레이스 확인

**대응 절차**:
1. 오류 메시지 확인: 구체적인 오류 내용 파악
2. 일반적인 원인:
   - 파일 권한 문제: DB 파일 생성 권한 확인
   - 스키마 충돌: 기존 테이블과 충돌 → 기존 DB 파일 삭제 후 재초기화
   - 의존성 누락: 필요한 Python 패키지 설치 확인
3. 재시도: 문제 해결 후 `init_db` 재실행

**로그 메시지 예시**:
```
[ERROR] Database initialization failed: ...
```

---

### 4. event_log 기록 실패

**트리거 조건**:
- `log_event()` 함수 호출 시 예외 발생
- 예상한 이벤트가 `event_log` 테이블에 기록되지 않음

**확인 방법**:
```sql
-- 최근 이벤트 확인
SELECT * FROM event_log 
ORDER BY timestamp DESC 
LIMIT 20;

-- 특정 이벤트 타입 확인
SELECT * FROM event_log 
WHERE event_type = '<expected_event_type>' 
ORDER BY timestamp DESC;
```

**대응 절차**:
1. DB 연결 확인: 서비스가 올바른 DB 파일에 연결되어 있는지 확인
2. 트랜잭션 확인: `db.commit()`이 호출되었는지 확인
3. 로그 레벨 확인: Python 로그 레벨이 적절히 설정되어 있는지 확인
4. 수동 기록: 필요시 수동으로 이벤트 기록

**로그 메시지 예시**:
```
[ERROR] Failed to log event: ...
```

---

### 5. Token 발급 실패 (502/503)

**트리거 조건**:
- Execution 서버의 `/issue_token` 엔드포인트가 502 Bad Gateway 또는 503 Service Unavailable 반환

**확인 방법**:
- GUI 서버 로그에서 502/503 오류 확인
- Execution 서버 로그에서 상세 오류 확인

**대응 절차**:
1. Execution 서버 상태 확인: 서버가 정상적으로 실행 중인지 확인
2. `EXECUTION_JWT_SECRET` 확인: 환경변수가 올바르게 설정되었는지 확인
3. 네트워크 연결 확인: GUI → Execution 서버 간 네트워크 연결 확인
4. Execution 서버 재시작: 문제 지속 시 서버 재시작

**로그 메시지 예시**:
```
[ERROR] Token issuance failed: 502 Bad Gateway
[ERROR] Token issuance failed: 503 Service Unavailable
```

---

## 알림 우선순위

### 높음 (즉시 대응 필요)

1. **Kill switch active 상태에서 주문 요청 발생**: 의도하지 않은 주문 시도 가능성
2. **DB 초기화 실패**: 시스템 시작 불가
3. **event_log 기록 실패**: 감사 추적 불가

### 중간 (빠른 대응 권장)

1. **order_rejected_* 이벤트 연속 발생**: 시스템 오류 또는 설정 문제 가능성
2. **Token 발급 실패**: 승인 프로세스 중단

### 낮음 (모니터링 필요)

1. **일시적 네트워크 오류**: 자동 복구 가능
2. **정상적인 거부 이벤트**: 토큰 만료 등 예상 가능한 이벤트

---

## 모니터링 체크리스트

### 일일 확인 사항

- [ ] `event_log` 테이블에서 최근 24시간 이벤트 확인
- [ ] `order_rejected_*` 이벤트 빈도 확인
- [ ] Kill switch 상태 확인
- [ ] 서비스 정상 작동 확인 (GUI, Execution)

### 주간 확인 사항

- [ ] `order_rejected_*` 이벤트 패턴 분석
- [ ] DB 파일 크기 확인 (과도한 증가 여부)
- [ ] event_log 기록 누락 여부 확인

### 월간 확인 사항

- [ ] 전체 시스템 건강도 평가
- [ ] 알림 패턴 분석 및 개선 사항 도출
- [ ] 운영 절차 검토 및 업데이트

---

## 향후 개선 사항 (Phase 1+)

### 자동 알림 시스템

- **Slack 연동**: 실시간 알림을 Slack 채널로 전송
- **Email 연동**: 중요 이벤트를 Email로 전송
- **알림 집계**: 알림 빈도 및 패턴 분석

### 알림 규칙 고도화

- **임계값 설정**: 이벤트 빈도 임계값 설정 및 자동 알림
- **알림 그룹핑**: 유사한 알림을 그룹핑하여 노이즈 감소
- **알림 우선순위 자동화**: 이벤트 타입에 따른 우선순위 자동 할당

### 대시보드

- **실시간 모니터링**: 시스템 상태를 실시간으로 모니터링하는 대시보드
- **이벤트 히스토리**: 이벤트 히스토리 시각화
- **트렌드 분석**: 장기 트렌드 분석 및 예측

---

## 참고 자료

- **Runbook**: `docs/RUNBOOK.md`
- **롤백 계획**: `docs/ROLLBACK_PLAN.md`
- **사양서**: `docs/PHASE0_SPEC.md`

