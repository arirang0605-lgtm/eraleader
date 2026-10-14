# 163 — 6_5 한국 전체시장 연구 검색 평일 자동배치 launchd 준비

**일자:** 2026-10-14 KST
**개발 ID:** 6_2 · 6_5 · 1_2
**작업 브랜치:** feature/kr-marketwide-search-20261014

## 완료된 기능

- 새 `src/eraleader/marketwide_schedule.py` / `scripts/generate_marketwide_schedule.py`로 **기존 정상** `scripts/render_local_operations.py --marketwide-source-root`를 실행하는 macOS 사용자 launchd plist를 안전하게 생성한다. 기존 KRX/DART/Kiwoom API 코드는 재작성·호출하지 않는다.
- 기본 현지시각 **월~금 18:40(KST)**, launchd `Weekday=1..5`/Hour=18/Minute=40, `RunAtLoad=false`. Mac 시스템 로컬 시간대가 Asia/Seoul일 때 KST로 실행되는 구성. 현재 Mac `date` = KST +0900 확인.
- 생성 위치는 **해당 작업트리의 output/ 바로 아래 아직 없는 .plist**로 제한, `O_EXCL`/nofollow 및 소스·프로젝트 실제 로컬 디렉터리 검사. 로그는 기존 `output/verification_logs`, 프로그램 인자는 기존 read-only 로컬 연구 페이지 생성 명령만 포함. 추가 주문·실전 알림·외부 API 접근0. `launchctl load/bootstrap` 또는 macOS 서비스 설치 명령 실행0.
- T5DATA 현재 볼륨은 `chmod(0600)` 호출 뒤 `0700`으로 보이는 특성이 실제 확인됨. 따라서 모드 `0600` **또는 동일하게 group/other 접근이 0인 owner-only `0700`**만 허용하고, 그룹/타인 접근 권한이 있으면 무조건 FAIL. 실제 plist 모드 `0700` owner-only로 생성 성공.
- 원본 main 미커밋 내용/기존 캐시·백업·시장 자료/타 프로젝트 소스·Git main은 변경하지 않는다.

## 실제 T5DATA 로컬 작동

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/generate_marketwide_schedule.py --project "$PWD" \
  --source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
  --out "$PWD/output/kr_marketwide_research_weekdays_1840.plist"
```

- 생성 결과 `KR_MARKETWIDE_SCHEDULE_PREPARED_NOT_INSTALLED`, `plutil -lint` **OK**. 실제 Mac plist를 Python `plistlib`로 다시 읽어 5개 평일/18:40/`RunAtLoad=false`/파일권한0700 확인.
- **plist 안에 기록된 실행 명령을 1회 직접 호출**: 종료코드0, 연구 검색 최신 공식 KRX 2026-10-13 전체 2,761종목 자동 확인, `KR_MARKETWIDE_SEARCH_ALREADY_CURRENT`, 기존 운영 화면 링크 자동 반영. 설치 전 동작 실측 성공.
- 변경+기존 영향범위: `PYTHONPATH=src python3 -m pytest tests/test_marketwide_schedule.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_live_search.py tests/test_operations_marketwide_navigation.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/marketwide_schedule_final_20261014.xml` -> **79/79 PASS, failures0/errors0/skipped0, exit0**. Python compile, `git diff --check` PASS.
- 테스트 핵심: weekday 시간, 원래 운영 화면 실작동, 재실행 멱등, 기존 경로 덮어쓰기 금지, 잘못된 시간 거절, out-of-root 경로/심볼릭 링크 거절, 생성만 가능·재시도 실패.

## 제한과 다음 작업

**실제 정기 예약 실행 상태는 아직 아님.** 현재는 launchd 설정파일을 생성했으며 macOS 서비스에 설치하거나 로드하지 않았다. SSD 분리·재부팅 시험, 실거래 주문, 실제 SMS/메시지 발송, 독립 공시 PIT·실제 대장주 예측 정확도 검증은 실시하지 않았다. 소스 작업트리는 여전히 feature 브랜치에 있으므로 운영 설치 전 브랜치 경로 고정·주 프로젝트 통합을 고려한다. 데이터 소스가 지연되면 기존 연구용 최신 유효 거래일만 표시하며 당일 실제 시세라고 표시하지 않는다.

**다음 실제 기능 개발:** 5요소 실제 자료 커버리지와 대장주 상태 자동 판정·프로젝트 중립 JSON 송신 완성. 차후 승인된 운영 위치에서 launchd plist 설치 및 휴장/장애·재시작 검증.
