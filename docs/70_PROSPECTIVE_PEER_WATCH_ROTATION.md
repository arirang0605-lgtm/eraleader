# EraLeader 4_4·4_5 — 동종업계 WATCH 약화·교체 후보 연구 감사

> 2026-10-11. **실제 대장주 확정·매수 신호가 아니라 전향적 연구 원장의 WATCH 변화로 만든 교체 가설입니다.** 실제 법적 기업/산업 PIT, 공식 수급, 실적·주봉 추세 확인, 미래 성숙 결과 라벨은 미인증입니다. API/스크래핑 0건.

## 기존 코드와 차이

기존 `watch_progression.py`는 **한 종목**의 `INITIAL_WATCH`, `WATCH_PERSISTED`, `SCREEN_WEAKENED`, `SCREEN_REENTERED`를 별도로 기록합니다. 이 결과만으로는 같은 산업의 기존 유망 WATCH 종목이 약해지는 사이 다른 기업이 새롭게 부상하는 **상대적 교체 가설**을 검증할 수 없었습니다.

새 `src/eraleader/watch_rotation.py`는 기존 `ProspectiveRegistry.research_screen_observations` SQLite를 **read-only**로 읽고 원본 canonical JSON/SHA256/시장/모델/종목ID/스크린 결과/등록시각을 대조합니다. 원장 이력은 추가하거나 바꾸지 않습니다. 미래 leader label·투자 손익·숫자형 사후 랭킹점수를 읽지 않습니다.

## 고정된 보수적 교체 조건 — 모델 성능으로 최적화하지 않은 임시 연구 가설

- 원장 `market=KR|US` 및 특정 `model_version`만 사용. 분석 cutoff `evaluated_at`은 실제/테스트 시계보다 미래일 수 없습니다. 후보는 cutoff 이전의 **실제 최초 저장시각**으로 판단하며, 관측일이 등록일보다 **현지 달력 3일 초과** 이전인 소급 스크린은 제외합니다.
- 반드시 당시 원본 `company.industry_id`가 두 기업 모두에 명시되어야 합니다. 부문 누락/개별 종목의 산업 변경은 **동일 산업이라고 사후 추정하지 않고 대상 제외**합니다. 비교는 기업 영구 `security_id`로만, ticker 명칭으로 자동 결합하지 않습니다.
- 기존 WATCH 종목: **명시적 연속 양성 2회** 이후 **명시적 연속 음성 2회**. 과거 두 양성과 첫 음성 사이도 각각 30 시장 현지일 이내이며 실제 등록시각은 서로 달라야 합니다. 최종 명시적 값은 음성 상태여야 합니다. 중간 종목의 누락을 음성으로 취급하지 않습니다.
- 새 동종업계 WATCH 종목: 기존 종목이 **처음 명시적 약화된 이후 최초 양성**이 기록되어야 하고, **최소 2번의 서로 다른 등록시각**에 연속 양성이 기록되어야 합니다. 양성 시리즈 중간에 실제 음성으로 이탈했다면 교체가 확정된 듯 표시하지 않습니다.
- 기존 종목의 두 번째 명시적 음성과 새 후보의 두 번째 양성이 모두 cutoff 이전에 확인되어야 합니다. 첫 약화부터 신규 최신 양성까지 30 시장 현지일, 최신 양성부터 cutoff까지 30 시장 현지일을 초과하면 보류합니다. 임계값 **2회·3일·30일은 검증 전 가설**, 공식 대장주 판정값이나 최적 수익률 파라미터가 아닙니다.
- 읽기 전용 SQL 결과 최대 5만 건, 한 업종의 잠재 짝 비교 최대 10만 건, 표본 최대 1000개. 지나치게 큰 작업은 일부 임의 결과 대신 **명시적 오류**로 중단합니다.

## 반환/상태 경계

`RESEARCH_PEER_WATCH_ROTATION_NOT_CERTIFIED` 하에 `rotation_hypothesis_count`, 이전 WATCH `incumbent_security_id`, 새 `contender_security_id`, 자기선언 `industry_id`, 약화/재관심 실제 등록시각(UTC)을 반환합니다. **WATCH였던 기업을 진짜 업종 대장주라 주장하지 않습니다.** 아래 값은 항상 false 또는 0입니다.

- `official_leader_replacements=0`
- `historic_pit_certified=false`
- `industry_membership_pit_certified=false`
- `peer_universe_coverage_certified=false`
- `actual_prediction_accuracy_certified=false`
- 각 이벤트 `incumbent_is_certified_leader=false`, `contender_is_certified_leader=false`

