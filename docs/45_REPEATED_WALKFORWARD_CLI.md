# EraLeader 5_5 — 반복 워크포워드 오프라인 CLI 및 백업 통합

> 2026-10-10, `/Volumes/T5DATA/eraleader` 실제 개발/실행. 이 기능은 미래 대장주 발굴 정확도, 사전 등록 여부, 역사적 종목군/공시 PIT를 인증하지 않는다. 외부 API, 라이브 알림 및 실전 주문 0회.

## 이어 개발한 실제 기능

- `src/eraleader/walkforward_replay.py`의 이미 검증된 다중 폴드 엔진은 2~40개 확장 기원(Expanding-origin) 워크포워드 분할, 엄격한 폴드 순서, 엠바고, 잠금 모델 버전/라벨 정의를 강제한다. 기존 `walkforward.py`와 백테스트, 캐시 재작성 없음.
- `src/eraleader/cli.py` 신규 `replay-walkforward`는 로컬 JSON의 타임스탬프 피처 스냅샷/독립 라벨/폴드 윈도 목록을 받아 엔진을 호출한다. 결과는 `repeated_walkforward_research.json`에 **후보 목록 및 학습자료 해시만** 저장하며, 테스트 후보에 정답 라벨은 없다. CLI 상태에는 폴드 수, 고유 테스트 후보 수, `test_outcome_labels_revealed=false`, `historic_universe_pit_certified=false` 명시.
- `src/eraleader/local_backup.py`는 이 **파생 연구 JSON만** SHA256 백업 대상에 포함한다. 원본 피처/정답 파일은 백업 금지, 민감 정보의 공개 Git 반영도 금지.
- `tests/test_repeated_walkforward_cli.py` 3개 신규 테스트는 CLI 유출 차단, 라벨 정의 변조 시 실패, 복구된 결과의 미인증 상태와 원본 제외를 확인한다.

## 실제 로컬 실행

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader replay-walkforward \
  --snapshots output/repeated_walkforward_cli_trial_20261010/snapshots.json \
  --outcomes output/repeated_walkforward_cli_trial_20261010/outcomes.json \
  --windows output/repeated_walkforward_cli_trial_20261010/windows.json \
  --model-version locked-experiment-1 \
  --label-definition-id fixed-leader-definition-1 \
  --embargo-days 7 \
  --out output/repeated_walkforward_cli_trial_20261010/derived
PYTHONPATH=src python3 -m pytest tests/test_repeated_walkforward_cli.py tests/test_walkforward_replay.py -q
PYTHONPATH=src python3 -m pytest tests -q
```

- 합성 4개 시점별 후보, 2개 폴드 → 테스트 후보 총 3개, 모델/라벨 규약 고정, 향후 정답 누출 `false`, 실전 PIT `false`.
- 합성 결과 1개 JSON만 `output/continuous/repeated_walkforward_cli_verified_20261010.zip`에 SHA256 백업·검증·복원 완료. 복구한 JSON의 `fold_count=2`, `unique_test_candidate_count=3`, 테스트 라벨 비공개를 재확인.
- 직전 단계: `19b5ad7` + `27afec0` 영구 issuer ID 감사 코드 278 테스트 (독립 HEAD), 다른 세션의 19개 워크포워드 테스트를 별도 검증하여 `4ee780d`로 커밋/푸시. 이번 CLI 3개 테스트 추가 후 공유 소스 300개 테스트 PASS.

## 다음 미완료

2단계 진짜 거래소 원천에서 영구 기업 ID, 상장폐지 현금 정산, 이벤트 공개·정정 이력과 법적 기업행동 자료를 취득/독립 증명하지 않았다. 5단계 최종 봉인 홀드아웃은 실제 미래 결과가 성숙해야 평가 가능하다. 6단계 실제 맥북 재부팅/SSD 물리적 분리도 미검증. 모든 결과는 로컬 연구용이며 전체 1_1~6_5 인증 선언 금지.
