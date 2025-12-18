# 백로그 (BACKLOG)

## 티켓 운영 규칙

### 작업 단위
- **BACKLOG 티켓 1개 단위로만 작업**: 한 번에 하나의 티켓만 작업합니다.
- **티켓 밖 변경 금지**: 티켓에 명시되지 않은 기능이나 변경사항은 작업하지 않습니다.
- **완료 시 필수 항목**:
  - DoD 체크리스트 확인
  - 테스트 실행 및 통과 확인
  - 변경요약 문서 작성

### 티켓 템플릿
각 티켓은 다음 구조를 따릅니다:
- **ID**: 고유 식별자 (예: P0-001)
- **제목**: 간결한 작업 설명
- **목적**: 왜 이 작업이 필요한지
- **산출물**: 작업 완료 시 생성/수정되는 파일/기능
- **DoD**: Definition of Done (테스트 가능한 완료 기준)
- **테스트**: 수행해야 할 테스트 항목
- **리스크**: 작업 중 발생할 수 있는 위험 요소
- **영향범위**: 이 티켓이 영향을 미치는 모듈/시스템

---

## Phase 0 티켓 목록

### P0-001: 프로젝트 기본 구조 및 데이터 스키마 설계

**제목**: 프로젝트 기본 구조 및 데이터 스키마 설계

**목적**: 
- Engine-GUI-Execution 3단 아키텍처의 기본 디렉토리 구조를 설정
- 재현성/감사를 위한 데이터베이스 스키마를 설계하고 초기화 스크립트 작성
- 프로젝트 의존성 및 개발 환경 설정

**산출물**:
- `/engine`, `/gui`, `/execution`, `/storage` 디렉토리 구조
- 데이터베이스 스키마 정의 파일 (SQL 또는 ORM 모델)
- 데이터베이스 초기화 스크립트
- 프로젝트 의존성 파일 (requirements.txt, package.json 등)
- 기본 설정 파일 (config.yaml 또는 .env.example)
- event_log 테이블 골격 (append-only 이벤트 로그)

**DoD**:
- [ ] 3단 아키텍처 디렉토리 구조가 생성됨
- [ ] 데이터베이스 스키마가 PHASE0_SPEC.md의 스키마 초안을 반영함
- [ ] DB 마이그레이션/초기화는 멱등(idempotent)이며 2회 실행해도 실패하지 않는다
- [ ] event_log 테이블이 correlation_id, event_type, actor, payload_json 필드를 포함함
- [ ] event_log는 append-only 전제로 UPDATE/DELETE 경로가 존재하지 않는다(테스트로 확인)
- [ ] proposals 테이블이 universe_snapshot_id, config_hash, git_commit_sha, schema_version 필드를 포함함
- [ ] approvals 테이블이 token_hash, token_expires_at, token_used_at, token_jti 필드를 포함함
- [ ] orders/fills 테이블이 correlation_id, payload_json 필드를 포함함
- [ ] system_state 테이블이 존재하며 kill_switch_status 필드를 포함함
- [ ] schema_version이 존재하고 초기화 시점에 기록된다(테스트로 확인)
- [ ] 데이터베이스 초기화 스크립트가 정상 실행됨
- [ ] 프로젝트 의존성이 명시되어 있고 설치 가능함
- [ ] 기본 설정 파일이 생성됨
- [ ] .gitignore에 .env, secrets/, 키/토큰 패턴이 포함되어 비밀정보 커밋이 방지된다

**테스트**:
- 데이터베이스 초기화 스크립트 실행 테스트
- 스키마가 모든 필수 테이블을 포함하는지 확인 (event_log, snapshots, proposals, approvals, orders, fills)
- correlation_id 필드가 관련 테이블에 포함되어 있는지 확인
- 프로젝트 의존성 설치 테스트

**리스크**:
- 스키마 설계 오류로 인한 후속 작업 지연
- 의존성 버전 충돌

**영향범위**:
- 전체 프로젝트 구조
- 모든 모듈 (Engine, GUI, Execution, Storage)

---

### P0-002: Engine 모듈 기본 구현 (Proposal 생성)

**제목**: Engine 모듈 기본 구현 (Proposal 생성)

**목적**:
- 샘플/모의 데이터를 입력으로 Proposal을 생성하는 Engine 모듈 구현
- Phase 0 고정 파라미터(연변동성 12%, MDD -15%, 최대 20종목 등)를 반영한 Proposal 생성 로직
- Phase 0에서는 외부 시장데이터 API 연동을 하지 않는다. 대신 샘플/모의 데이터(파일 또는 고정 JSON)로 snapshot을 생성·저장하고, 그 snapshot을 입력으로 Proposal을 생성한다

**산출물**:
- Engine 모듈 기본 코드
- Proposal 생성 로직
- 샘플/모의 데이터 처리 기능
- 데이터 스냅샷 저장 기능 (샘플 데이터 기반)
- Proposal 데이터 모델