후보 누락·전향기록 부재·산업 정보 부족은 가짜 교체 이벤트를 만들지 않습니다. 샘플 가설에서 분자만 좋아 보이더라도 **진짜 발견율·정밀도·false positive는 전향적 동결 후 성숙 라벨**로만 검증할 수 있습니다.

## CLI / 로컬 백업

~~~bash
cd /Volumes/T5DATA/eraleader

# 단일 EraLeader 진입점 (종목 등록 원장만 읽음)
PYTHONPATH=src python3 -m eraleader audit-watch-rotation \
  --ledger output/watch_rotation_trial_20261011/prospective.sqlite \
  --market KR --model-version synthetic-screen-v1 \
  --evaluated-at '2026-10-09T00:00:00Z' \
  --out output/watch_rotation_trial_20261011/derived

# 별도 독립 CLI (새 파일 O_EXCL, 기존 결과를 덮어쓰지 않음)
PYTHONPATH=src python3 -m eraleader.watch_rotation \
  --ledger output/watch_rotation_trial_20261011/prospective.sqlite \
  --market KR --model-version synthetic-screen-v1 \
  --evaluated-at '2026-10-09T00:00:00Z' \
  --out output/watch_rotation_trial_20261011/standalone/rotation.json

PYTHONPATH=src python3 -m pytest tests/test_watch_rotation.py tests/test_watch_progression.py -q
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

`watch_rotation_kr_research.json`, `watch_rotation_us_research.json` 두 **파생 요약 파일만** `local_backup.py` ZIP allowlist에 추가했습니다. 합성 입력 SQLite, 재무/가격/공시 원본, 미래 평가라벨/비밀키는 ZIP/Git 제외. 샘플 CLI는 실제 미래 후보가 과거에 존재했다는 증빙이 아닌 **시계 주입 합성 fixture**입니다.

## 해결하지 못한 사항

다음은 2_2/2_5 독립 PIT 기업 영구ID·역사 유니버스/산업분류·실적·기업행동/상폐 증거와 5_5 전향적 성숙 성과라벨/기준 고정 강건성 검증입니다. 따라서 이번 연구 교체 가설은 **어떤 경우에도 확정 대장주/매매 권고가 아닙니다**. D-017 외부 API는 로컬 개발 이후, D-021 물리 SSD 분리·재연결 및 Mac 재부팅 검증은 API 후 최종 단계에서만 수행합니다.

## 2026-10-11 추가 — 6_2 정적 업종 WATCH 교체 연구 화면

- 기존 `delivery.py`의 연구용 HTML 생성 방식을 재사용해 `render_watch_rotation_dashboard` / `write_watch_rotation_dashboard` 추가. `audit-watch-rotation` CLI 실행 시 JSON과 별도로 `site/watch_rotation_kr.html` 또는 `site/watch_rotation_us.html`을 생성. 휴대폰·PC 브라우저에서 기존 EraLeader 로컬 정적 서버로 볼 수 있는 **읽기 전용 연구 화면**이며 자동 매매/푸시 알림 없음.
- 화면에는 시장·모델·관찰 기준시각, research rotation hypothesis 건수, 실제 입력·소급 제외 건수, 기존 WATCH↔신규 WATCH의 산업ID·첫/두 번째 약화/신규 양성 기록 UTC를 표로 표시. **확정 대장주 0건**과 **독립 PIT 인증 없음 / 투자 추천 아님** 안내를 고정 표기.
- 렌더 전 `status`, 시장, 공식 교체 0, 4개 미인증 불변 flag, 데이터 건수와 샘플 event `kind`, 기존/신규 인증 false 여부를 검증하여 가짜 공식 확정 내용을 표시하지 않음. 종목·산업 문자열은 HTML escape 처리하여 악성 `<img onerror>` 삽입을 방지.
- 안전 백업 ZIP에는 `watch_rotation_{kr,us}_research.json` + `site/watch_rotation_{kr,us}.html` **파생 결과만 2개**; 원본 `prospective.sqlite`, 데이터 공급자 원본, 가격, 결과 라벨은 보관하지 않음. 신규 합성 테스트는 안전한 HTML, 악성 문자열 탈출, 허위 승격 flag/건수 불일치 차단, JSON+HTML ZIP SHA 및 복구를 포함.
