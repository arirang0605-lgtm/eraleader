# EraLeader 2_2 / 2_5 — 최초 원자적 공급자 쌍 receipt SHA PIN + as-of 재감사

2026-10-12. 기존 docs/127의 **두 공급자 최초 오프라인 수입 및 2개 DB 동시 발행**을 보존하며, 수입 직후의 A/B 최초 조합이 이후에도 **원래 원문·정규화 자료·첫 SQLite 등록 시각과 동일한지** 검증하는 실제 읽기 전용 연결을 추가했습니다. KRX/DART/SEC 실제 HTTP API나 공식 issuer/share-class 인증은 수행하지 않습니다.

## 1. 변경된 최초 수입

- 기존 `src/eraleader/provider_pair_atomic_onboard.py`는 기존의 모든 입력/semantic 검증 통과 후, 단일 final rename 이전 private 임시폴더에 owner-only `0600` `first_pair_receipt.json`을 `O_EXCL` 생성합니다. 해당 receipt는 **원본 A/B staged manifest의 절대경로(비공개)**, 원본 manifest SHA, 1~4개 스트림별 원시 bytes SHA, 정규화된 두 provider manifest SHA, 정확한 최초 등록 UTC, 원래 최초 유효 회원/기업행동/재무/산업 일치 건수, local origin nonce, 공식 외부 PIT false만 포함합니다.
- 전체 원자적 수입 CLI 결과에는 민감한 파일 경로나 종목 ID 대신 **`first_pair_receipt_sha256`** 64자리 해시를 추가합니다. 이 첫 해시를 **원래 발행 시 사용자가 별도로 안전하게 보존**해야만 이후 감사를 할 수 있습니다. 같은 내부 저장소 파일만으로 최초 증거를 인증한다는 주장은 금지합니다.
- 원래 first PIN/수입 SQLite/소스 의미 검사·시장·KR/US ticker/class 스키마·시간·한쪽 실패 전체취소 정책은 그대로입니다. 기존 2폴더 `source_a/ source_b/`에 root receipt 파일 하나만 더 생기므로 그에 따른 테스트 기대값만 최소 조정했습니다.

## 2. 새로운 as-of 재감사

- 신규 `src/eraleader/provider_pair_asof_seal.py`: `audit_atomic_provider_pair_asof(pair_root,first_pair_receipt_sha256, decision_at, clock=None)`. 첫 영수증 SHA **필수**. 감사 대상 private 0700 root/0600 first receipt 소유자/링크/크기/정규 JSON/필드 고정 확인. receipt 위조·동일 사용자 소급 조작에 대해 원래 별도 보관한 SHA가 달라지면 즉시 차단합니다.
- A/B raw staged manifest·모든 stream 원문 해시를 기존 `_preflight`로 다시 계산, 원래 first receipt의 fixed SHA와 일치 확인. A/B normalized manifest SHA, 최초 SQLite import receipt와 원래 document-ID first source PIN을 기존 `audit_provider_source_pair(require_original_pins=True)`와 정확한 original_paths로 확인. **처음 수입된 판단시점**에 요구했던 원래 full membership/actions/fundamentals/industry 일치 건수도 다시 계산해 receipt에서 선언한 카운트와 대조합니다. 그 후 **요청한 as-of**에서 두 출처의 then-visible 멤버십/상폐/기업행동/재무/산업 전체 일치와 활성 기업을 재검사합니다.
- as-of가 **최초 로컬 등록 UTC보다 이르면** `BLOCKED_PINNED_PROVIDER_PAIR_RETROSPECTIVE_ASOF`; 과거 등록 SHA가 이미 있다고 최초 확보일을 당겨 인정할 수 없습니다. 기준일에는 양쪽이 의미상 일치해도 이후 상폐/유니버스 공백이 나타나면 `BLOCKED_PINNED_PROVIDER_PAIR_SOURCE_CONTRADICTION`, 실전 후보 승격0. 통과해도 상태는 `LOCAL_PINNED_TWO_PROVIDER_ASOF_CONCORDANT_RESEARCH_ONLY`, `eligible_for_local_candidate_watch_research_only=true`일 뿐 공식 투자 신호나 미래 대장주 확정이 아닙니다.
- 새 CLI `scripts/audit_provider_pair_asof.py`는 별도 receipt SHA·보관 루트·as-of 시각을 필수 요구하며 **원본 데이터/SQLite/첫 SHA 영수증 쓰기·API·메시지·주문0**. 완료 보고 JSON에는 두 공급자의 normalized SHA와 익명 count/에러 코드만; 법인/주식 코드·수집 원본 절대 경로/파일 본문 노출0. 오류 시 exit2, 성공 exit0.
- 남은 한계: 최초 SHA 보존 시점에 대한 외부 공증 없음, 같은 로컬 관리자가 최초부터 양 공급자와 로컬 clock을 위조할 가능성 있음. SHA 일치는 출처 발행자 신분 및 KRX/DART/SEC 최초 공개시각의 독립적인 증명이 아닙니다. 공식 PIT/survivorship/delist cash, historic universe/full price action 인증과 prospective 5_5 미래 Top-K 성숙 성과는 D-017 API 연결 및 자연 시간 경과 뒤.

