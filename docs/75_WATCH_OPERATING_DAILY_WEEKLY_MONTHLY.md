# EraLeader 6_4 / 6_5 — 전향 WATCH 일·주·월 운영 연구 보고서

> 2026-10-11. **오프라인 실제 WATCH 원장을 읽는 로컬 운영 기능**으로, 백테스트 승자·미래 결과를 만들어 채우지 않습니다. PIT·거래소 전체 종목군·성과 라벨·외부 거래소 발행시각은 여전히 독립 인증되지 않았으며 어떤 보고서도 매매 권고나 확정 대장주를 표시하지 않습니다. 스케줄 실행 및 외부 알림 발송은 설치하지 않습니다.

## 이전 기능과 남아 있던 실무 단절

기존 `batch.py`는 한국·미국 *가격 관찰* 스냅샷으로 일간/주간/월간 Markdown 보고서 6개를 만들고, `local_schedule.py`는 캐시 날짜·SHA/백업을 검증하지만 실제 후보 상태의 전이와 별도 `prospective.sqlite` 연구용 WATCH·동료 점수로 보고서를 연결하지 않았습니다.

신규 `src/eraleader/watch_operating_reports.py`는 기존 원장/점수/백테스트 구조를 재작성하지 않고 **별도 읽기 전용 운영 보고서**를 만듭니다. 누락된 과거 음성 스크린을 만들어 내거나 오래된 기록을 오늘 대장주로 선언하지 않습니다.

## 실제 개발 계약

- 명령 `report-watch-operations`: 사용자가 지정한 `--market KR|US --model-version ... --evaluated-at <timezone ISO>` 기준으로 기존 `prospective.sqlite`를 SQLite `mode=ro / PRAGMA query_only=ON`으로 열어 `research_screen_observations`의 실제 기록된 명시적 screen-hit TRUE/FALSE와 불변 `prospective_signals` 양성 기록을 대조.
- 기록일은 원본 `observed_as_of`가 아니라 **실제 등록 `recorded_at_utc`를 각 시장 현지 시간대로 바꾼 날짜**를 사용. `evaluated_at` 뒤의 이벤트는 제외. 역사 관측일에 비해 **현지 달력 3일 초과 소급 등록**은 전향 기록에서 제외. 매 시장/고정모델 단위로 원본 payload canonical JSON/SHA·영구 회사ID·시장·WATCH 상태·양음·source run ID/최초 양성 signal_id/원문 hash를 검사. 원본 최초 양성 signal이 남았는데 대응하는 관측행이 없으면 **불완전 원장**으로 명시적 오류.
- 관측 변화 6종: `INITIAL_WATCH`, `WATCH_PERSISTED`, `SCREEN_WEAKENED`, `SCREEN_STILL_WEAK`, `SCREEN_REENTERED`, `PRE_WATCH`. **한 종목의 이전 기간 명시적 상태를 먼저 처리**하므로 새 주 첫날 재양성은 잘못 `INITIAL_WATCH`로 세지 않음. 목록에서 기업이 빠졌다는 사실만으로 약화/상폐/실패를 유추하지 않음.
- WATCH 양성 기록·명시적 관찰 기록을 **하나의 SQLite 읽기 트랜잭션**으로 비교하고, 현재 평가시점 이전 관찰 원본 hash 목록·시장/모델/as-of/동료 점수 파생 증거를 묶은 20자리 **로컬 연구 run ID**를 계산합니다. 세 기간 JSON/HTML/Markdown이 같은 run ID를 공유하며, 이는 독립 인증서가 아닌 동일 연구 입력 버전 확인용입니다.
- 동일 `evaluated_at` 기준 **일간(현지 날짜), 주간(월요일~해당일), 월간(1일~해당일)** 집계. UTC와 한국·미국 현지 날짜 차이/DST를 고려하며 기간 내 명시적 관측건수·커버된 기업 수(전체 시장 종목군과 구분)·source-run 수·6가지 전이별 개수 및 관측 시각을 표시. 표본은 최대 200건, 표본 잘림 플래그를 남겨 총수 집계와 혼동하지 않음.
- 마지막 명시 양성의 전체 건수와 **최근 7 현지 달력일 이내 마지막 양성**을 별도로 표시. 과거 자료만 남아 있으면 `STALE_RESEARCH_OBSERVATIONS_NOT_CURRENT`, 전향 관찰이 없으면 `NO_PROSPECTIVE_OBSERVATIONS`로 표시. **신선도 보류는 자동 음성/실패가 아니다.**
- 선택 `--score-history <peer_scores.sqlite> --feature-root <historic_feature_dir>`를 **함께** 제공하면 기존 `audit_peer_score_advantage`를 그대로 재검증해 같은 시장/모델/as-of 연구교체 가설/2개 관찰일 점수 상관 건수를 요약. 미제출이면 `NOT_REQUESTED`, 가설·우위 숫자 `null` (허위 0건 아님). 원천 변조·정합성 불일치는 보고서 발행 전에 예외.
- 오프라인 보고서에는 `official_leader_promotions=0`, `actual_future_precision=null`, `future_accuracy_certified=false`, `market_universe_coverage_certified=false`, `pit_certified=false`, `live_notifications_sent=0` 고정. 시장 조정수익률·실전 조기발견 정확도를 계산하거나 주장하지 않음.
- 공급자 원시 feature/유료 가격/미래 outcome labels, API 키, 전체 payload를 보고서/공개 Git에 넣지 않음. 종목 문자열·모델 ID는 Markdown control/newline 및 HTML injection escape. PDF/외부 이메일 발송은 이 기능의 범위가 아님.

