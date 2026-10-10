# EraLeader — 시대의 대장주 검색기

> 독립형 한국·미국 주식시장 대장주 발굴·추적·검증 시스템
> 프로젝트 문서 기준일: 2026-10-10 / 언어: 한국어

## 새 대화에서 개발 재개 — 먼저 읽기

**[START_HERE_NEXT_CHAT.md](START_HERE_NEXT_CHAT.md)** → [개발 지침](AGENTS.md) → [실제 개발 상태](PROJECT_STATE.md) → [다음 실행 작업](docs/25_NEXT_IMPLEMENTATION_SPRINT.md).

- **현재(2026-10-10)**: **로컬 Python 1차 통합 MVP 구동**(한국/미국 가격 관찰·PIT fixture·SQLite 이벤트·가격 baseline·정적 웹/알림 미리보기·Markdown 보고). **17개 pytest PASS**. 재무·산업 PIT와 미래 대장주 확정/성능 검증은 미완료. [실제 코드·검증·실행방법](docs/27_LOCAL_FIRST_IMPLEMENTATION.md).
- **추가로 필요한 점검**: [투자 지도와 실전 개발 사이의 남은 과제](docs/24_ARCHITECTURE_GAP_REVIEW.md).
- `CycleOS-Lab_BacktestEngine`의 데이터를 **읽기 전용 재사용**하며 무조건 재다운로드하지 않음. 새 독립 Git 저장소는 아직 없음.


## GitHub 저장소 확인 및 연결 상태 (2026-10-10)

