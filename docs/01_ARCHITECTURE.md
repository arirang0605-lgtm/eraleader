# 시스템 아키텍처

## 모듈
```text
sources/{krx,dart,sec,us_price,consensus?}
  → ingest → normalize → data_quality → pit_store
  → industry_scoring + company_scoring + market_scoring
  → ranking + state_machine + candidate_events
  → result_store
  → dashboard / alerts / scheduled_reports / read_only_api
               ↘ backtest_adapter → backtest_engine → evaluation
```

## 설계 원칙
- Regime(시장 환경) ≠ Sector/Industry Selection ≠ Company Selection ≠ Portfolio Allocation ≠ Risk ≠ Execution. EraLeader는 산업/기업 후보 판별과 평가에 집중.
- 분석 모듈별 데이터 계약·버전·테스트 고정. 외부 프로젝트와 내부 클래스 공유 금지.
- 데이터 수집·변환·점수·후보/이력·UI를 분리. 재실행 가능한 결정적 배치.
- 최초 실행은 Python CLI, 배치 스케줄러 및 웹 UI는 추가 레이어.
- source_raw 는 불변 보존, normalized와 feature는 버전·as_of 시각으로 구분.
- 결과 출력은 기준일+데이터 사용시각+코드/데이터 버전+점수 설명+결측 마스크 동봉.

## 권장 구현 디렉터리 (아직 코드가 아니라 목표 구조)
```text
eraleader/
  README.md AGENTS.md PROJECT_STATE.md DECISIONS.md
  docs/
  pyproject.toml
  src/eraleader/
    config.py cli.py
    data/{sources,normalize,pit,quality,storage}
    features/{industry,company,momentum}
    discovery/{score,rank,state,events}
    backtest/{adapter,metrics}
    delivery/{api,dashboard,alerts,reports}
  tests/{unit,integration,pit,regression}
  scripts/{run_daily,verify,update_state}
  output/            # 대용량 결과; gitignore
  .env.example       # 비밀키 입력 템플릿만 저장
```

## 단계형 파이프라인
- 입력 검증 실패 → 해당 종목/지표 N/A; 시스템 전체의 조용한 성공 처리 금지.
- 데이터 준비 → 특징 계산 → 결정적 점수 → 상태 이벤트 기록 → 단일 DB에 저장.
- 사용자 화면·알림·보고는 같은 후보 스냅샷을 재사용; 화면 열 때 LLM 재분석 없음.
- 로그는 실행 ID/run_id, 기준일, 코드 버전, 데이터 출처, 성공/실패 요약을 보존.

## 기술 후보
Python 3.11+, DuckDB+Parquet(초기 로컬), pytest, CLI, Streamlit 혹은 간단한 웹 프레임워크. 클라우드 필요 시 API와 저장소만 교체하도록 추상화. 구체 기술은 실제 배포 및 비용 확인 후 선택.
