# EraLeader 6_2·6_5 — 기존 운영 화면 + 콜드 원본 복구 SHA 이력 읽기 전용 결선

2026-10-12 KST. **이미 검증된** `operations_overview.py`(가격/WATCH/Top-K), docs/122~125의 encrypted-only cold ZIP·first SHA PIN·첫 native AES 복구·기한 게이트를 재작성하지 않고 별도 모듈로 통합.

## 구현

- 신규 `src/eraleader/operations_cold_bridge.py`와 독립 CLI `scripts/render_local_cold_operations.py`. 사용자가 **원래** PIN-root·비공개 0700 scratch를 명시한 경우만 기존 cold restore gate의 최초 genesis/first event/append SHA history/최종 checkpoint를 원본 owner-only flock으로 **읽기만** 한다. 기존 가격·WATCH·Top-K 3개 예약 모드는 원래 `audit_local_operations` 및 `render_operations_overview` 그대로 재사용.
- 새 요약 상태: `NO_COLD_RESTORE_RECORD`(등록/감사 기록 없음), `COLD_OBSERVER_CORRUPTED`(기록·SHA 첫 봉인·권한 위조), `COLD_OBSERVATION_STALE`(마지막 검사 > 정책 max-gap 48h), `COLD_INCIDENT_PRESENT`(미복구·실패·만료·SHA 이상), `RESEARCH_ONLY_PREVIOUS_REPLAY`(연구용 colocated 마지막 PASS), `LOCAL_REPLAY_SHA_HISTORY_ONLY`(당시 로컬 strict SHA 증거 존재, 현재 실물 상태 증명 아님). 어떤 상태도 **실전 매수 가능·예측력 인증·공식 issuer PIT·진짜 offsite 공증**으로 승격하지 않는다.
- 마지막 기록 SHA head/건수·원래 policy 경로 SHA에 묶인 감사 체인을 검증, 기존 report에 추가된 `private_key_accessed=true`·`plaintext_decrypted=true`·`external_offsite_notarization_attested=true`·live notification 등 위험한 자기주장도 거부. 표시: 익명 상태별 백업 건수, 마지막 관찰 UTC, 경고 건수만. 사용자의 PIN 경로·개인키·원시 주식/기업 식별자/복호화 결과/원래 ZIP 내부 데이터는 파생 HTML/JSON에 포함하지 않는다.
- 첫 감사와 *동일 기준시각* 두 번째 SHA 감사 결과가 일치한 경우에만 원자적으로 `output/operations_cold/site/index.html` 및 `output/operations_cold/cold_operations_research.json` 2파일을 발행한다. 이는 기존 `output/operations`, `output/site` 및 6_5 PIN/vault/원래 원장/LaunchAgent 파일을 **덮어쓰지 않는다**. 새 프로그램에 개인키 인자 자체가 없고 외부 API/라이브 알림/주문 기능 없음.

## 실행

기존 cold first PIN 저장소와 원래 복구 리허설 `scratch`가 존재해야 한다. 운영 strict 조건에서는 원본 SSD/콜드 ZIP/PIN 별도 파일시스템 정책을 그대로 적용하며, `--allow-colocated-research-only`는 오프라인 합성 시험 전용이다.

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/render_local_cold_operations.py \
  --project /Volumes/T5DATA/eraleader \
  --pin-root /Mac_original_0700_pin_root \
  --scratch-root /Mac_original_0700_replay_scratch
# 브라우저: output/operations_cold/site/index.html (파일 열람 또는 기존 로컬 serve 사용)
```

## 검증·한계

- 신규 `tests/test_operations_cold_bridge.py`: 원래 3모드와 결합, 정상 evidence·기록 미존재, 위험/만기·손상·future-clock·이력과 report 위조·자동 live claim 주입·변경 시 재감사 차단·개인키/경로 비노출·기존 파생 보고서/first SHA 불변, 로컬 HTTP200. 실제 수행 집중 결과와 새 SHA는 PROJECT_STATE 최신 기록을 참조.
- **SHA 이력 읽기만 수행**하므로 어제의 인증 리허설이 지금도 복호화 가능한지, 원래 외부 저장장치가 재연결 가능한지, 3번째 실제 독립 드라이브/지리적 오프사이트가 있다는 뜻이 아니다. 이 화면에서는 `current_pin_ciphertext_reverified=false`, `aes_gcm_replayed_now=false`, `official_market_pit_certified=false`를 고정 유지한다.
- D-017 공식 KRX/DART/SEC PIT 및 앞으로의 전향적 미래 Top-K 자연만기 결과, D-021 실물 SSD 탈착/재부팅은 사용자 요청대로 최종 단계. **전체 pytest 회귀는 API 연결 후**, 이번 단계는 변경 테스트만 실행. 기존 `native_first_capture.py` 미커밋 7줄 보존.