- GitHub: [arirang0605-lgtm/eraleader](https://github.com/arirang0605-lgtm/eraleader) — 생성 확인, 기본 브랜치 `main`, 현재 공개(Public), 아직 코드 미업로드(size 0).
- T5DATA 로컬 폴더는 **Git 초기화(main)** 되었으며, GitHub origin/첫 push는 공개 범위 승인 전 **미진행**. GitHub 백업은 아직 완료되지 않았습니다.
- [보안·연결 체크리스트](docs/26_GITHUB_REPO_HANDOFF.md) 참고. 공개 설정이 바뀌지 않은 상태에서 API 키·전략·원본 데이터 push 금지.

## 1. 미션

**최종 목적은 앞으로 한국·미국 시장의 미래 대장주를 조기에 발견하는 능력을 갖춘 독립 운영 시스템을 완성하는 것**이다. 산업 구조 변화의 초기 징후와 기업 성장 가속을 발견하고, 잠재 후보 → 확정 대장주 → 주도력 약화·교체를 지속 추적한다. **과거 데이터와 백테스트는 이 미래 발견 능력이 실제로 동작하는지 검증·개선하는 수단**이지 목적 자체가 아니다. 역사적 성과가 좋다는 것만으로 미래 발견 능력이 보장된다고 주장하지 않는다.

기본 흐름:
1. 한국(KOSPI/KOSDAQ)과 미국 주요 상장주식 데이터 확보
2. 과거 시점별 공개정보(PIT) 보존 및 품질검증
3. 산업 구조변화·성장성 평가
4. 기업 펀더멘털·실적가속·상대강도·수급 평가
5. 잠재 후보 / 확정 대장주 / 약화·교체 후보 분류
6. 단계별 백테스트와 최종 미사용 데이터 평가
7. 웹 대시보드, 상태변경 알림, 일간·주간·월간 보고서
8. 필요할 때만 MarketOS 등에 읽기 전용 API·파일로 결과 제공

## 2. 확정된 프로젝트 원칙

- **EraLeader는 MarketOS와 별개**로 저장·실행·배포한다. 독자적 데이터·분석·화면을 갖추고 외부 연동은 선택 사항.
- AI는 설계·코드 개선·예외 분석에 주로 사용하고, 수집/지표/순위/백테스트/보고는 로컬 Python 배치로 수행한다.
- 백테스트는 **기반을 초기에 만든 뒤 모듈별 수행**, 마지막에 전체 통합 검증과 분리된 미사용 데이터 검증을 한다.
- 개발은 기존 코드 보호 → 최소 변경 → 자동 테스트 → 체크포인트 기록. 구현보다 테스트 결과를 기준으로 완료 판정한다.
- 결과 소비 기능 3종 전부 포함: **① 웹 대시보드 ② 자동 알림 ③ 정기 보고서**.
- 과거 상장폐지, 주식분할, 미래 데이터 누설, 발표 시차 등을 무시한 성과는 공식 성과로 인정하지 않는다.
- 검증되지 않은 점수/임계값은 초기 실험값으로 표시하며 투자성과 또는 실제 대장주 발견 확률로 표현하지 않는다.

## 3. 계획된 시스템

~~~text
[KRX/공시 DART/SEC/미국 시세/선택적 컨센서스]
                 |
         [수집·정제·품질검사]
                 |
          [PIT 데이터 저장소]
                 |
       +---------+---------+
       |                   |
  [산업 분석]          [기업 분석]
       +---------+---------+
                 |
     [스코어·후보 상태 엔진]
        잠재 / 확정 / 교체
                 |
        [검증·백테스트]
                 |
          [결과 저장/이력]
        /        |         \
 [웹 대시보드] [변화 알림] [정기 보고서]
                 |
      [선택적 외부 출력/API]
~~~

## 4. 문서 읽는 순서

1. [개발자가 우선 읽을 지침](AGENTS.md) — 재개 절차와 금지사항
2. [현재 실제 개발 상태](PROJECT_STATE.md) — 완료/미완료/다음 작업
3. [확정·제안·미결정 기록](DECISIONS.md) — 사용자 의사결정
4. [목표·범위](docs/00_VISION_SCOPE.md)
5. [시스템 설계](docs/01_ARCHITECTURE.md)
6. [데이터·PIT](docs/02_DATA_PIT_SPEC.md)
7. [대장주 판정 로직](docs/03_LEADER_DISCOVERY_LOGIC.md)
8. [백테스트 설계](docs/04_BACKTEST_VALIDATION.md)
9. [모듈 인터페이스](docs/05_INTERFACE_CONTRACTS.md)
10. [사용자 결과 화면·알림·보고](docs/06_DASHBOARD_ALERT_REPORT.md)
11. [개발 로드맵](docs/07_IMPLEMENTATION_ROADMAP.md)
12. [운영과 토큰 절약](docs/08_OPERATION_TOKEN_EFFICIENCY.md)
13. [위험 관리](docs/09_RISK_REGISTER.md)
14. [테스트·완료 기준](docs/10_TEST_ACCEPTANCE.md)
15. [데이터 조달·비용 기준](docs/11_DATA_SOURCES_COSTS.md)
16. [기존 범용 엔진 재사용 조사](docs/12_BACKTEST_ENGINE_REUSE.md)

## 5. 현재 상태 (중요)

이 SSD 폴더에는 이번에 **요구사항과 개발 명세 문서를 정리하는 작업**을 진행하고 있다. 이 문서가 있다고 해서 데이터 API 연동, 백테스트, 대시보드가 구현되었다는 뜻이 아니다. 이전 대화에서 별도로 전달된 EraLeader v0.1 가상 데이터 시제품은 **이 SSD 프로젝트에 설치되거나 검증됐다고 주장하지 않는다**. 실제 코드가 들어오면 먼저 목록/실행/테스트로 확인하고 PROJECT_STATE.md에 증거를 남긴다.

## 6. 첫 구현 목표 — 작동하는 MVP

- 실제 데이터 1개 이상 공급원을 받아 영구 저장
- 미래정보 차단 테스트 통과
- 산업 및 기업 기본 점수 → 잠재/확정 후보 랭킹
- 해당 결과의 간단한 PIT 백테스트와 지표
- 브라우저로 볼 수 있는 최소 결과 화면
- 전체 실행 명령, 오류 요약, Git 체크포인트
- 이후 미국 데이터 확장, 알림·정기 보고·클라우드 운영

> 데이터 부족 시 N/A로 표시하고, 임의 수치·가짜 백테스트 결과를 만들지 않는다.

## 7. 유의사항

투자 판단을 대체하지 않는 연구 도구이다. 대장주/후보 판정은 시장 상황과 데이터 품질에 따라 틀릴 수 있으며, 수익을 보장하지 않는다.

## 8. 1~6단계 새 전체 설계도 (세부 번호 1_1~6_5)

- **[전체 설계도 PNG (3240×2600)](EraLeader_전체설계도_1-6단계_세부번호.png)** — 6개 단계의 30개 작업을 1_1부터 6_5까지 표기.
- [수정 가능한 SVG 원본](EraLeader_전체설계도_1-6단계_세부번호.svg)
- [30개 작업 ID 목록·명세 링크](docs/21_MASTER_ARCHITECTURE_NUMBERING.md)
- [전체 설계도 재생성 Python](render_master_numbered.py)
- [중복 이미지 정리 기록](docs/22_IMAGE_CLEANUP_LOG.md)

점수와 임계값은 **미검증 개발 가설**. 기존 단계별 개별 이미지는 보존하고 옛 중복 합본만 정리합니다.

## 9. 데이터 수집 구현 명세 및 구조도 (2026-10-10)

- [주가·재무·산업/거시·공시/뉴스 데이터 수집 구현 명세](docs/13_DATA_COLLECTION_IMPLEMENTATION.md): 데이터 공급자, API 접근, PIT, 원본 저장, 정제, 스케줄, 비용·품질 게이트, 테스트 기준.
- [데이터 수집 전체 구조도 — PNG](EraLeader_데이터수집_전체구조도.png): 2400×1510의 한 장짜리 시각화.
- [데이터 수집 전체 구조도 — SVG](EraLeader_데이터수집_전체구조도.svg): 벡터 그림으로 글자·레이아웃 수정 가능.
- [그림 생성 스크립트](render_data_collection.py): 실행 시 SVG 재생성. PNG는 브라우저 렌더링으로 갱신.

**주의:** 위 파일은 개발 설계·문서 산출물이다. API 연결 및 실데이터 수집이 완료되었다는 뜻이 아니다.

## 10. 개발 2~6단계 상세 명세·개별 구조도 (2026-10-10)

**[개발 2~6단계 한눈에 보기 / 그림·MD 전체 목차](docs/19_STAGES_2_TO_6_INDEX.md)**

| 단계 | 개발 명세 | 한 장 구조도 (PNG / SVG) |
|---|---|---|
| 2 PIT 검증·저장 | [14_STAGE2_PIT_DATA_ENGINE.md](docs/14_STAGE2_PIT_DATA_ENGINE.md) | [PNG](EraLeader_2단계_PIT검증저장_구조도.png) / [SVG](EraLeader_2단계_PIT검증저장_구조도.svg) |
| 3 발굴 분석 엔진 | [15_STAGE3_ANALYSIS_ENGINE.md](docs/15_STAGE3_ANALYSIS_ENGINE.md) | [PNG](EraLeader_3단계_분석엔진_구조도.png) / [SVG](EraLeader_3단계_분석엔진_구조도.svg) |
| 4 대장주 상태 판정 | [16_STAGE4_LEADER_STATE_MACHINE.md](docs/16_STAGE4_LEADER_STATE_MACHINE.md) | [PNG](EraLeader_4단계_대장주상태판정_구조도.png) / [SVG](EraLeader_4단계_대장주상태판정_구조도.svg) |
| 5 백테스트 | [17_STAGE5_BACKTEST_RESEARCH.md](docs/17_STAGE5_BACKTEST_RESEARCH.md) | [PNG](EraLeader_5단계_단계별백테스트_구조도.png) / [SVG](EraLeader_5단계_단계별백테스트_구조도.svg) |
| 6 웹·알림·보고 | [18_STAGE6_DASHBOARD_ALERT_REPORT.md](docs/18_STAGE6_DASHBOARD_ALERT_REPORT.md) | [PNG](EraLeader_6단계_대시보드알림보고_구조도.png) / [SVG](EraLeader_6단계_대시보드알림보고_구조도.svg) |

- [새 1~6단계 전체 설계도](EraLeader_전체설계도_1-6단계_세부번호.png) / [SVG](EraLeader_전체설계도_1-6단계_세부번호.svg) — 30개 세부 작업 번호 포함
- [수정 가능한 SVG 6장 재생성 스크립트](render_stages_2_to_6.py) — Python 표준 라이브러리로 생성하고 PNG는 브라우저 렌더링.
- **중요:** 구현할 기능과 수집할 자료·테스트 기준을 구체화한 **개발 문서**이며 실제 API 연결, 코드 구현, 장기 백테스트, 서비스 운영은 아직 별도 작업이다.

- [2~6단계 문서·구조도 저장 검사 결과](docs/20_STAGES_2_TO_6_VALIDATION.md): PNG/SVG 존재·해상도·SVG XML·내부 링크 확인.

## 11. 기존 T5DATA 백테스트 자료 재사용 — 실점검 결과 (2026-10-10)

- **[기존 엔진/가격 자료 현장점검 및 활용 계획](docs/23_BACKTESTENGINE_LOCAL_REUSE.md)**: 비어 있는 \`backtestengine/\`가 아니라 \`CycleOS-Lab_BacktestEngine/\`에 재사용 자산이 존재함을 확인.
- **[로컬 가격 자료 검증 스크립트](scripts/verify_backtestengine_reuse.py)**: 외부 폴더를 읽기 전용으로 검사하고 요약 JSON 생성.
- **검증 결과:** \`results/reuse_probe/local_assets_audit.json\` (한국 일봉 1995~2026 32개 파일, 15,648,407행 메타데이터 대조 성공).
- **기존 백테스트 재실행 결과:** \`results/reuse_probe/sector_mom_baseline_one_config.csv\` (미국 업종 모멘텀 1개 설정의 계산 성공; EraLeader 대장주 발굴 성능 아님).
- **반드시 지킬 원칙:** 기존 자료 폴더는 수정하지 않고 경로 기반 **read-only adapter**로 재사용. 미래정보/PIT/상폐/기업행동/라이선스 미검증 자료는 실전 성과로 발표하지 않는다.

- **[첫 실사용 가격 캐시 조회기](scripts/read_cached_marcap.py)**: 기존 marcap Parquet에서 삼성전자(005930) 2025년 1월 시세 18개 거래일을 실제로 읽음. 새 다운로드 0회. \`results/reuse_probe/marcap_sample_query.json\`에 샘플 결과 저장.

- **[새 대화 복구 검증 스크립트](scripts/check_handoff.py)**: `python3 scripts/check_handoff.py` → 2026-10-10 실행 PASS (문서·그림·검증 증거 존재 확인; 투자성능 시험 아님).

## 12. 로컬 우선 개발판 실행 (2026-10-10 최초 통합 테스트)

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m eraleader run --market KR --as-of 2026-10-02 --top 20
PYTHONPATH=src python3 -m eraleader run --market US --as-of 2026-02-23 --top 20
PYTHONPATH=src python3 -m eraleader serve --port 8765
```

브라우저 주소: **http://127.0.0.1:8765/** (PC 안에서만 접속). 명령 실행 없이 `output/site/index.html` 파일을 직접 열어도 된다. 보고서 생성은 `PYTHONPATH=src python3 -m eraleader report weekly --market KR`, 알림 모의 생성은 `PYTHONPATH=src python3 -m eraleader alerts-preview`.

**[구체 개발 상태·증거·제약 사항](docs/27_LOCAL_FIRST_IMPLEMENTATION.md)**. 현재 웹 목록은 **가격 기반 연구용 WATCH**이며, 재무/산업 PIT가 없어 잠재·확정 대장주 순위를 보증하거나 생성하지 않는다. 외부 API/실제 메시지 발송 없음.

## 13. 오프라인 PIT 종목·기업행동·재무/산업 분석 (2_2·2_3·3_1~3_3)

- [상세 코드·입력·실행·검증 결과](docs/28_OFFLINE_PIT_FEATURE_IMPLEMENTATION.md). 전체 자동 테스트 **33개 통과**(2026-10-10).
- API 사용 없이 CSV/JSON을 `offline-import`로 입력하고, `offline-features --as-of`로 당시 공개된 산업/기업 성장값 계산.
- **가상 예제**: `PYTHONPATH=src python3 -m eraleader offline-import --file tests/fixtures/offline_synthetic.json --out output/demo_offline`
- **분석 예제**: `PYTHONPATH=src python3 -m eraleader offline-features --market KR --as-of '2024-09-01T17:00:00+09:00' --out output/demo_offline`
- 연구용 합성 데이터는 `output/demo_offline/`에만 저장, 실제 한국·미국 가격 목록과 혼합 금지. 아직 종목별 역사 완전성/재무 PIT 제공자 검증 전이라 확정 대장주를 발표하지 않는다.

## 14. 3~6단계 로컬 연결 및 GitHub 동기화 (2026-10-10)

- **코드·테스트·실행방법:** [29_LOCAL_STAGE3_TO_6_MILESTONE.md](docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md).
- 가격·산업·재무 시점 결합 `offline-integrated` 명령을 추가해 `output/demo_offline/site/research_kr.html` 연구 화면까지 생성.
- 최초 발굴→정식 평가 시점의 **조기 발견 품질 계산기** `validate-discovery`, 상태·변경 이벤트 이력 `state_history.py` 구현. 연구용 synthetic fixture만 검증함.
- **pytest 49개 PASS**, 로컬 HTTP e2e PASS. 30개 세부 작업 전체 완료는 아니며 PIT/실전 모델 검증·외부 API 연결은 보류.
- GitHub **Public push 사용 승인됨**, `main`에 최초 push 성공. API/인증키는 `.secrets/` 로컬 전용(Git ignore)으로 보관. 후속 체크포인트는 `PROJECT_STATE.md` 최신 기록을 기준으로 한다.

## 15. KR·US 로컬 배치와 워크포워드 (2026-10-10)

- [실제 구현 및 재현 명령: 30_WALKFORWARD_LOCAL_BATCH.md](docs/30_WALKFORWARD_LOCAL_BATCH.md).
- **연구용 batch**: `PYTHONPATH=src python3 -m eraleader batch --kr-as-of 2026-10-02 --us-as-of 2026-02-23 --out output/batch_20261010`. 실제 SSD 캐시로 2개 국가·일/주/월 보고서 6개·로컬 HTML·알림 미리보기 생성 PASS, 재실행 새 알림 0건.
- **walkforward**: 피처/라벨 시점 분리 및 embargo, 미래 라벨 격리 (아직 완성된 실전 검증 아님). **pytest 54 PASS**.
- 소스 가격 관측일이 양국마다 다르므로 해당 실행을 최신 실전 장마감 리포트로 오해하지 않는다. API·실제 메일·메시지 전송은 없음.

## 16. 기업행동·상장종목군 품질 감사 (2026-10-10)

- [2_2·2_5 기업행동 수익률과 시장 종목군 관측 감사 결과](docs/31_CORPORATE_ACTION_AND_UNIVERSE_AUDIT.md)
- `PYTHONPATH=src python3 -m eraleader corporate-return --help`: 비조정(raw) 종가와 공시·실효일을 이용한 분할/배당 누적수익 복원(연구용). 과거 종가의 `available_at`이 신호시점 후라면 누출 차단.
- `PYTHONPATH=src python3 -m eraleader audit-universe --as-of 2026-10-02 --days 35`: 실제 SSD 캐시 관측 종목군 비교. 직전/당일 등장·미관측·무거래/정지 플래그 검사, 실제 상장폐지 진실 등록부로 오인 금지.
- **전체 pytest 73 PASS**, 외부 API·유료 데이터 요청 없음. 인증된 분할/배당·상폐 재무/기업행동 완전성 검증은 미완료이며 현황에 명시.

## 17. SQLite 연구 결과 로컬 백업·복구 (6_5 부분 구현, 2026-10-10)

- [32_LOCAL_BACKUP_RECOVERY.md](docs/32_LOCAL_BACKUP_RECOVERY.md): `backup-local`, `verify-backup`, `restore-backup` 명령. SQLite 온라인 일관 백업 + SHA256 매니페스트 확인, 검증 후 새 경로에만 원자적 복구.
- 실제 SSD 한국/미국 결과로 **16개 파일 백업 및 복구 PASS**, 보고서 6개·HTML 3개 확인. 비밀정보·원시 주가 자료 제외. 전체 **pytest 79개 통과**.
- 이 기능은 같은 SSD 내부의 운영 복구용이므로 외장장치 손상 대비 오프사이트 백업이나 실제 서비스 자동 스케줄의 완료를 뜻하지 않는다.
