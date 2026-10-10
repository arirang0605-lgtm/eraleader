# EraLeader 중복 그림 정리 기록

> 기준일: 2026-10-10. 전체 세부번호 1_1~6_5 일원화, 오래된 중복 그림 정리.

## 최신 유지 설계도

- [새 전체 1~6단계 번호 설계도 PNG](../EraLeader_전체설계도_1-6단계_세부번호.png)
- [새 전체 1~6단계 번호 설계도 SVG](../EraLeader_전체설계도_1-6단계_세부번호.svg)
- [고유 30개 작업 ID 및 상세 문서](21_MASTER_ARCHITECTURE_NUMBERING.md)

## 삭제한 중복 그림

| 삭제한 파일 이름 | 삭제 전 크기(바이트) |
|---|---:|
| EraLeader AI 투자 시스템 설계도.png | 1,914,031 |
| EraLeader 데이터 수집 구조도.png | 1,950,354 |
| EraLeader 주도주 발굴 시스템 로드맵.png | 1,794,925 |
| EraLeader_전체개발청사진.png | 546,495 |
| EraLeader_전체개발청사진.svg | 28,358 |
| EraLeader_2-6단계_통합구조도.png | 509,519 |
| EraLeader_2-6단계_통합구조도.svg | 27,086 |

- 삭제한 원본 그림 총 7개, 약 6.46MiB.
- 해당 파일과 연관된 macOS AppleDouble 그림 보조 파일(있는 경우)도 제거.
- 오래된 설계도 생성 스크립트 render_blueprint.py 제거(새 render_master_numbered.py 유지).

## 유지하는 필수 그림

- 최신 전체 설계도 1장 × PNG·SVG
- 1단계 데이터 수집 상세도 1장 × PNG·SVG
- 2~6단계 개별 상세도 5장 × PNG·SVG
- 원본 MD·범용 백테스트 설계·PIT 설계 및 단계별 개발 명세는 삭제하지 않음.

## 과거 문서 주의

- docs/20_STAGES_2_TO_6_VALIDATION.md의 구형 합본 파일 목록은 과거 검증 이력으로 보존한 것이며, 현재 보존 목록은 이 문서와 최신 전체 설계도를 우선한다.
- README.md와 단계 인덱스의 최신 연결을 먼저 변경한 뒤 중복 그림을 삭제했다.
