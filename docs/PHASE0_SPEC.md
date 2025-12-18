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
- Engine: 시장 데이터 분석 및 Proposal 생성
- GUI: Proposal 승인/거부 및 정책 설정
- Execution: 승인된 Proposal만 주문 실행 (승인 토큰/상태 검증 필수)
- Storage: 데이터 스냅샷, 파라미터, Proposal, 승인, 주문/체결 결과 저장

### 기능
- 모의투자 환경 연동 (실거래 금지)
- 승인 토큰 기반 주문 실행 제어
- Kill switch 기본 구현 (손실/오류/데이터 결측 시 자동 중단)
- 기본 로깅 및 감사 추적

### 운영 파라미터 (중립 모드 - 고정값)
- 연변동성: 12%
- MDD (Maximum Drawdown): -15%
- 최대 종목 수: 20종목
- 종목당 최대 할당: 8%
- KR/US 비율: 40/60
- 리밸런싱 주기: 월 1회

## 3. Out of Scope (Phase 0에서 제외)

### 금지 사항
- **실거래 연동 금지**: Phase 0에서는 모의투자만 허용
- **최적화 작업 금지**: 파라미터 튜닝, 백테스팅 최적화 등은 제외
- **수익 보장 표현 금지**: 모든 문서/코드/출력에서 수익 보장 관련 표현 사용 금지

### 제외 기능
- 실거래 API 연동
- 파라미터 자동 최적화
- 백테스팅 엔진
- 고급 리스크 관리 (기본 Kill switch만 포함)
- 운영 안전장치 고도화 (로그/알림/롤백/재시작 Runbook은 Phase 1 이후)

## 4. 운영 고정값 (중립 모드)

Phase 0에서는 다음 값들을 고정값으로 사용합니다. 이 값들은 코드에 하드코딩되거나 설정 파일에 명시되어야 하며, Phase 0 동안 변경 불가입니다.

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| 연변동성 | 12% | 연간 목표 변동성 |
| MDD | -15% | 최대 낙폭 허용치 |
| 최대 종목 수 | 20 | 동시 보유 가능한 최대 종목 수 |
| 종목당 최대 할당 | 8% | 단일 종목에 할당 가능한 최대 비중 |
| KR/US 비율 | 40/60 | 한국/미국 시장 비중 |
| 리밸런싱 주기 | 월 1회 | 포트폴리오 재조정 주기 |

## 5. 검증 게이트

Phase 0 완료를 위해서는 다음 게이트를 모두 통과해야 합니다.

### 5.1 데이터 게이트
- [ ] 시장 데이터 수집 및 스냅샷 저장 기능 동작 확인
- [ ] 데이터 결측 시 Kill switch 작동 확인
- [ ] 데이터 스키마가 재현성 요구사항을 만족하는지 확인

### 5.2 리스크 게이트
- [ ] MDD -15% 초과 시 Kill switch 작동 확인
- [ ] 종목당 8% 할당 제한 준수 확인
- [ ] 최대 20종목 제한 준수 확인
- [ ] KR/US 40/60 비율 준수 확인

### 5.3 집행 게이트
- [ ] 승인 없이 주문 API 호출 시도 시 서버에서 거부되는지 확인
- [ ] 승인 토큰 없이 Execution 모듈이 주문을 실행할 수 없는지 확인
- [ ] 승인된 Proposal만 주문이 실행되는지 확인
- [ ] 모의투자 환경에서만 동작하는지 확인 (실거래 API 호출 불가능)

### 5.4 감사 게이트
- [ ] 모든 Proposal이 저장되는지 확인
- [ ] 모든 승인/거부 결정이 저장되는지 확인
- [ ] 모든 주문/체결 결과가 저장되는지 확인
- [ ] 파라미터 변경 이력이 저장되는지 확인
- [ ] 데이터 스냅샷이 저장되는지 확인
- [ ] 저장된 데이터로 재현 가능한지 확인

## 6. Definition of Done (DoD)

Phase 0 완료를 위한 구체적이고 테스트 가능한 기준입니다.

### 6.1 아키텍처 DoD
- [ ] Engine 모듈이 독립적으로 Proposal을 생성할 수 있음
- [ ] GUI 모듈이 Engine의 Proposal을 수신하고 승인/거부 결정을 내릴 수 있음
- [ ] Execution 모듈이 승인 토큰/승인 상태 없이는 주문 API를 호출할 수 없음 (서버 레벨 차단)
- [ ] 세 모듈 간 통신이 명확한 인터페이스로 정의되어 있음

### 6.2 승인 시스템 DoD
- [ ] GUI에서 승인한 Proposal만 Execution으로 전달됨
- [ ] 승인 토큰이 생성되고 Execution에 전달됨
- [ ] Execution이 승인 토큰 없이 주문을 시도하면 서버에서 401/403 에러 반환
- [ ] 승인 상태가 데이터베이스에 저장됨

### 6.3 모의투자 DoD
- [ ] 실거래 API 엔드포인트에 접근할 수 없음 (코드 레벨 차단 또는 설정 차단)
- [ ] 모의투자 API만 사용됨
- [ ] 모의투자 환경에서 주문/체결이 정상 동작함

### 6.4 Kill Switch DoD
- [ ] 손실이 MDD(-15%)를 초과하면 자동으로 모든 거래 중단
- [ ] 데이터 결측이 발생하면 자동으로 거래 중단
- [ ] 시스템 오류 발생 시 자동으로 거래 중단
- [ ] Kill switch 상태가 GUI에 표시됨
- [ ] Kill switch 해제는 수동으로만 가능 (자동 해제 금지)

