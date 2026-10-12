# EraLeader 2_2 / 2_5 — KR·US 두 출처 PIT 자료의 원자적 오프라인 최초 수입

2026-10-12. **공식 KRX/DART/SEC API를 아직 연결하지 않고**, 이미 구축된 공급자 중간 파일 정규화(docs/80), provider first-ingest original SHA 첫 PIN(docs/85~86), immutable PIT SQLite 수입(docs/78), 두 출처 의미적 원장 교차감사(docs/81~82)를 **한 번에 실제 실행**하도록 새 수입 엔트리포인트를 구현했다. 정상 기존 코드를 재작성하지 않는다.

## 왜 이 기능이 필요한가

기존에는 A 수입 성공 → B 파일 누락·위조·회사 ID/현금행동 불일치 등으로 실패할 때 **한 공급자의 결과만 영구 등록**될 수 있었다. 사용자가 수동으로 rollback하면 최초 SHA·첫 시각 증거까지 삭제될 수 있다. 이제 **A/B 파일 모든 행 preflight → 임시 private 디렉터리에서 각각 정규화 → 현재 OS 시각 first-import → 각 원문/변환 SHA/doc ID 증거 PIN → 두 DB의 동일시점 full PIT 의미적 비교 → 양 원문 재검사 → 둘 다 성공할 때 하나의 완전한 폴더로만 발행**한다. 중간 실패 시 다른 한쪽을 성공 상태로 발행하지 않고 임시 폴더만 정리한다.

## 계약

- `src/eraleader/provider_pair_atomic_onboard.py`: `onboard_staged_provider_pair(staged_a,staged_b,target,clock=None)`. staged A/B는 **서로 다른 기존 절대경로**의 `manifest.json`, 시장은 한 호출에서 KR 또는 US 한 시장, claimed `source_id`/publisher ID는 달라야 한다. 정상 입력은 기존 공급자 독립 `eraleader.provider_staged_export.v1` JSONL 중간 형식이며 공식 API 원형이 아니다.
- `scripts/onboard_provider_pair.py`: 매 실행마다 실제 로컬 UTC를 최초 DB 등록시각 및 동일 research decision cutoff로 사용. 사용자가 소급 과거 임의 first-ingest 시각을 CLI로 입력하여 당시 PIT인 것처럼 만들 수 없다. 임시 디렉터리는 기존 owner-only `0700` private 부모에 생성한다. 원래 staged source 폴더와 publish 대상이 겹치거나 target이 이미 있으면 거절. 기존 파일 덮어쓰기·원시 자료 이동·원본 삭제 없음.
- 등록된 새 최종 루트는 `source_a/normalized/manifest.json`, `source_a/offline.sqlite`, `source_b/normalized/manifest.json`, `source_b/offline.sqlite`. 각 SQLite에는 기존 고유 첫 수입시각·`user_supplied` 표시와 처음 original staged SHA/doc-ID witness가 PIN되어 있다. 별도 코드·프로젝트 SQLite를 수정하지 않는다.
- `audit_provider_source_pair(...,require_original_pins=True)` 자체 조건을 그대로 적용한다. 멤버십/기업행동·분할/배당/공시자료/산업·두 출처 데이터 전부 일치하고 한 종목 이상의 당시 활성 회원이 있어야 `LOCAL_TWO_PROVIDER_ATOMIC_FIRST_INGEST_RESEARCH_ONLY`로 파생 결과를 발행한다. 서로 동일한 공급자 이름/관측값이라고 공식 출처 독립성을 입증한 것은 아니며 **후보 WATCH 승격은 별도 candidate gate**가 필요.
- 반환 JSON에는 claimed issuer/ticker/법인ID·원문 파일 경로·재무 수치 없이 시장·등록시각·정규화 SHA·두 출처 익명 일치 건수·미인증 한계만 포함. 원문 JSONL/SQLite/민감 raw 데이터는 **GitHub push 금지**, `target`을 Git 무시되는 owner-only 저장소(예: `output` 외부 사설 디렉터리, `.secrets` 등)에 지정. 실전 자동 거래/외부 메시지/API 호출 0, 공식 PIT·미래 대장주 예측력 인증 0.

## 예시

```bash
cd /Volumes/T5DATA/eraleader
# 외부 공급자 수집은 하지 않음. 소유자 전용 0700 저장 폴더를 먼저 준비.
python3 scripts/onboard_provider_pair.py \
  --project /Volumes/T5DATA/eraleader \
  --staged-a /PRIVATE_STAGED_A/manifest.json \
  --staged-b /PRIVATE_STAGED_B/manifest.json \
  --target /PRIVATE_NEW_PARENT_0700/kr_pair_first_import

# 미국 US도 별도 A/B 중간 소스로, 별도 target에서 동일 절차.
```

## 부분 시험 및 주의점

- `tests/test_provider_pair_atomic_onboard.py`: KR/US 두 시장 정상 first-ingest PIN + 실제 paired PIT asof 재감사, 최초 파일 SHA 불변, 중복/서로 같은 publisher·source/시장혼합/파일손상/미래 수집·공개시각, 분할비율·재무·업종·issuer 표기의 두 출처 모순, 목표가 이미 존재/링크/권한 0755/원문 폴더 겹침, B 수입 실패 후 A 잔여 DB 0, publish 직전 원본 bytes 변조 감지, subprocess CLI 공개 경로·키 노출 0. **집중 23/23 PASS**. 이전 정상 provider 관련 모듈의 영향 테스트도 변경범위 안에서 수행한다.
- **안전 경계**: Mac/SSD 같은 관리자·OS 시간으로 공급자 두 명칭 및 자료 모두 위조 가능, 첫 SHA PIN도 독립 타임스탬프 공증·KRX/DART/SEC 공식 issuer/class/상폐현금/기업행동·완전 역사 종목군/원문 첫 공개시각 인증은 아님. 같은 파일시스템 디렉터리 원자 발행은 별도 물리 백업이 아니다. 무선 API/SSD 물리 탈착·재연결/재부팅은 여전히 D-017/D-021 마지막.
- 사용자 최근 결정: **전체 pytest 회귀는 외부 API 연결 후에 실행**, 이번에는 신규 및 직접 영향받는 기존 테스트만. API 제외 로컬 코드 진행률 약99%(추정), 실제 미래 리더 적중률 N/A. 다음 작업은 공식 원천 API의 실제 필드·수집시각/장기간 prospective 검증 및 user offsite 경계 연결.