**DoD**:
- [ ] 샘플/모의 데이터(파일 또는 고정 JSON)로 snapshot을 생성할 수 있음
- [ ] 생성된 snapshot을 입력으로 Proposal을 생성할 수 있음
- [ ] Engine이 고정 파라미터를 반영하여 Proposal을 생성할 수 있음
- [ ] 생성된 Proposal이 최대 20종목, 종목당 8% 제한을 준수함
- [ ] 생성된 Proposal이 KR/US 40/60 비율을 준수함
- [ ] Proposal이 데이터베이스에 저장됨
- [ ] 시장 데이터 스냅샷(샘플 데이터 기반)이 저장됨

**테스트**:
- Engine 단위 테스트 (Proposal 생성 로직)
- 샘플 데이터로 snapshot 생성 테스트
- 파라미터 제한 준수 테스트 (20종목, 8% 할당, 40/60 비율)
- 데이터 저장 테스트

**리스크**:
- 샘플 데이터 품질 및 구조 문제
- Proposal 생성 로직 오류

**영향범위**:
- Engine 모듈
- Storage 모듈 (Proposal 저장)

---

### P0-003: GUI 모듈 기본 구현 (승인 시스템)

**제목**: GUI 모듈 기본 구현 (승인 시스템)

**목적**:
- Engine에서 생성된 Proposal을 수신하고 표시하는 GUI 구현
- Proposal 승인/거부 기능 구현
- 승인 결정 후 Execution Server(또는 Approval Service)에 토큰 발급을 요청
- 거부 시 사유 기록

**산출물**:
- GUI 모듈 기본 코드
- Proposal 수신 및 표시 기능
- 승인/거부 UI 및 로직
- Execution Server와의 인터페이스 (토큰 발급 요청, Execution만 서명키 보유)
- 승인 상태 저장 기능

**DoD**:
- [ ] GUI가 Engine의 Proposal을 수신할 수 있음
- [ ] GUI에서 Proposal을 승인/거부할 수 있음
- [ ] 승인 결정 후 Execution Server(또는 Approval Service)에 토큰 발급을 요청함
- [ ] 토큰은 서버에서 서명되어 반환되며, GUI는 토큰 원문을 저장하지 않고 token_hash만 저장함
- [ ] GUI는 토큰 서명키를 보유하지 않음
- [ ] 승인 토큰에 proposal_id, 심볼/수량/방향, expires_at, jti가 포함됨
- [ ] GUI는 브로커 API 자격증명을 보유하지 않음 (Execution Server만 보유)
- [ ] 승인/거부 결정이 데이터베이스에 저장됨
- [ ] 승인된 Proposal만 Execution으로 전달됨
- [ ] 거부 시 사유가 기록됨

**테스트**:
- GUI 단위 테스트 (승인/거부 로직)
- 토큰 발급 요청 테스트 (서버에 요청하고 서명된 토큰을 받는지 확인)
- 토큰 해시 저장 테스트 (원문은 저장되지 않음)
- 승인 상태 저장 테스트
- Proposal 전달 테스트

**리스크**:
- GUI 프레임워크 선택 및 구현 복잡도
- 승인 토큰 보안 이슈

**영향범위**:
- GUI 모듈
- Engine 모듈 (Proposal 수신)
- Execution 모듈 (승인된 Proposal 전달)
- Storage 모듈 (승인 상태 저장)

---

### P0-004: Execution 모듈 기본 구현 (승인 기반 주문 실행)

**제목**: Execution 모듈 기본 구현 (승인 기반 주문 실행)

**목적**:
- 승인 토큰/승인 상태를 검증하는 Execution 모듈 구현
- 승인된 Proposal만 주문 실행
- 승인 토큰 없이 주문 API 호출 시도 시 서버에서 거부되도록 구현
- 모의투자 환경에서만 동작하도록 제한

**산출물**:
- Execution Server 모듈 기본 코드 (주문 게이트웨이)
- 승인 토큰 검증 로직 (서버 강제)
- 주문 실행 로직 (모의투자만)
- 주문/체결 결과 저장 기능
- 실거래 API 차단 메커니즘
- 브로커 API 자격증명 보유 (Execution Server만 보유)

**DoD**:
- [ ] Execution Server만 브로커(KIS) API 자격증명을 보유함
- [ ] Engine 및 GUI는 브로커 API 자격증명을 보유하지 않음
- [ ] Execution Server가 승인 토큰 없이 주문을 시도하면 항상 401/403 에러 반환
- [ ] 승인 토큰 검증 실패 시 브로커 API 호출이 절대 발생하지 않음 (서버 강제)
- [ ] 승인된 Proposal만 주문이 실행됨
- [ ] 모의투자 API만 사용됨 (실거래 API 호출 불가능)
- [ ] 주문/체결 결과가 데이터베이스에 저장됨
- [ ] 승인 토큰 사용 시 token_used_at이 기록되고 재사용 불가능함

