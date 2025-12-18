# Phase 0 사양서 (PHASE0_SPEC)

## 1. Phase 0 목표

Phase 0은 **모의투자 환경에서 3단 아키텍처(Engine-GUI-Execution)의 기본 구조를 구축하고, 승인 기반 주문 실행 시스템의 핵심 메커니즘을 검증**하는 단계입니다.

### 핵심 목표
- Engine(분석/Proposal) – GUI(승인/정책) – Execution(주문) 3단 분리 아키텍처 구현
- 승인 없이는 주문 실행 불가능한 시스템 구축 (서버 레벨 강제)
- 모의투자 환경에서 전체 플로우 검증
- 재현성/감사를 위한 데이터 저장 체계 구축
- Kill switch 기본 메커니즘 구현

## 2. In Scope (Phase 0에서 포함)

### 아키텍처
- **3단 분리 스캐폴딩**: Engine(분석/Proposal) – GUI(승인/정책) – Execution(주문) 기본 구조 구축
- **승인 강제(서버)**: Execution Server에서만 주문 API 호출 가능, 승인 토큰 검증 필수
- **이벤트 로그/스냅샷/감사 저장 스키마 초안**: append-only 이벤트 로그, 데이터 스냅샷, 재현성 보장 스키마 설계
- **Kill switch**: 기본 메커니즘 구현 (시작 시 기본 ON, 손실/오류/데이터 결측 시 자동 중단)
- **최소 테스트/게이트**: 각 모듈 단위 테스트 및 통합 테스트, 검증 게이트 통과

### 기능
- 모의투자 환경 연동 (실거래 금지)
- 승인 토큰 기반 주문 실행 제어 (서버 강제)
- Kill switch 기본 구현 (손실/오류/데이터 결측 시 자동 중단)
- 기본 로깅 및 감사 추적 (이벤트 로그 기반)

### 운영 파라미터 (중립 모드 - 고정값)
- 연변동성: 12%
- MDD (Maximum Drawdown): -15%
- 최대 종목 수: 20종목
- 종목당 최대 할당: 8%
- KR/US 비율: 40/60
- 리밸런싱 주기: 월 1회 (트리거/워크플로우 수준만)

## 3. Out of Scope (Phase 0에서 제외)

### 금지 사항
- **실거래 연동 금지**: Phase 0에서는 모의투자만 허용
- **종목선정/전략 고도화 금지**: 기본 Proposal 생성 로직만 구현, 전략 최적화 제외
- **최적화/튜닝 금지**: 파라미터 튜닝, 백테스팅 최적화 등은 제외
- **성과지표 개선 금지**: 수익률, 샤프 비율 등 성과 지표 개선 작업 제외
- **수익 보장 표현 금지**: 모든 문서/코드/출력에서 수익 보장 관련 표현 사용 금지

### 제외 기능
- 실거래 API 연동
- 종목 선정 알고리즘 고도화
- 전략 최적화 및 튜닝
- 파라미터 자동 최적화
- 백테스팅 엔진
- 성과 지표 개선 도구
- 고급 리스크 관리 (기본 Kill switch만 포함)
- 운영 안전장치 고도화 (로그/알림/롤백/재시작 Runbook은 Phase 1 이후)

## 4. 아키텍처 설계 원칙

### 4.1 서버 강제 아키텍처

**주문 API 호출은 Execution Server(주문 게이트웨이) 단일 컴포넌트에서만 가능하다. 이 서버만 브로커(KIS) API 자격증명(키/시크릿)을 보유한다.**

**Engine 및 GUI는 브로커 API 자격증명을 절대 보유하지 않는다. 승인 없이 브로커 API를 직접 호출하는 경로는 구조적으로 존재하지 않는다.**

**Execution Server는 승인 토큰 검증 실패 시 항상 401/403을 반환하며, 이 경우 브로커 API 호출이 절대 발생하지 않는다(서버 강제).**

### 4.2 모듈 분리 원칙
- Engine: 시장 데이터 분석 및 Proposal 생성 (브로커 API 자격증명 없음)
- GUI: Proposal 승인/거부 및 정책 설정 (브로커 API 자격증명 없음)
- Execution Server: 승인된 Proposal만 주문 실행 (브로커 API 자격증명 보유, 승인 토큰 검증 필수)
- Storage: 데이터 스냅샷, 파라미터, Proposal, 승인, 주문/체결 결과 저장

