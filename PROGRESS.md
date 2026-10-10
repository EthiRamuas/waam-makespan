# PROGRESS.md

## 현재 상태 (체크포인트 갱신)
- 단계: **1단계 종료** (geometry · segment · prevalidate · timing · writer). 2단계 진입: 작업 5 results.csv 스키마부터
- 통과 테스트: 225 passed (Claude 실측, 10-10 14:24)
- 막힌 곳: 없음. 결정 대기: C-06(max_step_mm), C-15(writer 게이트에 선후관계·아크 검사)
- 다음 작업: 작업 5 results.csv 스키마 인터페이스 제안(승인 대기) → 구현 → 리뷰 → 커밋. slicing.py 명세서는 코드 없이 제출
- 신호: 계속

## 시간 기록
| 시각 | 사건 |
|---|---|
| 2026-10-10 13:28 | 세션 시작 (가용 3h, 연속) |
| 2026-10-10 13:32 | ★2 승인. 브랜치 `session/2026-10-10` 생성. 작업 1 시작 |

계획 중반(15:00) 계획 대비 결과 한 줄: (미기록)
| 2026-10-10 13:34 | 작업 1 완료·커밋 (pytest 151 passed 실측) |
| 2026-10-10 13:36 | 작업 2 시작 (C-08/C-09 승인 직후) |
| 2026-10-10 13:45 | 작업 2 완료: timing.py 구현, 리뷰(waam-reviewer, 약 5분 12초) 지적 8건 중 1~7 반영·8 테스트로 고정, pytest 180 passed |
| 2026-10-10 13:5x | C-12 완료(213b23a). 작업 3 writer 인터페이스 제안 작성 중, 승인 전 writer.py 미생성 |
| 2026-10-10 14:18 | 작업 3 완료: writer.py + 린터, 리뷰(waam-reviewer, 약 6분 10초) 지적 8건 중 1~8 반영(선후관계·아크 게이트는 C-15로 이월), pytest 224 passed |
| 2026-10-10 14:2x | 작업 4 완료: sample_job을 build_chain+writer로 재현, waam-validator run exit 0 / PASS (summary.json makespan_s=25.606472432806626). 리뷰(약 3분 22초) 지적 1~4 반영. 범위 한계: sample_job config는 center z·속도 fail·아크 시간이 실제 모델과 다름 |

## 1단계 종료 근거 (실측)
- pytest 225 passed (66.68 s, 10-10 14:24).
- sample_job을 `build_chain` + `writer`로 재현해 `waam-validator 1.0.1 run`: exit 0, status PASS, issues=[], summary.json makespan_s=25.606472432806626.
- 한계: sample_job config는 실제 모델과 다르다(tcp_z_reference top, 속도 fail 꺼짐, 아크 시간 없음). 실제 제출 경로(center z, 속도 fail 켜짐, 아크 필수)는 모델 01 fixture를 쓰는 test_timing/test_writer 골든 테스트가 덮는다. 모델 01~06 형상 PASS와 ratio는 미측정(toolpath 이후).

## 작업별 실측 소요 시간 (시계 읽기 기준, 계획 대비)
| 작업 | 시작 | 종료 | 소요 | 리뷰어(waam-reviewer) | 계획 예상(가설) |
|---|---|---|---|---|---|
| 1 문서·규칙·브랜치 | 13:32 | 13:34 | 약 2분 | — | 15분 |
| 2 timing | 13:36 | 13:45 (커밋 2ec6604) | 약 9분 | 5분12초 | 30~60분 + 리뷰 |
| 3 writer + 린터 | 시작 시각 미기록 (제안서 13:49, 승인 후 구현) | 14:18 pytest 224 passed 후 커밋 ea87e94 | 미기록 (구현 첫 테스트 통과 14:08) | 6분10초 | 30~60분 + 리뷰 |
| 4 1단계 종료 검증 | 시작 시각 미기록 | 14:24 (커밋 34eb79c) | 미기록 (첫 통과 14:20) | 3분22초 | 20분 |
- 사람이 답을 기다린 시간은 위 소요에 섞여 있다(작업 2는 C-08/C-09 답 대기 구간을 포함하지 않는다).
- **이 속도를 2~4단계 일정에 적용하지 않는다.** 1단계 모듈은 명세(Validator 판정식, CSV 계약)가 이미 확정돼 있었고 설계 결정이 인터페이스 2~3건뿐이었다. 계획 합계 약 2h35분(가설)을 약 1시간에 마쳤지만, 이를 slicing·toolpath·할당 설계의 예상 시간으로 환산하지 않는다(K6).