## 출력 및 재현

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader report-watch-operations \
  --watch-ledger output/research/prospective.sqlite \
  --market KR --model-version local-screen-v1 \
  --evaluated-at '2026-10-11T09:00:00+09:00' \
  --out output/research/watch_operating

# 원천 점수 증거까지 있다면 --score-history, --feature-root 동시 제공
# report-watch-operations --score-history ... --feature-root ...
~~~

산출:
- `watch_operating_kr_research.json`: 하나의 연구 실행에서 생성된 세 기간의 공통 소스/품질 집계 및 연구용 관찰 샘플.
- `reports/watch_daily_kr.md`, `watch_weekly_kr.md`, `watch_monthly_kr.md`: 기존 가격 전용 보고서와 **별도** 후보 관찰·약화·재진입 요약. US는 `_us`.
- `site/watch_daily_kr.html`, `watch_weekly_kr.html`, `watch_monthly_kr.html`: 모바일/PC 로컬 브라우저 정적 확인. HTTPS/인증이 없는 로컬 연구용 UI로, 외부 웹 공개 금지.

각 결과 파일은 새 임시파일 작성/동기화 뒤 atomic replace; 공통 JSON 연구 manifest를 **마지막에** 발행합니다. 기존 `local_backup.py`는 신규 `watch_operating_{kr,us}_research.json`만 JSON allowlist에 추가하고 기존 안전한 `reports/*.md` / `site/*.html` 백업을 재사용. 실제 원장 SQLite 및 입력 원문은 파생 보고 ZIP에 포함되지 않습니다.

## 검증

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_watch_operating_reports.py \
  tests/test_watch_progression.py tests/test_local_backup.py \
  tests/test_peer_score_series.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

synthetic KR 최초→지속→명시약화→재진입, US DST/월말 변환, prior-week 상태 승계, 관측보다 늦은 등록일만 집계, 과거 소급 제외, 부재시 자동 약화 0, 수개월 전 양성 캐시 신선도 경고, 해시를 다시 맞춘 영구ID 변조/양성 signal 사라짐 차단, 미래 cutoff 사용금지, XSS, 실제 CLI/7개 파생파일 ZIP SHA/복원 및 로컬 HTTP GET 200 회귀 포함. **테스트 통과 수와 Git SHA는 `PROJECT_STATE.md` 최종 기록 우선.**

## 의도적인 미완료

1. 여기서 집계하는 WATCH는 로컬 연구용 신호로, 실시간 1_1~1_5 외부 데이터를 확보하지 않은 상태에서 거래소 현재 수급/실적/시가총액을 주장하지 않음.
2. 공시 독립 시점/PIT·기업행동/상폐 금액·역사 전체 유니버스·실전 사전 봉인/성숙 결과를 아직 인증하지 못했으므로 **확정 대장주·투자 전략 성과/진짜 precision/recall N/A**.
3. 실제 macOS `launchd`와 자동 알림 전송·외부 API는 이번 개발에서 설치/연결하지 않음. 다음 6_5 단계에서 검증된 보고서만 자동 운영에 선택 통합하고 채널 자격증명/데이터 신선도·동일 run 기준을 검증할 수 있음. D-017 API 연결은 전체 로컬 개발 이후, D-021 물리 SSD 재연결/재부팅은 API 이후 최종 단계.

## 2026-10-11 구현 직후 직접 로컬 검증

- `output/peer_score_dashboard_trial_20261011/prospective.sqlite`와 선택적인 `peer_scores.sqlite` / `feature_source`는 **이전 작업에서 생성한 100% 합성 fixture 데이터**입니다. 이번 새 정기 보고서의 기능 검증에만 재사용했으며 실제 거래소 발굴 데이터·실시간 투자 판단 근거가 아닙니다.
- 기존 CLI `report-watch-operations`를 시장 KR과 US 각각에 `--evaluated-at '2026-10-11T09:00:00+09:00'` 명시하여 실제 Mac에서 수행했습니다. KR은 기존 합성 두 후보의 자체선언 **2시장일 점수 우위 연구 1건**을 `peer_score_rotation`에 연결, US에 일치한 연구용 스크린이 없어 `NO_PROSPECTIVE_OBSERVATIONS`/미래 정밀도 `null` 처리. 어느 시장에서도 공식 대장주/실전 수익/알림은 0 인증.
- `output/watch_operating_trial_20261011/derived` 아래 한국·미국 공통 JSON 2개, 기간별 `reports/*.md` 6개, `site/*.html` 6개로 **파생파일 14개**를 실제 생성. 세 기간 파일은 같은 시장의 **공통 local research run ID**를 사용. 임시 localhost HTTP GET `watch_monthly_kr.html` **200**, 안전 ZIP `watch_operating_derived_only.zip` 14개 파일 SHA `LOCAL_BACKUP_VERIFIED`; 새 경로 `restored/`로 재생한 14개 파생 바이트 모두 동일. 원본 WATCH/점수 SQLite, 원시 시장 가격·공시·레이블·키는 파생 ZIP에 없음.
- 세 기간별 변화 상태/실제 등록일·원래 source-run 묶음은 동일 read-only 원장 snapshot에서 계산하며, 기존 가격 전용 `batch.py` 자동 배치를 대체하거나 예약실행을 설치하지 않습니다. 로컬 자동운영 연계는 추후 점수·WATCH 최초 등록 실시간 운영 데이터가 생긴 다음 보수적으로 opt-in해야 합니다.
