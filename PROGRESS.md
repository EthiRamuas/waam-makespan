# PROGRESS.md

## 현재 상태 (체크포인트 갱신)
- 단계: **1단계 종료.** 2단계(B′, C-23) 진행: slicing → lower_bound(야간) → 안전망 탐침(모델 03, `experiments/`) + 형상 판정식 확인(완료, C-24 확인 결과) + 해칭 간격 스윕
- 통과 테스트: 394 passed (Claude 실측, 10-10 16:14, 작업 8 반영 후)
- 막힌 곳: 없음. 결정 대기: C-06, C-15(데드라인: 4단계 첫머리), C-21(run_all 설계 때), C-24(coverage 활용, 데드라인: 3단계 toolpath 설계 시작 전), C-25(비공개 모델 메시 repair, 15주차 전)
- 다음 작업(B′ 순서): 작업 9(읽기 전용 분석, .cache/waam/analysis/) → (18:40 이후) slicing → lower_bound 래퍼 → 안전망 탐침 + 해칭 간격 스윕 → (3단계) toolpath v0 → baseline_sector → run_all
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
| 2026-10-10 14:45 | 작업 5 완료: results.py + 스키마 테스트, 리뷰(waam-reviewer, 약 5분 33초) 지적 10건 중 5·6·7(일부)·8·10번과 2번 문서화 반영, 1·3·4·9번은 C-19/C-20으로 이월. pytest 273 passed 1 xfailed |
| 2026-10-10 14:50–14:54 | C-20(0959290, 14:50) · C-19(3b8da00, 14:53) 별도 커밋으로 반영. lower_bound 명세 작성(e8a8fcb, 14:54; 읽기 전용 측정: 6개 모델 하한이 spec 표와 일치) |
| 2026-10-10 14:57 | C-22 결정 반영(8b51481): lower_bound 명세 확정(한계 §4 명시), 모델 05 재측정(80,953.5032 s, Validator 함수 결과). 야간 큐 자격 재판정: 명세 ✓ / ★4 승인만 남음 |
| 2026-10-10 15:32 | 사용자 결정: 2단계 범위 B′ (C-23) |
| 2026-10-10 15:42 | 작업 6: C-23·C-24·C-25 기록, C-15 데드라인 갱신, lower_bound §4 문구 수정, Validator 형상 판정식 읽기 전용 확인 |
| 2026-10-10 16:03 | ★3 승인(수정 3건 반영, auto). 작업 8(lower_bound_from_areas) 시작 |
| 2026-10-10 16:14 | 작업 8 완료: lower_bound_from_areas + 테스트 106건, 리뷰(waam-reviewer 약 6분15초) 지적 8건 반영, 전체 pytest 394 passed(76.37 s). 체크포인트 커밋 직후 작업 9(.cache/waam/analysis) 착수 |
| 2026-10-10 16:15 | 작업 9 시작(읽기 전용, 결과 .cache/waam/analysis/, 커밋 없음) |
| 2026-10-10 16:17 | 작업 9 완료(읽기 전용, 결과 .cache/waam/analysis/REPORT.md, 커밋 없음). 발견: CLAUDE.md의 도달범위 구조(41.2/55.6/3.2/0%)는 workspace 원판 기준(측정 0/41.24/55.58/3.18%), 부품 단면 기준은 모델마다 다름(전용 면적: 01·02·03·06 0%, 04 2.3%, 05 27.1%); 모델 03 층당 루프 10 vs spec §8-3의 9.0(원인 미확인) |
| 2026-10-10 | 작업 10 완료 18:41(터미널 표시), 소요 1분 8초, 사용량 미보고. 문서만 수정(CLAUDE.md 도달범위 정정, docs/measurements/reach_analysis.md, DECISIONS C-26, PROGRESS 미결), 커밋 1141271 |

## 미결 항목 (작업 10·10-1 등록)
- 모델 03 윤곽 개수 불일치: 작업 9 측정 층당 루프 10(폴리곤 1 + 홀 9) vs `docs/spec.md` §8-3의 9.0. 원인 **미확인**. 확인 전에는 `docs/spec.md`를 수정하지 않는다.
- `docs/operations.md` §6-3의 단계 정의(2단계 lower_bound·runner·tests / 3단계 slicing·toolpath·baseline / 4단계 설계)가 C-23(2단계 B′, 3단계 toolpath v0→baseline_sector→run_all)과 다르다. 수정하지 않았다(C-23 기준이 현재 기준).
- CLAUDE.md "도달범위 구조"의 배분 골격은 원판 기준 수치에 기대고 있어 부품 기준 재검토 필요 표시를 넣었다. 새 배분 방침은 없다(C-26 입력 메모).
- 구 도달범위 문구(41%/56%, 원판 기준 수치)가 `docs/spec.md`, `docs/playbook.md`, `docs/operations.md`, `.claude/agents/waam-architect.md`에 남아 있다. 수정하지 않았다. 특히 `waam-architect.md`는 에이전트 프롬프트라 정정 우선순위가 높다. `docs/spec.md`는 교수 제공 명세와의 관계를 확인한 뒤에만 수정한다.

## 일정
- 중간평가 10/20(화): 진행 상황 평가. 3단계(toolpath v0 → baseline_sector → run_all)의 목표 시점이다.
