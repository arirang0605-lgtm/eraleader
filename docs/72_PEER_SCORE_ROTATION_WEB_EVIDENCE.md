# EraLeader 4_5 / 6_2 — WATCH 교체 후보의 전향적 점수 근거 웹 화면

> 2026-10-11. 로컬 PIT 미인증 연구 결과를 **브라우저에서 검토 가능하도록** 제공하는 기능입니다. 이는 실제 시대 대장주 확정이나 예측력 인증, 실매매 권고가 아닙니다. 외부 API 0회.

## 기존 모듈을 보존하면서 연결한 부분

- 기존 `src/eraleader/peer_score_series.py`의 `audit_peer_score_advantage`가 WATCH 교체 연구 가설과 각 원래 WATCH/점수/특성 파일을 read-only로 교차검증한다. 기능 정상 계약, 기존 `rank_score_events` 최초 점수 불변 로직, `ProspectiveRegistry`, 기업행동·동결 홀드아웃은 **재작성하지 않음**.
- 기존 결과에는 두 관찰일의 `contender - incumbent` 점수차·해시만 있었다. 파생 감사 JSON의 `hypothesis_sample[]`에 **`last_two_paired_scores`**(시장 현지 `market_day`, `incumbent_score`, `contender_score`)를 추가하여 점수차가 실제 두 종목의 점수와 수학적으로 일치하는지 UI에서도 검증할 수 있게 했다. 원문 feature JSON을 웹에 넣지 않는다.
- 기존 `src/eraleader/delivery.py`에 `render_peer_score_rotation_dashboard` / `write_peer_score_rotation_dashboard` 추가. `src/eraleader/cli.py`의 기존 `audit-peer-score-rotation` 명령은 JSON + `site/peer_score_rotation_{kr,us}.html`를 함께 작성하고 반환 메시지에 `dashboard` 경로를 추가한다. 다른 기존 CLI 기본 옵션은 유지.
- 모바일 브라우저에서 기존 정적 서빙 기능을 통해 시장/모델/기준시각, 전체 WATCH 교체 *연구 가설*, 최근 2회 점수 우위가 관측된 연구 가설, 점수 근거 미충족 수, 각 후보의 기존/신규 영구 종목ID, 업종, 두 현지 관찰일·각 점수·차이, 두 점수 이벤트 SHA256(앞 12글자 + 전체 SHA HTML title)와 차단 사유를 표시. 공식 교체·확정 대장주 0건/PIT 미인증을 화면 상단에 고정.

## 렌더 전에 막는 잘못된 연구 주장

- market/연구 status/source WATCH status 확인. `official_leader_replacements=0`, `issuer_industry_pit_certified=false`, `rank_scores_independently_authenticated=false`, `real_leader_replacement_certified=false`가 아닌 결과는 렌더 실패.
- 전체 가설 = 2회 점수 연속우위 가설 + 근거 미충족 가설; 사건 수·기록 가능한 점수 수 합계 불일치, sample > 총수, 등록되지 않은 이벤트·누락된 SHA 증거 차단.
- `last_two_paired_market_days`는 정렬된 서로 다른 ISO 시장일이어야 한다. 각 점수 0~100 유한 수치, 파생 점수차가 `round(신규 - 기존, 6)`과 일치, SHA256는 소문자 64자리로 검증. 가설 `locally_score_correlated=true`라면 최근 2회가 반드시 각각 고정 초기 가설 기준 **5점 이상**이고 `issues=[]`여야 한다. 점수 미충족이면 원인 코드를 함께 표시하며 성공으로 승격하지 않는다.
- 업종·기업ID·모델·문자열 문제 코드는 모두 HTML escape 적용. `<img onerror>` 문자열/가짜 official status·위조된 증빙/숫자 및 시장일 순서 회귀에서 실패를 확인. 후보가 아예 없을 때는 실제 실패 건수를 만들어내지 않고 **N/A / 미검증**을 표시.
- 표시 이벤트 샘플 200개 제한. 이는 전체 입력 종목군 수익률이나 실제 발견 성공률을 뜻하지 않는다.

## 직접 재현

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader audit-peer-score-rotation \
  --watch-ledger output/peer_score_dashboard_trial_20261011/prospective.sqlite \
  --score-history output/peer_score_dashboard_trial_20261011/peer_scores.sqlite \
  --feature-root output/peer_score_dashboard_trial_20261011/feature_source \
  --market KR --model-version synthetic-screen-v1 \
  --evaluated-at '2026-10-06T10:00:00+09:00' \
  --out output/peer_score_dashboard_trial_20261011/derived

# 출력은 파생 JSON과 정적 HTML 두 파일
# output/peer_score_dashboard_trial_20261011/derived/site/peer_score_rotation_kr.html

PYTHONPATH=src python3 -m pytest tests/test_peer_score_dashboard.py \
  tests/test_peer_score_series.py tests/test_watch_rotation.py -q
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

웹 HTTP 검증은 임시 `127.0.0.1` 서버에서 완료 후 서버를 종료하므로 항상 켜 둔 운영 서비스로 착각하지 않는다. `src/eraleader/local_backup.py` 기존 allowlist를 그대로 사용하며 **파생 JSON + site HTML 2개만** SHA256 ZIP으로 로컬 저장 및 새 경로 복원 가능하다. 원래 `peer_scores.sqlite`, `prospective.sqlite`, 임의 feature 문서/상용 시세/개인키는 이 파생 ZIP에 담지 않는다.

## 실증 여부와 다음 작업

2026-10-03/04 synthetic KR WATCH `INC/NEW` 사례의 점수 경로 기존 **40→38**, 신규 **65→72**, 차이 **+25/+34점**은 코드·화면·SHA 연결 확인용 합성 값이지 실제 미래 유망주·과거 실전 발굴 결과가 아니다. 다음은 독립 원천 PIT/법적 issuer/업종/기업행동·상폐·공시 및 5_3/5_5 사전 동결 후보의 실제 만기 outcome 수집/정밀도·리드타임 검증이다. 외부 API 연결은 D-017 로컬 구현 완료 후, SSD 물리 재연결·맥북 재부팅은 D-021 API 후 최종 검수에만 실시한다.