**승인 토큰의 서명키(또는 HMAC secret)는 Execution Server(또는 동일 보안 경계의 Approval Service)에만 존재한다. GUI는 승인 의사결정과 토큰 발급 요청만 수행하며, 서명키를 보유하거나 토큰을 직접 서명하지 않는다.**

## 5. 운영 고정값 (중립 모드)

Phase 0에서는 다음 값들을 고정값으로 사용합니다. 이 값들은 코드에 하드코딩되거나 설정 파일에 명시되어야 하며, Phase 0 동안 변경 불가입니다.

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| 연변동성 | 12% | 연간 목표 변동성 |
| MDD | -15% | 최대 낙폭 허용치 |
| 최대 종목 수 | 20 | 동시 보유 가능한 최대 종목 수 |
| 종목당 최대 할당 | 8% | 단일 종목에 할당 가능한 최대 비중 |
| KR/US 비율 | 40/60 | 한국/미국 시장 비중 |
| 리밸런싱 주기 | 월 1회 | 포트폴리오 재조정 주기 |

## 6. 검증 게이트

Phase 0 완료를 위해서는 다음 게이트를 모두 통과해야 합니다.

### 6.1 데이터 게이트
- [ ] 시장 데이터 수집 및 스냅샷 저장 기능 동작 확인
- [ ] 데이터 결측 시 Kill switch 작동 확인
- [ ] 데이터 스키마가 재현성 요구사항을 만족하는지 확인

### 6.2 리스크 게이트
- [ ] MDD -15% 초과 시 Kill switch 작동 확인
- [ ] 종목당 8% 할당 제한 준수 확인
- [ ] 최대 20종목 제한 준수 확인
- [ ] KR/US 40/60 비율 준수 확인

### 6.3 집행 게이트
- [ ] 승인 없이 주문 API 호출 시도 시 서버에서 거부되는지 확인
- [ ] 승인 토큰 없이 Execution 모듈이 주문을 실행할 수 없는지 확인
- [ ] 승인된 Proposal만 주문이 실행되는지 확인
- [ ] 모의투자 환경에서만 동작하는지 확인 (실거래 API 호출 불가능)
- [ ] Execution Server는 주문 엔드포인트에서 kill_switch_status=active인 경우 항상 403을 반환하며, 이 경우 브로커 API 호출이 절대 발생하지 않는다(서버 강제)

### 6.4 감사 게이트
- [ ] 모든 Proposal이 저장되는지 확인
- [ ] 모든 승인/거부 결정이 저장되는지 확인
- [ ] 모든 주문/체결 결과가 저장되는지 확인
- [ ] 파라미터 변경 이력이 저장되는지 확인
- [ ] 데이터 스냅샷이 저장되는지 확인
- [ ] 저장된 데이터로 재현 가능한지 확인

## 7. Definition of Done (DoD)

Phase 0 완료를 위한 구체적이고 테스트 가능한 기준입니다.

### 7.1 아키텍처 DoD
- [ ] Engine 모듈이 독립적으로 Proposal을 생성할 수 있음
- [ ] GUI 모듈이 Engine의 Proposal을 수신하고 승인/거부 결정을 내릴 수 있음
- [ ] Execution 모듈이 승인 토큰/승인 상태 없이는 주문 API를 호출할 수 없음 (서버 레벨 차단)
- [ ] 세 모듈 간 통신이 명확한 인터페이스로 정의되어 있음

### 7.2 승인 시스템 DoD
- [ ] GUI에서 승인한 Proposal만 Execution으로 전달됨
- [ ] 승인 토큰이 발급되고 Execution에 전달됨
- [ ] 승인 토큰은 서명된 형식(JWT 또는 HMAC 서명 토큰)이며 proposal_id 및 주문 대상(심볼/수량/방향)과 바인딩된다
- [ ] 승인 토큰은 expires_at(만료)와 jti(토큰 ID)를 가지며 1회성(one-time)으로만 사용 가능하다(재사용 시 403)
- [ ] DB에는 승인 토큰 원문을 저장하지 않고 token_hash만 저장한다
- [ ] Execution이 승인 토큰 없이 주문을 시도하면 서버에서 401/403 에러 반환
- [ ] 승인 상태가 데이터베이스에 저장됨