## 3. 사용 예

```bash
cd /Volumes/T5DATA/eraleader

# 먼저 docs/127에서 서로 다른 ORIGINAL A/B 중간 수집 source를 1회 수입:
python3 scripts/onboard_provider_pair.py \
  --project /Volumes/T5DATA/eraleader \
  --staged-a /private/provider_A/manifest.json \
  --staged-b /private/provider_B/manifest.json \
  --target /private/owner0700_new_pair_dir

# 응답의 first_pair_receipt_sha256을 별도의 안전한 장소에 보존.
# 이후 특정 판단시점의 당시 공개·최초 로컬 등록·두 원본 일치를 읽기 전용 재감사:
python3 scripts/audit_provider_pair_asof.py \
  --project /Volumes/T5DATA/eraleader \
  --pair-root /private/owner0700_new_pair_dir \
  --first-pair-sha256 <실제로_보존한_64자리_SHA256> \
  --as-of '2026-10-12T15:00:00+09:00'
```

## 4. 테스트/후속

- 신규 `tests/test_provider_pair_asof_seal.py`, 최소 수정 `tests/test_provider_pair_atomic_onboard.py`: KR/US 정상 출처에서 original SHA/DB 첫 PIN·동결 카운트 재검증, 최초 수입 이후 as-of 및 소급 과거 판단 거부, receipt 삭제·symlink/0600 권한/바이트 변조/새 SHA/원시 source 재해시, normalized manifest/SQLite payload 조작, 양쪽 교차 시차·미래 as-of, 첫시점 정상 후 미래 상장종목 만료, 실제 Mac CLI 에러 경로 비노출. 초기 테스트에서 새 영수증 생성의 기본 권한이 0644인 것을 발견하고 **명시적 O_EXCL mode0600**으로 수정 후 집중 **46/46 GREEN**.
- 후속 기존 직접 영향범위(원본 provider normalizer/first ingest/semantic pair)만 테스트. **전체 pytest 회귀는 사용자의 명시적 요청에 따라 공식 API 연결 후**; 테스트되지 않은 타 모듈을 전체 통과했다고 주장하지 않음.
- D-017 KRX/DART/SEC 실제 provider schema/API·원본 자료/독립 최초 published+received timestamp, issuer/class·상폐 현금·기업행동/역사 전수 universe, 5_5 미래 대장주 실제 첫 WATCH/Top-K outcome은 미인증. D-021 SSD 물리 탈착/재부팅 최종. 기존 정상 first-native SHA/시장·MarketOS/CycleOS 코드 REWRITE 금지, 미커밋 `native_first_capture.py` 7줄 별도 보존.
