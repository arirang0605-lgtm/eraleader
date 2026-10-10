# EraLeader 6_5 로컬 운영 백업·무결성 검증·원상복구

> 2026-10-10 실제 구현 및 SSD 캐시 산출물로 검증. 데이터 소스/API 연결 없음.

## 목표 및 개발한 부분

- `src/eraleader/local_backup.py`: 운영 중 갱신 가능한 `state.sqlite`, `offline.sqlite`, `state_history.sqlite`에 **SQLite 온라인 백업 API**를 적용하여 읽기 일관성을 확보.
- 허용된 `kr_latest.json`, `us_latest.json`, `batch_manifest.json`, `site/*.html`, `reports/*.md`, `runs/*.json` 등의 연구 결과만 ZIP 압축. `.env`, `.secrets`, 원시데이터, `*.parquet`, 알 수 없는 파일은 제외.
- 압축 파일 `MANIFEST.json`에 각각 SHA256/파일 크기/버전·생성시각 기록. 보관 전과 복구 전 모두 전체 파일을 실제 읽어 SHA256 검증, 파일 중복·경로탈출(path traversal)·대용량 압축폭탄 보호 검사.
- 새 백업이 이미 있으면 덮어쓰지 않음. 복구는 **새 경로**에서만 가능하며 기존 결과 DB를 덮어쓰지 않는다. 임시폴더에 모든 파일을 만든 뒤 원자적 rename으로 새 목적지에 배치.
- `src/eraleader/cli.py`: `backup-local`, `verify-backup`, `restore-backup` CLI 추가.
- `tests/test_local_backup.py`: 메모리·디스크 SQLite/미커밋 WAL 일관성·SHA 위변조/위험 경로·기존파일 덮어쓰기/비밀 파일 제외/실제 CLI 호출 검증.

## 직접 재현한 명령

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader backup-local \
  --out output/batch_20261010 \
  --archive output/continuous/eraleader_batch_backup_20261010.zip
PYTHONPATH=src python3 -m eraleader verify-backup \
  --archive output/continuous/eraleader_batch_backup_20261010.zip
PYTHONPATH=src python3 -m eraleader restore-backup \
  --archive output/continuous/eraleader_batch_backup_20261010.zip \
  --target output/continuous/restored_batch_20261010
PYTHONPATH=src python3 -m pytest tests -q
```

## 실제 실행 결과

| 항목 | 검증 결과 |
|---|---|
| 전체 자동 테스트 | **79 PASS** (기존 73 + 신규 6) |
| 기존 SSD 실제 배치 결과 백업 | **16개 파일, 입력 데이터 162,531 bytes**, 실행 성공 |
| ZIP SHA256/매니페스트 확인 | PASS |
| 다른 출력 경로로 복구 | PASS |
| 복구된 보고서 | **6개 Markdown** |
| 복구된 웹 문서 | **3개 HTML** |
| 악성 경로/변조/파일 덮어쓰기/유효하지 않은 DB | 테스트로 차단 |
| 비밀키·원시 시세·데이터 공급자 호출 | 포함/호출 없음 |

**제한**: 같은 T5DATA SSD에 보관한 로컬 백업은 SSD 자체 고장에 대비한 이중 백업이 아니다. 나중에 사용자가 승인한 별도 외장 디스크/클라우드에만 복제. 현재 목적은 로컬 실행/손상에서 안전하게 복구할 수 있는 기술적 기반 구축이다.

## 다음 미완료 우선순위

- 2단계 역사적 종목군/기업행동 PIT 자료 출처·커버리지 및 정산금·조정가격 대조, 5단계 거래비용/상폐 포함 시점별 강건성 검증.
- 6_5 맥북 로컬 일정 자동화(launchd), 오류·휴장·잠자기/재부팅 복구, 데이터 갱신 시점 관리. AI Codex CLI는 2026-10-10 실제 사용량 소진이 확인되어 사용 불가 중이며, 개발 관리자가 무한 재시도해 토큰을 낭비하지 않도록 해야 한다.
- 1~6단계 전체 완료 및 미래 대장주 실전 조기 발굴 성능은 **아직 미검증**.
