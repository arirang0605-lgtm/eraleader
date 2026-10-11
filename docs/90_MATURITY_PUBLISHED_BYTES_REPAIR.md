# EraLeader 6_5 — Top-K 만기 예약보고 HTML/JSON/MD 실제 바이트 무결성

기준일: 2026-10-11 KST. 기존 `docs/89_SCHEDULED_NATIVE_TOPK_MATURITY_BRIEFS.md`의 한국·미국 native Top-K 16개 연구 보고서 예약 생성 흐름을 유지하면서, 완료 체크포인트의 '변경 없음' 상태를 잘못 승인하는 결함을 수정했다. 외부 API, 라이브 알림, 외부 배포 및 실제 SSD 분리 시험은 수행하지 않는다.

## 실제 확인된 결함

기존 `run_scheduled_maturity_only`는 동일 원본 fingerprint이고 ZIP의 내부 SHA 검증이 성공하면, 발행된 16개 파일의 **존재 여부만** 확인해 `SKIPPED_UNCHANGED_RANKED_MATURITY_EVIDENCE`를 반환했다. ZIP 생성 후 로컬 공개 HTML에 거짓 수익률을 추가하거나 JSON/주간 보고서를 수정한 경우에도 '검증된 화면'이라고 판단했다. 손상된 화면과 검증된 ZIP은 별개의 상태이므로 이는 배포 무결성 결함이다. 또한 체크포인트 `archive` 필드가 임의 디렉터리에 있는 다른 유효 ZIP을 가리켜도 상태를 통과시켰다.

회귀 테스트 **5개가 기존 코드에서 실제 FAIL(RED)**: HTML/월간 HTML/주간 MD/JSON 기존 파일 내용 추가 조작 4유형 + 체크포인트 백업 포인터 외부 경로 변경 1유형.

## 최소 수정: 스케줄러 재사용+read-only 교차검증

- `src/eraleader/scheduled_maturity_bridge.py`: `published_maturity_pages_match_verified_backup` 추가. 먼저 기존 `verify_backup`이 ZIP의 SHA 매니페스트를 검증한 후, 원래 KR+US JSON 2 + 기본 HTML 2 + 일·주·월 MD/HTML 12, 합계 **16개 원본 보고서 경로**를 ZIP `MANIFEST.json`의 각 SHA256/길이와 실제 live 파일의 **현 바이트**로 다시 대조한다. 누락, 내용 변형, 링크, 크기 불일치, 파일별 SHA 불일치는 SKIP 허용하지 않는다.
- `src/eraleader/local_schedule.py`: checkpoint의 archive 포인터가 지정 `backups` 디렉터리 안의 `ranked_maturity_only_*.zip`인지 경계 검사. 이전 ZIP 내부 무결성·실제 16 live 보고서 증거·KR/US 원본 freeze/score/WATCH/정의 재감사가 **모두** 통과할 때만 `SKIPPED_UNCHANGED_...` 반환. 아니면 기존 예약 생성 함수로 16개 보고서 재발행 후 새 ZIP SHA 검증 및 atomic checkpoint 갱신.
- `tests/test_scheduled_maturity_bridge.py`: 신규 **6개 회귀 테스트**(4종 파일 변조 + 부적절한 ZIP 포인터 + **크기는 같고 내용만 N/A→100으로 바꾼 거짓 성과**). 변경 없음이면 불필요한 재작성 없이 기존 ZIP 재사용하는 테스트 등 이전 테스트 보존.

로컬 SHA는 해당 기기의 파일 변화 감지이고, KRX/SEC 법적 기업/공시 시각·원천 데이터의 **독립적 인증이나 실전 성공률**은 아니다. 결과 label이 없는 horizon 경과 후보의 positive/negative/precision은 여전히 N/A, 공식 대장주 승격 0.

## 재현

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_scheduled_maturity_bridge.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 -m py_compile src/eraleader/{scheduled_maturity_bridge,local_schedule}.py
```

원본 WATCH/SCORE/PRICE SQLite, 시세·공시 파일, 다른 프로젝트 코드는 수정하지 않았다. `output/` 로컬 synthetic 결과는 Git 추적하지 않는다. 실전 신규 cohort 생성·5_5 independent matured outcome·원천 PIT completeness는 잔여 과제. D-017(API 후순위), D-021(실제 SSD 탈착 및 재부팅 최종 단계) 유지.

검증 횟수·Git SHA 및 push 여부는 `PROJECT_STATE.md` 마지막 체크포인트에서 실제 수행 결과를 기준으로 한다.
