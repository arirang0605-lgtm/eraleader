# ER-NC-09 — 사전 봉인 NEWS OFF/ON·테마·시장게이트 홀드아웃 비교

작업일: 2026-10-13 KST. **연구용 봉인 비교 엔진 구현**; 공식 PIT 인증/미래 대장주 예측력·투자성능 인증은 **N/A**.

## 인수·분리

- ER-NC-B00 암호화 원본 2중 백업/독립 격리 복원 PASS. 본 작업은 `feature/er-nc-09-frozen-ablation-20261013` 독립 worktree, 기준 ER-NC-08 `d0dd1c137b1626a47c6055417afdabcf4304a465`.
- 기존 `main`의 `native_first_capture.py` 미커밋 수정 6추가1삭제 및 원래 ER-NC worktree의 미추적 `news_market_response.py`는 원본 SHA 보존. 기존 `backtest.py`, `frozen_holdout.py`, `walkforward.py`, `ProspectiveRegistry`, WATCH 점수/알림/대시보드, KRX/DART/SEC 실제 캐시 수정 **0**.
- 이전 `ER-NC-06/08` 기존 핵심 코드를 그대로 재사용; 기존 5_4/5_5의 `frozen_holdout._read_frozen`, `_publish_once`, `evaluate_frozen_candidates` 및 ER-NC-02 `market_regime_experiment.entry_permission`를 직접 사용. 새로운 성과 평가 계산기를 재작성하지 않음.

## 사전 선언 B0~B5 (매수·실전 주문 없는 연구)

| 팔 | 사전 봉인 가설 | 유효한 입력 | 해석 |
|---|---|---|---|
| B0 | `ORIGINAL_BASELINE_NO_NEWS` | 기존 실제 ProspectiveRegistry에서 이미 동결된 최초 후보 | 기준. 원래 WATCH 점수와 생성시각 변경 없음 |
| B1 | `NEWS_SIDECAR_ONLY_EXACT_BASELINE` | B0 + 당시 이용 가능한 뉴스 메타 | B0와 후보 신원·성과 반드시 **100% 동일**, 뉴스가 매매 규칙을 변경하지 않음 |
| B2 | `THEME_RISING_OR_REACTIVATING_PIT_FILTER_HYPOTHESIS` | B0 중 최초 신호 등록 전 **이미 알려진** 테마 RISING/REACTIVATING 증거 | 연구용 부분집합. 탈락 후보도 포함한 회수율/N 비교 필요 |
| B3 | `B2_AND_STRICT_UPTREND_NEW_ENTRY_HYPOTHESIS` | B2 중 PIT 시장 국면 `RISING`이고 기존 `entry_permission`이 신규진입 허용 | 원형 신호/손절·청산 규칙은 **변경하지 않음**. 통과 후보만 연구용 부분집합 |
| B4 | 저자 매매 원형 단독 | 남석관·유목민 N_ST/N_MT/Y_ST/Y_MT의 검증된 1차 원문 | 현재 `RULE_REVIEW_REQUIRED`·`NOT_READY`, 성과 수치 생성 금지 |
| B5 | 저자 원형+뉴스 필터 | B4 확인 및 독립 뉴스 계약·PIT | `NOT_READY`, 임의 승격 금지 |

## 절대 PIT / 독립 SHA / 홀드아웃 잠금

1. `freeze_news_ablations(original_holdout, context_json, new_target_dir, expected_context_sha256=...)`는 이전 `freeze_registered_candidates` 산출물의 SHA/label ID/horizon/first recorded date를 재검증. **미래 결과 라벨 파일 입력 자체가 없다.**
2. 정형 context schema `eraleader.er_nc09_context.v1`: `market, model_version, source_mode=LIVE_OBSERVED, items`. 각 `security_id`의 별도 `theme`/`regime`/`news`는 선택사항. 입력 전체 SHA256 외부 PIN 필수, 각 객체 형식/증거시각이 후보 **실제 첫 등록 시각 이하**여야 함. 뒤늦게 수집한 과거 뉴스/기업의 후일 테마 편입, 시장 국면 미래 확정, 티커를 원본 주권 ID로 둔갑시키는 정보는 차단.
3. 테마에는 원래 ER-NC-04 `source_sha256`, `episode_id`, `quality_status`와 멤버 최초 인지·시장관측 일자를 요구. 시장 국면은 기존 ER-NC-02 계약과 input cutoff/first received를 요구. 시차가 7일 넘는 context·사후 부여/정보 충돌은 fail-closed. 뉴스 그 자체는 신호를 변경하지 않음.
4. 동일 원본 후보집합 B0=B1, B3 ⊆ B2 ⊆ B0를 독립으로 봉인. 각 `B0_frozen.json`~`B3_frozen.json`은 `_publish_once` SHA self-witness; 선택된 보안 디렉터리는 기존 경로를 덮지 않고 새로운 원자적 게시로 생성. 별도의 `ablation_manifest.json`은 시나리오별 원본 SHA·정책·후보 목록·같은 사전 라벨 정의·만기를 SHA 연결. **원본 freeze/SQLite 쓰기 0**.
5. 사후 평가 `evaluate_news_ablations(sealed_dir, mature_labels, expected_manifest_sha256, evaluated_at)`는 사용자가 보관한 **외부 manifest SHA PIN**과 각 scenario SHA·선택 목록·최초 봉인시각을 다시 검사하고 기존 `evaluate_frozen_candidates`로 결과를 산출. 외부 라벨/이벤트는 기존 평가기 기준 **mature_at 및 outcome_available_at**이 평가시각 이후면 검열(censored), 만기 전 부정은 FP로 확정하지 않음. 봉인 전 성숙/인지된 결과가 있으면 거절. 봉인본 수정/늦은 라벨·컨텍스트/동일 종목 충돌 시 실패.
6. `clock` 주입 합성 테스트는 `simulation_clock_supplied=true` 및 `run_is_simulation=true`로 분리. 로컬 데이터가 원래 실제 운영시간에 공개됐다는 **독립 공급자 first received/first published 증빙은 아직 없음**. `source_pit_certified=false`, `real_prospective_accuracy_certified=false`, `statistical_improvement_claimed=false` 강제.

