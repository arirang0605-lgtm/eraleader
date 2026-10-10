# EraLeader 개발 체크포인트 — 5_3 워크포워드 + 6단계 로컬 배치

> 날짜: 2026-10-10 KST. **로컬 실행 성공**. 사용자 원칙: API/스크래핑은 로컬 1~6단계 기능 완성 이후 연결. 최종 목표는 미래 대장주 조기 발굴이다.

## 개발 완료 범위 (완전한 서비스 완성으로 착각 금지)

- `src/eraleader/walkforward.py`: 5_3 연구용 시간 순서 분리. 시점별 피처 최초 이용가능시각을 신호시각 이전으로 강제, 학습 라벨은 훈련 종료 전에 실제 이용 가능했던 라벨만 사용. 테스트기간에는 정답을 노출하지 않음. embargo 일수 설정, 미성숙 라벨은 censored. **역사 종목군 PIT/정식 백테스트 성능 검증은 아님**.
- `src/eraleader/batch.py`: 6단계 로컬 원클릭 배치. **국가별 명시된 날짜**의 저장 가격만 이용해 한국/미국 20개 가격 관찰 목록, 해당 종목별 정적 웹 화면, 두 시장 각각 일·주·월 보고서 총 6개, 알림 dry-run을 하나의 CLI에서 실행. 같은 배치 반복 시 이벤트 중복 방지. 절대 외부 API/실제 알림 발송 없음.
- `src/eraleader/state_history.py`와 `src/eraleader/cli.py`: 기존 `offline-integrated` 로컬 연구 결과를 **상태 이력 SQLite에도 저장**. 현재 모두 WATCH(종합 PIT 미검증)이며 임의 승격하지 않는다.
- CLI에 `walkforward`, `batch` 추가, `tests/test_walkforward.py`/ `tests/test_batch.py` 추가.
- GitHub Public 저장소에 사용자 명시 승인하에 보안검사/pytest 통과본만 main push.

## 실제 운영 확인 명령

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests -q

# 역사적 마감 가격 기준 — 실시간 시세 아님
PYTHONPATH=src python3 -m eraleader batch \
  --kr-as-of 2026-10-02 --us-as-of 2026-02-23 \
  --out output/batch_20261010 --top 20 --days 550

# 이미 준비된 가상 산업/재무 피처 시점 통합
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR --as-of '2024-09-01T17:00:00+09:00' \
  --out output/demo_offline
```

출력: `output/batch_20261010/batch_manifest.json`, `output/batch_20261010/site/index.html`, `output/batch_20261010/reports/` (6개 Markdown), `output/batch_20261010/alerts_preview.json`. 가상 재무 자료는 `output/demo_offline/`로 완전 분리.

## 실제 테스트와 제약

| 검증 | 결과 |
|---|---|
| 전체 pytest | **54 PASS** |
| PIT 훈련/평가 데이터 경계 | 테스트 PASS(봉인 테스트 구간 라벨 미노출, embargo, 미래 피처 차단) |
| 배치 fixture 검사 | 한국·미국 2시장 / 보고서 6개 / 1차 WATCH 알림 4 / 2차 0 |
| **실제 SSD 2026-10-02 KR·2026-02-23 US 시장 캐시** | 통합 배치 성공, 웹 2개, 보고서 6개, 첫 실행 알림 미리보기 40건 |
| 동일 캐시 배치 재실행 | 성공, **새 알림 0건** |
| 실전 미래대장주 정확도 | **N/A 미검증** |
| 네트워크/라이브 전송 | **0회** |

**중요:** 한국 2026-10-02·미국 2026-02-23은 서로 다른 관찰 시점이며, 해당 배치는 국가별 기존 캐시의 기능 테스트다. 이를 양국 동일 날짜 실전 장마감 리포트나 최신 시세로 취급하면 안 된다. 실전 자산/성과·후보 상태는 여전히 PIT 및 기업행동 완전성 검증 전이므로 WATCH/연구용으로 고정.

## 완성을 위해 남은 필수 기능

- 1단계: 실제 기업 재무·산업·실적 revision/투자자수급의 오프라인 자료 계약과 source coverage. API 사용은 사용자 지시대로 후순위.
- 2단계: 과거 종목군·상폐·기업행동으로 수익률/실거래가능 가격을 검증하고 해당 커버리지 측정.
- 3단계: 산업·경쟁력·실적·주가·수급의 정규화 및 조기 예측 스코어 테스트·ablation.
- 4단계: **실제 검증된** PIT 증거를 이용한 잠재/확정/약화/교체 판정과 이력 회복.
- 5단계: 사전 정의된 미래 대장주 라벨·walkforward/holdout·오탐/lead-time 검증 및 성능 개선.
- 6단계: 실사용 UI·재실행/오류 복구·로컬 일정 실행·알림/보고 자동화. 현재 실전 알림·PDF·클라우드·API 연결은 미완료.

**개발 원칙:** REWRITE 아닌 CONTINUE. 실제 테스트 + 결과 산출 + 사용자 인수인계 + Git SHA/push 상태를 `PROJECT_STATE.md`에 기록하고 계속 진행.
