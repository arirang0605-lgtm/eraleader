# EraLeader 2_2·2_5 → 4_4·4_5·5_5 — 두 개의 first-SHA 고정 공급자 빈티지와 실제 WATCH 약화/교체 연구의 PIT 연결

2026-10-12 KST. 문서 127·128의 KR/US **각각 독립적으로 최초 발행한 A/B 쌍**과 문서 129의 기존 후보 WATCH 게이트, 기존 prospective.sqlite 관찰 이력 및 문서 70의 `watch_rotation.py`를 **읽기 전용으로 조합**한다. 실거래/공인 대장주 신호가 아니며 새 백테스트·기존 WATCH/점수/알림/first-native 코드 재작성 없이 한 단계 기능을 추가한다.

## 1. 기능과 데이터 계약

- 새 `src/eraleader/provider_pair_vintage_watch.py` 및 독립 `scripts/audit_pair_vintage_watch.py`. 옛 쌍의 **최초 독립 보관 SHA/비공개 0700 원본 경로/당시 WATCH `joined_*.json`**, 새 쌍의 별도 첫 SHA/비공개 원본 경로/새 WATCH 원본, **원래 하나의 `prospective.sqlite` 연구용 관찰 원장**과 시장·실제 현재 감사시간이 모두 필요하다.
- docs/128·129 재사용: 각 original raw A/B 전체, 원래 first PIN receipt, source bundle hash, SQLite 첫 등록·문서 witness, 최초 4도메인 및 요청 as-of 시점별 동일성과 활성 기업을 읽기 전용으로 검증. 최초 서로 다른 pair SHA/폴더와 전향적 등록시각 `old_first_ingest < new_first_ingest`, `old_decision < new_decision <= audit_cutoff`가 필요하다.
- 기존 `offline-integrated`가 만든 연구 run JSON에서 최초 paired receipt SHA, 정상 `provider_candidate_gate`, 실제 20자 `run_id`를 기존 original run hash + original provider pair digest + 최초 SHA로 **재계산**, 작성된 회사 WATCH는 연구용만 허용. `ProspectiveRegistry.research_screen_observations`의 동일 시장/모델/run_id/as-of에 저장된 **원래 canonical payload 및 SHA256**와 1:1 비교한다. 누락·중복·데이터 위조/미래 등록을 WATCH 근거로 사용할 수 없다.
- 대장주 후보 약화는 반드시 **같은 영구 security_id에 대해 앞 빈티지의 명시적 스크린 양성 1회와 뒤 빈티지의 명시적 음성 1회**가 실제 등록되어야 **`explicit_one_screen_weakening_only`** 1건으로 계산한다. 반대는 `explicit_one_screen_emerging_only` 1건. 두 결과만으로 교체 확정/매매/정책상 손절이 아니다.
- **반드시 원래 WATCH 등록시간이 다음 공급자 쌍 첫 수입시각보다 이르고**, 새 WATCH 등록은 새 쌍 최초 수입 이후여야 한다. 그렇지 않으면 과거 스크린을 새 원천 확보 이후 재연한 백필로 보고 **`paired_old_screens_registered_after_new_vintage_censored`**에만 집계, 조기 약화로 인정하지 않는다. 거래소 현지 3일 초과 등록지연도 제외한다.
- 소스의 명시적 상장폐지/합병·유효 회원 기간 종료, 새 공급자에서 종목/재무 기간 누락, 종목 업종 변경, 명시적 비교 스크린 결측은 **음성 스크린이라고 추측하지 않고** 결측·중단·재분류 집계로 분리한다. 동일 과거 회계기간 실적/산업 수치, 기존 분할·배당 경제조건 및 선언된 기업 동일성/상장 유효구간이 다른 경우 `source_delta_counts`의 **fundamentals / industry / actions / membership**별 신규·유실·정정 건수로 분리하고 이전 positive를 소급 변경하지 않는다. 최초 시점의 원장·민감 원문을 수정/복원/재발행하지 않는다.
- 이미 구현된 `audit_watch_rotation`으로 두 양성 뒤 두 명시적 음성/신규 같은 업종 두 양성 등 기존 2+2 보수적 가설을 새로 만들지 않고 가져온다. **이번 이전+이후 두 최초 쌍에서 각각 명시적 약화/부상한 동일 ID와 실제 마지막 등록시각이 일치할 때만** `pair_linked_existing_rotation_hypotheses`의 연구 개수를 집계한다. 1000개 표본 상한 초과이면 불완전 결과를 0건처럼 주장하지 않고 `null` 및 truncated로 반환.
- 공개 요약에는 개별 법인/종목 코드, 원문 저장 경로, 원시 공시·재무값, 인증키, 개인키, 원래 JSON/SQLite 본문을 포함하지 않는다. 핵심 시각·SHA·증거/결측/변동의 건수만 출력. **보고서 출력은 read-only 콘솔이며, 오프라인 URL/네트워크 요청·Git 업로드·실제 알림·주문 0**.

