# EraLeader 다음 개발 실행계획 — 검증 우선 MVP

> 기준 2026-10-10. 새 대화에서 가장 먼저 개발할 작업. **일정·완료율 추정은 기록하지 않음**. 각 단계는 실제 코드·테스트로만 통과.

## 구체 실행 목표: 첫 PIT 데이터/모멘텀 파이프라인

**작업 패키지 P1/2_1/2_3/5_1**, 기존 코드 직접 재작성 없이 재사용부터 확인.

| 순서 | 작업 ID | 실제 개발할 것 | 검증/완료 기준 |
|---|---|---|---|
| 1 | P1 | `src/eraleader`, `tests/`, `pyproject.toml`, CLI, 독립 환경, 상태 기록 | 설치·import·pytest smoke 실행 |
| 2 | 1_1/1_5 | `legacy_marcap_adapter`: 1995~2026 Parquet **read-only** 로드, 원본 캐시 여부 확인 | 005930 / 2025-01-02~01-31 18거래일, 중복 조회 동일 |
| 3 | 2_1/2_4 | 내부 `security_id`, `session_date`, `OHLCV`, `source`, `quality_flags`, `data_hash` 정규화 | 원자료 행수/금액/시점 검증, 중복키 0 |
| 4 | 2_3 | `first_available_at` 기반 point-in-time 재무 샘플(테스트 fixture부터) | t 이후 공시 입력 뒤에도 과거 PIT 결과 불변 |
| 5 | 2_2/2_5 | 종목/상폐/기업행동 누락 시 상태 보류 및 품질보고 | 가짜 '완전검증' 경고·누수 회귀 테스트 |
| 6 | 5_1 | 기존 섹터 모멘텀 26주/Top2/4주 리밸런싱 비교 계약/스모크 | 재현 CSV 및 테스트 통과, 성과 공식 인정은 보류 |
| 7 | 기록 | `PROJECT_STATE.md` 상태 갱신, Git/실행 명령·데이터 범위 요약 | 다음 새 대화에서도 같은 실행 가능 |

### 신규 개발 시 경고

- 기존 `CycleOS-Lab_BacktestEngine` 원본 **수정/복제 금지**. `backtestengine`은 조사 시 빈 폴더였다.
- 실제 미국 과거 시점 S&P500 구성 변화를 반영하기 전, 기존 2026-03 기반 NASDAQ100/S&P500 자료를 '생존편향 없는 과거 전체'로 간주하지 않음.
- 과거 marcap 종가 보정, 분할·배당, 종목코드 변경/상폐 완전성 미검증. 초반에는 **데이터 검증용**으로 사용.
- PIT 기업실적은 DART/SEC 접수시각 자료 없으면 별도 **fixture**로만 테스트. 실데이터 PIT 성능을 주장하지 않음.
- Python 배치는 반복 계산·백테스트를 자동 처리하고, AI는 코드 개선/실패 분석. 자세한 오류로그 대신 실패 요약을 남긴다.

### 재사용 가능한 이미 존재하는 최소 코드와 결과

- `scripts/verify_backtestengine_reuse.py` → `results/reuse_probe/local_assets_audit.json`.
- `scripts/read_cached_marcap.py` → `results/reuse_probe/marcap_sample_query.json`.
- `results/reuse_probe/sector_mom_baseline_one_config.csv`: 기존 모멘텀 계산 실행 결과.
- `docs/23_BACKTESTENGINE_LOCAL_REUSE.md`: 실제 점검 기록 및 제한사항.

### 종료 보고 템플릿

```text
EraLeader 작업: [1_1 / 2_3 / 5_1 ...]
수정한 파일:
실제 실행 명령:
테스트: 전체 / PASS / FAIL / 미실행
백테스트: 실험 ID / 데이터 기간·종목수 / 결과 / PIT 유효성
남은 문제:
다음 작업(하나):
Git 상태/커밋(있다면):
```

### 새 세션에 바로 보낼 한 줄

> T5DATA SSD의 EraLeader 개발을 이어서 진행해 주세요. START_HERE_NEXT_CHAT.md와 AGENTS.md, PROJECT_STATE.md를 읽고 25_NEXT_IMPLEMENTATION_SPRINT.md의 첫 미완료 작업부터 기존 코드를 보존하며 구현하고 실제 테스트까지 완료한 후 상태 파일을 갱신해 주세요. 기존 CycleOS-Lab_BacktestEngine은 읽기 전용으로 재사용하세요.
