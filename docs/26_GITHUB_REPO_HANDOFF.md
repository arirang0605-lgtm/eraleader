# GitHub EraLeader 저장소 연결 및 안전한 개발 연속성

> 2026-10-10 GitHub 커넥터로 사용자 권한의 저장소 목록을 직접 조회한 결과. SSH/HTTPS Git remote 설정은 이후 작업.

## 1. 실제 확인 결과

| 항목 | 확인 |
|---|---|
| 저장소 전체 이름 | `arirang0605-lgtm/eraleader` |
| 주소 | https://github.com/arirang0605-lgtm/eraleader |
| Git URL | `https://github.com/arirang0605-lgtm/eraleader.git` |
| 기본 브랜치 설정 | `main` |
| 현재 GitHub 표시 크기 | `0` (미업로드/빈 저장소로 보임) |
| 가시성 | **PUBLIC(공개)** — 사용자가 기대한 Private 상태가 아님 |
| 커넥터 계정 권한 | admin, pull, push 보유 |
| 로컬 SSD `eraleader/.git` | **없음**, 원격 연결 안 됨 |
| 실제 commit/push 여부 | 수행하지 않음 |

## 2. 우선 조치 (실행 전 사용자 확인)

1. **공개/비공개 확인**: 사용자가 Private으로 변경하면 GitHub의 Settings → General → Danger Zone → Change repository visibility에서 비공개 전환 여부 확인. 사용자 승인 없이는 공개 상태 변경하지 않는다.
2. **로컬 자료 확인**: 현재 `/Volumes/T5DATA/eraleader`에 소스 패키지는 아직 없고 많은 MD·SVG·PNG·실행 결과와 스크립트가 있다. 최초 커밋 전 파일 목록 검토.
3. **민감 데이터 예방**: `.env`, API 키, 토큰, 계정/로그, 개인정보, 대용량 원시 시세, `results/`의 원자료·데이터 재배포 제한 파일을 Git에 올리지 않는다. `.gitignore` 준비 및 `git status` 확인.
4. **Git 초기화·remote 설정**: 빈 로컬 폴더 안의 기존 파일을 보존한 채 `git init -b main`, `git remote add origin https://github.com/arirang0605-lgtm/eraleader.git`는 해당 단계에서만 실시.
5. **원격 초기 커밋 확인**: GitHub 화면에서 size=0으로 확인되지만 브랜치 존재 여부는 첫 push 전 `git ls-remote` 등으로 재확인. 이미 원격 초기 README가 있으면 합치고 기존 원본 덮어쓰기 금지.
6. **테스트 → 커밋 → 푸시**: 로컬 정적/단위 테스트를 통과한 파일만 Git에 추적, 보안 검사 후 `git push -u origin main`. push 뒤 원격 commit SHA와 `PROJECT_STATE.md` 기록을 확인.
7. **보존**: 백테스트 실데이터는 읽기 전용 공유하고 원격 저장소에 대량 복사하지 않는다. SSD 백업과 Git을 서로 다른 독립 보존 수단으로 활용.

**중요**: 저장소가 현재 공개이므로 보안/공개 범위를 확정하기 전에는 첫 push를 자동 수행하지 않는다. 원격 visibility 상태는 언제든 바뀔 수 있으므로 push 전 다시 확인.

## 3. 새 대화의 필수 작업 순서

```text
PC 연결 → START_HERE_NEXT_CHAT.md → AGENTS.md →
PROJECT_STATE.md 상단 → DECISIONS.md →
해당 작업 MD → git status/remote -v 확인 →
실행·테스트 → git diff/비밀정보 검토 →
사용자 승인된 repo로 커밋/푸시 → PROJECT_STATE.md 최신화
```

- **REWRITE 금지**, 변경 대상 파일 위주로 검토.
- 사용자 결정 없이는 remote repository visibility/branch/history를 강제 변경하지 않음.
- 원격이 비어 있다면 'GitHub 생성 완료 / 연결·첫 push 미완료'라고 정확히 보고.
- 토큰 절약: 매번 GitHub 전체 repository를 재검색하지 않고 `git status`, `git log -1`, `git remote -v` 및 필요 시 커넥터로 최신 상태 확인.

## 4. 개발 최종 목적 및 기록

EraLeader의 **최종 목표는 미래 대장주를 조기에 발견하는 능력을 구현하고 운영하는 것**. 과거 데이터와 백테스트는 그 능력이 당시 정보만으로 작동하는지 검증하는 수단이며, 높은 과거 수익률 자체가 목표가 아니다.

각 작업은 `1_1`~`6_5` 중 ID를 남기고, 수정 파일/테스트 수/검증 출처/미해결/다음 작업/커밋 SHA 및 push 결과를 `PROJECT_STATE.md`에 기록한다.

## 최신 로컬 개발 추가 기록 (2026-10-10)

- 기존 점검 당시 로컬 `.git` 없다는 문구는 **역사적 기록**이다. 이후 사용자 승인된 개발 착수 과정에서 `/Volumes/T5DATA/eraleader` 로컬 Git `main` 초기화 완료.
- 최초 로컬 커밋 `72ef51487d6bd997e819d744fbbc26713f46e6a3`; **68개 코드·문서·구조도 파일**이 추가됨. `.env`, `results/`, `output/`, 원시 가격은 제외.
- GitHub `arirang0605-lgtm/eraleader`의 공개 상태는 마지막 조회 당시 Public. 원격 `origin` 연결과 push는 수행하지 않았다. 다음 작업에서 사용자 공개 범위 승인 후 진행.