## 2. 실행

첫 SHA 두 개는 각각 docs/127 최초 발행시에 **별도로 보관했던 진짜 SHA**만 입력한다. 두 WATCH 파일은 각각 docs/129에서 생성된 원래 불변 `runs/joined_<market>_<run_id>.json`이며, `prospective.sqlite`는 두 실행이 실제 같은 원장에 기록된 것이어야 한다.

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/audit_pair_vintage_watch.py \
  --project /Volumes/T5DATA/eraleader \
  --market KR \
  --old-pair-root /PRIVATE/OLD/first_pair \
  --old-first-sha '<당시_첫_SHA>' \
  --new-pair-root /PRIVATE/NEW/first_pair \
  --new-first-sha '<나중_첫_SHA>' \
  --old-run /PRIVATE/DERIVED/runs/joined_kr_OLD.json \
  --new-run /PRIVATE/DERIVED/runs/joined_kr_NEW.json \
  --prospective-ledger /PRIVATE/DERIVED/prospective.sqlite \
  --evaluated-at '<실제_현재_시각_타임존포함>'
```

- 통과: stdout 연구용 익명 집계 JSON, 종료 0.
- 실패: stdout 비우고 원시 절대경로·종목/원본 재무값을 숨긴 오류 유형만 stderr 출력, 종료 2. 기존 원장 자동 복구·덮어쓰기/첫 PIN 재발행 없음.

## 3. 검증 및 경계

```bash
PYTHONPATH=src python3 -m pytest tests/test_provider_pair_vintage_watch.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests/test_provider_pair_vintage_watch.py tests/test_provider_pair_candidate_bridge.py tests/test_provider_pair_asof_seal.py tests/test_provider_pair_atomic_onboard.py tests/test_watch_progression.py tests/test_watch_rotation.py -q --tb=short
```

합성 KR/US 동일 영구 종목에 2024·2025년 연간 매출/영업이익·산업매출을 넣어 old **성장스크린 양성** → 실제 Mac에서 old 최초 WATCH 등록 → 다음 최초 source 쌍 수입+2025년 회계기간 매출값 correction → 새 WATCH 명시적 음성으로 바뀌는 전 과정을 기존 파이프라인으로 실행. 원래 WATCH/두 최초 영수증의 SHA/실행 시각 보존, 새 source 데이터 정정은 과거 원장 소급 변경 없음, API/메시지0. 실패 주입: 첫 SHA 위조, 시장 혼합, 역순 쌍, 미래 판정, run/원시 스트림 변조·삭제, prospective SQLite SHA 변경·행 삭제. 기존 2+2 회전 가설은 **실제 두 시점만으로 새로 생기지 않음**(정상 보수적 동작). 상세 시험 수·커밋 SHA는 PROJECT_STATE 최신.

**한계**: 첫 SHA/로컬 OS 시계는 독립 출처 인증·독립 타임스탬프 공증이 아니다. KRX/DART/SEC 원본 publisher/법적 영구 주권ID/share class·전수 상장·상폐 현금정산·처음 공개/수신시각 PIT, 첫 native Top-K의 실제 1~12개월 성숙 라벨은 **공식 API 연결 및 실제 시간 경과 후** 검증해야 한다. API 없는 로컬 연구 설계 진척과 대장주 발굴 성능/공인 PIT 인증을 혼동하지 않는다. 사용자의 결정에 따라 전체 pytest 회귀와 SSD 실물 탈착·재연결/재부팅, API는 최종 단계.