## 출력·점수 해석

- 봉인 manifest + 4개 variant freeze (결과 라벨/미래 기업 구분 내역 **0**).
- 최종 평가 arm별 신호 N/성숙 라벨 N/검열 N, 진짜 선행 TP/거짓 FP/고점 이후 LATE, known precision, FDR (known non-late), 보수적 precision floor, lead-time median, coverage.
- **precision@K = N/A**(원래 ProspectiveRegistry freeze에 독립 봉인된 rank@K 증거 없음), **recall = N/A**(공식 PIT 전체 시장 유니버스 미인증), **CAGR/MDD/거래비용/리스크 = N/A**(자동 체결/분할/배당/상폐/다음날 가격 모델 없음). B2/B3는 선택 부분집합이므로 표본 축소에 의한 precision 개선을 성능 개선의 통계적 증거로 주장하지 않음.
- 가상 데이터 `A/B/C/D`에 B0=4, B1=4, B2=2, B3=1의 연구 관측은 설계 검증일 뿐 투자 전략의 실제 성과가 아님.

## 재현 CLI — 절대로 PIN 없이 실행 금지

`PYTHONPATH=src python3 scripts/run_er_nc09_ablation.py freeze --original-frozen /abs/base_frozen.json --context-json /abs/asof_pit_context.json --expected-context-sha256 <외부 SHA> --new-output-dir /abs/new_sealed_dir`

`PYTHONPATH=src python3 scripts/run_er_nc09_ablation.py evaluate --sealed-dir /abs/new_sealed_dir --outcomes-json /abs/later_mature_outcomes.json --expected-manifest-sha256 <별도보관 최초 manifest SHA> --evaluated-at 2026-10-13T10:00:00+09:00 --new-report /abs/new_eval_report.json`

둘 다 네트워크/API·메시지·거래 호출 0. 기존 리포트·보관 디렉터리 덮어쓰기 불가. 실시간 데이터 연결 전에는 synthetic fixture만 사용.

## 검증 및 남은 작업

- `tests/test_news_ablation.py`, `tests/test_er_nc09_cli.py`: 기존 ProspectiveRegistry fixture → 원래 5_5 freeze → 뉴스·테마·시장 컨텍스트 → 4-arm SHA 봉인 → 성숙·미성숙 라벨 분리 평가; 미래 뉴스·issuer·member 최초등록·regime first received·시장 세션·NaN/중복 context/미성숙·SHA 위변조·가짜 backtest 성과 등을 방어.
- 기존 변경 영향 `test_frozen_holdout.py, test_discovery_metrics.py, test_walkforward.py, test_market_regime_experiment.py, test_theme_lifecycle.py, test_news_catalyst_adapter.py, test_news_rotation_context.py, test_news_market_response.py, test_news_theme_delivery.py`로 검증. **전체 수천 개 회귀는 ER-NC-10 최종 통합 수락 전 한 차례 실행.**
- 다음: ER-NC-10의 실제 허가된 뉴스 공급원 스냅샷·별도 first-received SHA 증빙·실제 5/20거래일 전향 관측, PIT 역사 유니버스·기업행동/상폐 교차 인증, ER-NC-07 네 저자 원형 공식 문헌 확인 및 독립 전략 실행 준비, 현재 뉴스 OFF 기존 원래 사이트/보고/점수 보존 통합 검사. 실전 성과 판단은 자연 라벨 만기 뒤.