### 6.5 데이터 저장/감사 DoD
- [ ] 시장 데이터 스냅샷이 타임스탬프와 함께 저장됨
- [ ] 모든 Proposal이 생성 시점, 파라미터, 내용과 함께 저장됨
- [ ] 모든 승인/거부 결정이 결정자, 시점, 이유와 함께 저장됨
- [ ] 모든 주문이 주문 시점, 승인 토큰, 결과와 함께 저장됨
- [ ] 모든 체결이 체결 시점, 가격, 수량과 함께 저장됨
- [ ] 저장된 데이터로 특정 시점의 상태를 재현할 수 있음

### 6.6 운영 파라미터 DoD
- [ ] 연변동성 12%가 코드/설정에 명시되어 있음
- [ ] MDD -15%가 코드/설정에 명시되어 있음
- [ ] 최대 20종목 제한이 코드에 구현되어 있음
- [ ] 종목당 8% 할당 제한이 코드에 구현되어 있음
- [ ] KR/US 40/60 비율이 코드에 구현되어 있음
- [ ] 월 1회 리밸런싱 로직이 구현되어 있음

### 6.7 테스트 DoD
- [ ] 각 모듈의 단위 테스트가 작성됨
- [ ] 통합 테스트가 작성됨 (Engine → GUI → Execution 플로우)
- [ ] 승인 없이 주문 시도 시 실패하는 테스트가 작성됨
- [ ] Kill switch 작동 테스트가 작성됨
- [ ] 데이터 저장/조회 테스트가 작성됨

## 7. 데이터 스키마 초안

재현성과 감사를 위해 다음 데이터를 저장해야 합니다.

### 7.1 데이터 스냅샷 (market_snapshots)
- `snapshot_id`: 고유 ID
- `timestamp`: 스냅샷 생성 시점
- `market_data`: 시장 데이터 JSON (가격, 거래량 등)
- `data_source`: 데이터 출처

### 7.2 Proposal (proposals)
- `proposal_id`: 고유 ID
- `created_at`: 생성 시점
- `engine_version`: Engine 버전
- `parameters`: 사용된 파라미터 JSON
- `proposal_content`: Proposal 내용 JSON (종목, 비중, 거래 유형 등)
- `status`: 상태 (pending, approved, rejected, executed)

### 7.3 승인 (approvals)
- `approval_id`: 고유 ID
- `proposal_id`: 관련 Proposal ID
- `approved_at`: 승인 시점
- `approved_by`: 승인자
- `approval_token`: 승인 토큰 (Execution에서 사용)
- `rejection_reason`: 거부 시 사유 (nullable)

### 7.4 주문 (orders)
- `order_id`: 고유 ID
- `proposal_id`: 관련 Proposal ID
- `approval_id`: 관련 승인 ID
- `approval_token`: 사용된 승인 토큰
- `order_type`: 주문 유형 (buy, sell)
- `symbol`: 종목 코드
- `quantity`: 수량
- `price`: 가격
- `order_status`: 주문 상태 (pending, filled, cancelled, rejected)
- `created_at`: 주문 생성 시점
- `executed_at`: 체결 시점 (nullable)

### 7.5 체결 (executions)
- `execution_id`: 고유 ID
- `order_id`: 관련 주문 ID
- `executed_at`: 체결 시점
- `executed_price`: 체결 가격
- `executed_quantity`: 체결 수량
- `execution_type`: 체결 유형 (full, partial)

### 7.6 시스템 상태 (system_state)
- `state_id`: 고유 ID
- `timestamp`: 상태 기록 시점
- `kill_switch_status`: Kill switch 상태 (active, inactive)
- `kill_switch_reason`: Kill switch 활성화 사유 (nullable)
- `portfolio_value`: 포트폴리오 가치
- `current_mdd`: 현재 MDD
- `active_positions`: 현재 보유 종목 수

### 7.7 파라미터 변경 이력 (parameter_history)
- `change_id`: 고유 ID
- `changed_at`: 변경 시점
- `changed_by`: 변경자
- `parameter_name`: 파라미터 이름
- `old_value`: 이전 값
- `new_value`: 새 값
- `change_reason`: 변경 사유

## 8. 제약사항 및 경고

### 8.1 실거래 금지
- Phase 0에서는 실거래 API를 사용할 수 없습니다.
- 실거래 API 엔드포인트에 대한 접근은 코드 레벨 또는 설정 레벨에서 차단되어야 합니다.

### 8.2 수익 보장 표현 금지
- 모든 문서, 코드 주석, 로그 메시지, 사용자 인터페이스에서 수익 보장 관련 표현을 사용하지 않습니다.
- 예: "수익을 보장합니다", "이익을 납니다", "돈을 벌 수 있습니다" 등

### 8.3 운영 안전장치
- Phase 0에서는 기본적인 Kill switch만 구현합니다.
- 고급 운영 안전장치(상세 로깅, 알림 시스템, 롤백 메커니즘, 재시작 Runbook)는 Phase 1 이후에 구현됩니다.
- **운영 안전장치가 완성되기 전까지는 실거래를 진행할 수 없습니다.**

## 9. 다음 단계 (Phase 1 예고)

Phase 0 완료 후 Phase 1에서는 다음을 진행할 예정입니다:
- 운영 안전장치 고도화 (로그/알림/롤백/재시작 Runbook)
- 소액 실거래 환경 준비
- 파라미터 튜닝 도구 (선택적)
- 고급 리스크 관리 기능

---

**문서 버전**: 1.0  
**최종 수정일**: Phase 0 시작일  
**담당자**: Cursor Agent