### 7.3 모의투자 DoD
- [ ] 실거래 API 엔드포인트에 접근할 수 없음 (코드 레벨 차단 또는 설정 차단)
- [ ] 모의투자 API만 사용됨
- [ ] 모의투자 환경에서 주문/체결이 정상 동작함

### 7.4 Kill Switch DoD
- [ ] 시스템 시작 시 kill_switch_status=active가 기본값이며, 운영자 수동 해제 + 사유 기록 없이는 주문이 절대 진행되지 않는다
- [ ] Execution Server는 주문 엔드포인트에서 kill_switch_status=active인 경우 항상 403을 반환하며, 이 경우 브로커 API 호출이 절대 발생하지 않는다(서버 강제)
- [ ] 손실이 MDD(-15%)를 초과하면 자동으로 모든 거래 중단
- [ ] 데이터 결측이 발생하면 자동으로 거래 중단
- [ ] 시스템 오류 발생 시 자동으로 거래 중단
- [ ] Kill switch 상태가 GUI에 표시됨
- [ ] Kill switch 해제는 수동으로만 가능 (자동 해제 금지)

### 7.5 데이터 저장/감사 DoD
- [ ] 모든 주요 상태 변화는 append-only 이벤트 로그로 저장(삭제/수정 금지). correlation_id로 Proposal→승인→주문→체결을 연결한다
- [ ] Proposal/주문/체결 레코드는 생성 당시 git_commit_sha(또는 build_version), schema_version, config_hash를 함께 저장한다
- [ ] 시장 데이터 스냅샷이 타임스탬프와 함께 저장됨
- [ ] 모든 Proposal이 생성 시점, 파라미터, 내용과 함께 저장됨
- [ ] 모든 승인/거부 결정이 결정자, 시점, 이유와 함께 저장됨
- [ ] 모든 주문이 주문 시점, 승인 토큰 해시(token_hash), 결과와 함께 저장됨
- [ ] 모든 체결이 체결 시점, 가격, 수량과 함께 저장됨
- [ ] 저장된 데이터로 특정 시점의 상태를 재현할 수 있음

### 7.6 운영 파라미터 DoD
- [ ] 연변동성 12%가 코드/설정에 명시되어 있음
- [ ] MDD -15%가 코드/설정에 명시되어 있음
- [ ] 최대 20종목 제한이 코드에 구현되어 있음
- [ ] 종목당 8% 할당 제한이 코드에 구현되어 있음
- [ ] KR/US 40/60 비율이 코드에 구현되어 있음
- [ ] Phase 0에서는 월 1회 리밸런싱 트리거(또는 수동 실행 워크플로우)만 정의하고, Proposal 생성과 승인/집행 파이프라인 검증까지만 수행한다

### 7.7 테스트 DoD
- [ ] 각 모듈의 단위 테스트가 작성됨
- [ ] 통합 테스트가 작성됨 (Engine → GUI → Execution 플로우)
- [ ] 승인 없이 주문 시도 시 실패하는 테스트가 작성됨
- [ ] Kill switch 작동 테스트가 작성됨
- [ ] 데이터 저장/조회 테스트가 작성됨

## 8. 데이터 스키마 초안

재현성과 감사를 위해 다음 데이터를 저장해야 합니다. 모든 주요 상태 변화는 append-only 이벤트 로그로 저장되며, correlation_id로 Proposal→승인→주문→체결을 연결합니다.

### 8.1 이벤트 로그 (event_log)
- `event_id`: 고유 ID
- `timestamp`: 이벤트 발생 시점
- `event_type`: 이벤트 유형 (proposal_created, approval_granted, order_placed, fill_executed 등)
- `correlation_id`: Proposal→승인→주문→체결을 연결하는 상관관계 ID
- `actor`: 이벤트를 발생시킨 주체 (engine, gui, execution_server 등)
- `payload_json`: 이벤트 상세 정보 (JSON)
- `prev_hash`: 이전 이벤트 해시 (선택, 체인 검증용)
- `hash`: 현재 이벤트 해시 (선택, 무결성 검증용)