**테스트**:
- **서버 강제 테스트**: 승인 토큰 없이 주문 시도 시 401/403 반환 + 브로커 API 호출 0회 + event_log 기록
- **토큰 위변조 테스트**: 위변조된 토큰으로 주문 시도 시 401/403 반환 + 브로커 API 호출 0회 + event_log 기록
- **토큰 만료 테스트**: 만료된 토큰으로 주문 시도 시 401/403 반환 + 브로커 API 호출 0회 + event_log 기록
- **토큰 재사용 테스트**: 이미 사용된 토큰으로 주문 시도 시 401/403 반환 + 브로커 API 호출 0회 + event_log 기록
- **브로커 호출 0회 증명**: 브로커 클라이언트를 Mock/Spy로 래핑하여 호출 카운트를 assert 하거나, 브로커 호출 함수가 실행될 경우 테스트가 즉시 실패하도록 구성한다
- 승인된 Proposal만 주문 실행되는지 테스트
- 모의투자 환경 동작 테스트
- 실거래 API 차단 테스트
- 주문/체결 저장 테스트

**리스크**:
- 승인 토큰 검증 로직 오류
- 모의투자/실거래 API 구분 실패
- 주문 실행 실패 처리

**영향범위**:
- Execution 모듈
- GUI 모듈 (승인 토큰 전달)
- Storage 모듈 (주문/체결 저장)
- 외부 API (모의투자)

---

### P0-005: Kill Switch 및 기본 안전장치 구현

**제목**: Kill Switch 및 기본 안전장치 구현

**목적**:
- 손실/오류/데이터 결측 시 자동으로 모든 거래를 중단하는 Kill Switch 구현
- MDD -15% 초과 시 자동 중단
- 데이터 결측 시 자동 중단
- 시스템 오류 시 자동 중단
- Kill Switch 상태 표시 및 수동 해제 기능

**산출물**:
- Kill Switch 모듈
- MDD 모니터링 로직
- 데이터 결측 감지 로직
- 시스템 오류 감지 로직
- Kill Switch 상태 저장 기능
- Kill Switch 상태 표시 기능 (GUI)
- 운영 이벤트/알림/런북 초안 문서 (문서 중심)

**DoD**:
- [ ] 시스템 시작 시 kill_switch_status=active가 기본값이며, 운영자 수동 해제 + 사유 기록 없이는 주문이 절대 진행되지 않음
- [ ] MDD -15% 초과 시 자동으로 모든 거래 중단
- [ ] 데이터 결측 발생 시 자동으로 거래 중단
- [ ] 시스템 오류 발생 시 자동으로 거래 중단
- [ ] Kill Switch 상태가 GUI에 표시됨
- [ ] Kill Switch 해제는 수동으로만 가능 (자동 해제 금지)
- [ ] Kill Switch 상태 및 해제 사유가 데이터베이스에 저장됨
- [ ] 운영 이벤트/알림/런북 초안 문서가 작성됨 (문서 중심, 구현은 Phase 1 이후)

**테스트**:
- 시스템 시작 시 Kill Switch 기본 ON 테스트 (주문 불가능)
- Kill Switch 수동 해제 + 사유 기록 없이 주문 시도 시 실패 테스트
- MDD 초과 시 Kill Switch 작동 테스트
- 데이터 결측 시 Kill Switch 작동 테스트
- 시스템 오류 시 Kill Switch 작동 테스트
- Kill Switch 상태 표시 테스트
- Kill Switch 수동 해제 + 사유 기록 테스트

**리스크**:
- Kill Switch 작동 실패
- MDD 계산 오류
- 데이터 결측 감지 누락

**영향범위**:
- 전체 시스템 (모든 모듈)
- Engine (거래 중단)
- Execution (주문 실행 중단)
- GUI (상태 표시)
- Storage (상태 저장)

---

## 티켓 상태

| 티켓 ID | 제목 | 상태 | 담당자 |
|---------|------|------|--------|
| P0-001 | 프로젝트 기본 구조 및 데이터 스키마 설계 | 대기 | - |
| P0-002 | Engine 모듈 기본 구현 (Proposal 생성) | 대기 | - |
| P0-003 | GUI 모듈 기본 구현 (승인 시스템) | 대기 | - |
| P0-004 | Execution 모듈 기본 구현 (승인 기반 주문 실행) | 대기 | - |
| P0-005 | Kill Switch 및 기본 안전장치 구현 | 대기 | - |

**상태**: 대기 → 진행중 → 검토중 → 완료

---

## 작업 흐름

1. **티켓 선택**: BACKLOG에서 다음 작업할 티켓을 선택
2. **티켓 시작**: 티켓 상태를 "진행중"으로 변경
3. **작업 수행**: 티켓의 산출물을 구현
4. **DoD 확인**: 티켓의 DoD 체크리스트를 모두 완료
5. **테스트 실행**: 티켓의 테스트 항목을 모두 통과
6. **변경요약 작성**: 작업 내용을 요약한 문서 작성
7. **티켓 완료**: 티켓 상태를 "완료"로 변경

---

**문서 버전**: 1.0  
**최종 수정일**: Phase 0 시작일  
**담당자**: Cursor Agent