### 8.2 데이터 스냅샷 (snapshots)
- `snapshot_id`: 고유 ID
- `asof`: 스냅샷 기준 시점
- `source`: 데이터 출처
- `payload_json`: 스냅샷 데이터 (JSON)

### 8.3 Proposal (proposals)
- `proposal_id`: 고유 ID
- `created_at`: 생성 시점
- `universe_snapshot_id`: 사용된 시장 데이터 스냅샷 ID
- `config_hash`: 사용된 설정의 해시값
- `git_commit_sha`: Proposal 생성 시점의 Git 커밋 SHA (또는 build_version)
- `schema_version`: 스키마 버전
- `payload_json`: Proposal 내용 JSON (종목, 비중, 거래 유형 등)
- `status`: 상태 (pending, approved, rejected, executed)

### 8.4 승인 (approvals)
- `approval_id`: 고유 ID
- `proposal_id`: 관련 Proposal ID
- `token_hash`: 승인 토큰의 해시값 (원문은 저장하지 않음)
- `token_expires_at`: 토큰 만료 시점
- `token_used_at`: 토큰 사용 시점 (nullable, 1회성 사용 확인용)
- `token_jti`: 토큰 ID (JWT ID)
- `status`: 승인 상태 (approved, rejected)
- `approved_by`: 승인자
- `approved_at`: 승인 시점
- `rejection_reason`: 거부 시 사유 (nullable)

### 8.5 주문 (orders)
- `order_id`: 고유 ID
- `correlation_id`: Proposal→승인→주문을 연결하는 상관관계 ID
- `status`: 주문 상태 (pending, filled, cancelled, rejected)
- `broker_order_id`: 브로커에서 발급한 주문 ID (nullable)
- `payload_json`: 주문 상세 정보 (JSON: proposal_id, approval_id, symbol, quantity, price, order_type 등)
- `created_at`: 주문 생성 시점

### 8.6 체결 (fills)
- `fill_id`: 고유 ID
- `order_id`: 관련 주문 ID
- `correlation_id`: Proposal→승인→주문→체결을 연결하는 상관관계 ID
- `broker_fill_id`: 브로커에서 발급한 체결 ID
- `payload_json`: 체결 상세 정보 (JSON: executed_price, executed_quantity, executed_at 등)
- `created_at`: 체결 시점

### 8.7 시스템 상태 (system_state)
- `state_id`: 고유 ID
- `timestamp`: 상태 기록 시점
- `kill_switch_status`: Kill switch 상태 (active, inactive)
- `kill_switch_reason`: Kill switch 활성화 사유 (nullable)
- `portfolio_value`: 포트폴리오 가치
- `current_mdd`: 현재 MDD
- `active_positions`: 현재 보유 종목 수

## 9. 제약사항 및 경고

### 9.1 실거래 금지
- Phase 0에서는 실거래 API를 사용할 수 없습니다.
- 실거래 API 엔드포인트에 대한 접근은 코드 레벨 또는 설정 레벨에서 차단되어야 합니다.

### 9.2 수익 보장 표현 금지
- 모든 문서, 코드 주석, 로그 메시지, 사용자 인터페이스에서 수익 보장 관련 표현을 사용하지 않습니다.
- 예: "수익을 보장합니다", "이익을 납니다", "돈을 벌 수 있습니다" 등

### 9.3 운영 안전장치
- Phase 0에서는 기본적인 Kill switch만 구현합니다.
- 고급 운영 안전장치(상세 로깅, 알림 시스템, 롤백 메커니즘, 재시작 Runbook)는 Phase 1 이후에 구현됩니다.
- **운영 안전장치가 완성되기 전까지는 실거래를 진행할 수 없습니다.**

## 10. 향후 고려 사항

Phase 0 완료 후 향후 단계에서 고려할 수 있는 항목들입니다. Phase 0에서는 이러한 항목들을 구현하지 않습니다.

- 운영 안전장치 고도화 (상세 로깅, 알림 시스템, 롤백 메커니즘, 재시작 Runbook)
- 소액 실거래 환경 준비 (운영 안전장치 완성 후)
- 파라미터 튜닝 도구 (선택적)
- 고급 리스크 관리 기능

---

**문서 버전**: 1.0  
**최종 수정일**: Phase 0 시작일  
**담당자**: Cursor Agent

