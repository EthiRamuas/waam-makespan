# PROGRESS.md

## 현재 상태 (체크포인트 갱신)
- 단계: **1단계 종료.** 2단계(B′, C-23) 진행: slicing → lower_bound(야간) → 안전망 탐침(모델 03, `experiments/`) + 형상 판정식 확인(완료, C-24 확인 결과) + 해칭 간격 스윕
- 통과 테스트: 477 passed (Claude 실측, 10-10 20:04, 야간 Q2 반영 후). 야간 큐(Q1·Q2·R1·R2) 전부 종료, 막힌 곳 없음, 신호: 계속
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
| 2026-10-10 19:01경 | ★4 승인(수정 1~6 반영). 야간 큐 Q1 slicing → Q2 lower_bound 래퍼 → R1 모델 03 루프 수 조사(읽기 전용). `docs/prompts/night-2026-10-10.md` 작성. 야간 브랜치 `nightly/2026-10-10`(야간 세션이 생성), 병합은 아침에 사람이 결정 |
| 2026-10-10 19:36 | **야간 시작**(사람이 알려준 실제 시작 시각 19:36; Claude 실측 시계 19:35~19:36). 브랜치 `nightly/2026-10-10` 생성(from `session/2026-10-10`, 시작 시 `git status --short` 비어 있음). 사전 점검: `git stash list` → 출력 없음(stash 0건, 권한 프롬프트 없음); `python -I -c "print('ok')"` → `ok`(권한 프롬프트 없음). pytest -q: 394 passed (85.00 s, 19:37, Claude 실측). Q1 시작 전 |
| 2026-10-10 19:38 | **Q1 시작** (slicing, 타임박스 70분 / 2배 140분 = 21:58) |
| 2026-10-10 19:53 | **Q1 종료**: `src/waam/slicing.py` + `tests/test_slicing.py`(48건). 오라클 1(05 포함)·2·3(01~06 전부, WKB·면적 정확 일치)·4·6 통과, 오라클 5는 기록만. **모델 05 슬라이싱 시간(빈 캐시, 별도 프로세스): 6.01 s** (19:39, 기준 ≤5분이라 05를 오라클 1·3에 포함). 리뷰(waam-reviewer, 약 7분18초) 지적 9건: 1(캐시 쓰기 실패 격리·tmp 고유명)·2(키 파라미터별 테스트)·3(키에 라이브러리 버전·소스 해시)·4(fallback·SECTION_FAILED 테스트)·5·6(docstring 정정)·7(닫힘 허용오차 테스트)·8(시간 단언 → monkeypatch)·9(오라클 3에 05 포함) 모두 반영. 미반영: docs/specs/slicing.md §3의 '법선 정리' 문구에 의도된 생략 표기(명세 문서는 야간 규칙상 수정 안 함, 아침 판단). 전체 pytest 442 passed (123.84 s, skip 0), 기존 테스트 파일 변경 없음(git status: 신규 2파일뿐). 통과 후 Q2 착수 |
| 2026-10-10 19:54 | **Q2 시작** (lower_bound 래퍼, 타임박스 30분 / 2배 60분 = 20:54) |
| 2026-10-10 20:04 | **Q2 종료**: `lower_bound(stack, config)` 래퍼(`src/waam/lower_bound.py`) + `tests/test_lower_bound_wrapper.py`(35건). 오라클 2(Validator 파생값 rel 1e-9 + 명세 표는 인쇄 자릿수 반 단위; 05=80,953.5032 s 포함)·6·7 통과. 허용오차 해석: 명세 §6-2의 '표 초 값에 1e-9'는 표가 소수 첫째 자리까지만 인쇄돼 문자 그대로 충족 불가(예: 01 304.3 vs 304.272) → 위 두 갈래로 나눠 시작 전에 고정했고, 불일치 후 조정은 없음. 리뷰(waam-reviewer, 약 6분32초) 지적 6건: 1(stack TypeError→ValueError)·2(centerline/deposition 필드 단언)·3(Validator 층 목록 사용)·4(robots 문자열·dict 거부)·6(정보 없는 단언 제거) 반영. 미반영: 5(명세 §6-2 문구/DECISIONS 기록 — 명세·결정 문서는 야간에 수정하지 않음, 아침 판단), 6의 기존 test_lower_bound.py 1-2행 docstring 낡은 문구(수정 금지 파일), TYPE_CHECKING로 get_type_hints NameError(호출처 없음). 전체 pytest 477 passed (140.81 s, skip 0), 기존 테스트 파일 변경 없음 |
| 2026-10-10 20:05 | **R1 시작** (모델 03 층당 루프 수 10 vs spec §8-3의 9.0 조사, 읽기 전용, 타임박스 30분 / 2배 60분 = 21:05) |
| 2026-10-10 20:05 | **R1 종료**(시각은 시계 읽기; 이전 줄에 20:12로 적을 뻔한 추정은 쓰지 않음)(읽기 전용; 스크립트 `.cache/waam/analysis/r1_*.py`만, `src/`·`tests/`·`docs/` 변경 없음). 결과는 아래 "야간 결과" R1 문단 |
| 2026-10-10 20:06 | **R2 시작** (원판 기준 41%/56% 도달범위 문구 정정, 타임박스 20분 / 2배 40분 = 20:46) |
| 2026-10-10 20:09 | **R2 종료**: `.claude/agents/waam-architect.md`·`docs/playbook.md`·`docs/operations.md`(§6-3 단계 정의를 C-23 기준으로, 자동화 시작점 문구 포함) 정정. grep: 세 파일에서 '원판' 표시 없는 41%/56%/55.6 줄 0건. 전체 pytest 477 passed (141.60 s), 테스트 파일 변경 없음. `docs/spec.md` 미수정 |

## 미결 항목 (작업 10·10-1 등록)
- 모델 03 윤곽 개수 불일치: 작업 9 측정 층당 루프 10(폴리곤 1 + 홀 9) vs `docs/spec.md` §8-3의 9.0. 원인 **미확인**. 확인 전에는 `docs/spec.md`를 수정하지 않는다.
- `docs/operations.md` §6-3의 단계 정의(2단계 lower_bound·runner·tests / 3단계 slicing·toolpath·baseline / 4단계 설계)가 C-23(2단계 B′, 3단계 toolpath v0→baseline_sector→run_all)과 다르다. 수정하지 않았다(C-23 기준이 현재 기준).
- CLAUDE.md "도달범위 구조"의 배분 골격은 원판 기준 수치에 기대고 있어 부품 기준 재검토 필요 표시를 넣었다. 새 배분 방침은 없다(C-26 입력 메모).
- 구 도달범위 문구(41%/56%, 원판 기준 수치)가 `docs/spec.md`, `docs/playbook.md`, `docs/operations.md`, `.claude/agents/waam-architect.md`에 남아 있다. → 야간 R2(20:09)에서 `waam-architect.md`·`playbook.md`·`operations.md`는 정정함. `docs/spec.md`는 미수정(교수 제공 명세와의 관계를 확인한 뒤에만 수정). 원래 메모: 특히 `waam-architect.md`는 에이전트 프롬프트라 정정 우선순위가 높다. `docs/spec.md`는 교수 제공 명세와의 관계를 확인한 뒤에만 수정한다.

## 일정
- 중간평가 10/20(화): 진행 상황 평가. 3단계(toolpath v0 → baseline_sector → run_all)의 목표 시점이다.

## 야간 결과 (2026-10-10 야간 세션, 작성 중)

### 큐 대비 결과
| 항목 | 상태 | 시작 → 종료 (시계 읽기) | 비고 |
|---|---|---|---|
| Q1 slicing | 완료 | 19:38 → 19:53 | 리뷰 약 7분18초 포함, 타임박스 70분 이내 |
| Q2 lower_bound 래퍼 | 완료 | 19:54 → 20:04 | 리뷰 약 6분32초 포함, 타임박스 30분 이내 |
| R1 모델 03 루프 수 | 완료 | 20:05 → 20:05(분 단위 읽기) | 읽기 전용, 아래 문단 |
| R2 도달범위 문구 정정 | 완료 | 20:06 → 20:09 | 타임박스 20분 이내 |
- 세션 시작 19:36(사람이 알려준 시각), 사전 점검 `git stash list`·`python -I` 모두 권한 프롬프트 없이 실행됨.
- 모델 05 슬라이싱(빈 캐시, 별도 프로세스, timeout 600 s): **6.01 s** → 05를 오라클 1·3(및 lower_bound 오라클 2)에 포함.
- stash 목록: 0건 (`git stash list` 출력 없음, 20:09).
- `DECISIONS.md`: 이번 세션에서 보류·신규 결정을 만들지 않았다(수정 안 함).

**변경:** slicing(`src/waam/slicing.py`) + lower_bound 래퍼 + 테스트 83건 추가, R2로 문서 3개의 도달범위 문구 정정, R1 조사 기록
**측정:** 모델별 ratio = 미측정(toolpath·할당 없음) | 모델별 하한은 Validator 값과 일치(예: 05 = 80,953.5032 s) | 계산시간: 05 슬라이싱 6.01 s | Validator PASS: 미측정(이번 세션에서 Validator 실행 안 함) | pytest 477 passed (기존 394 + 신규 83, skip 0)
**판단:** 병합 전에 아래 3개 지점을 직접 보고, 명세 문서(`slicing.md` §3 법선 정리 생략, `lower_bound.md` §6-2 허용오차 해석)를 고칠지와 모델 03의 루프 수 집계 기준(R1)을 정해야 한다.

### 리뷰 지적 처리
- Q1 (waam-reviewer 9건): 반영 — 1 캐시 쓰기 실패 격리·tmp 고유명, 2 키 파라미터별 테스트, 3 캐시 키에 라이브러리 버전·소스 해시, 4 fallback·SECTION_FAILED 테스트, 5·6 docstring 정정, 7 닫힘 허용오차 테스트, 8 시간 단언 → monkeypatch, 9 오라클 3에 05 포함. 미반영: `docs/specs/slicing.md` §3 '법선 정리' 문구에 의도된 생략 표기(야간에 명세 수정 안 함).
- Q2 (waam-reviewer 6건): 반영 — 1 stack TypeError→ValueError, 2 필드 단언, 3 Validator 층 목록, 4 robots 문자열·dict 거부, 6 정보 없는 단언 제거. 미반영: 5 명세 §6-2 문구/DECISIONS 기록, 기존 `tests/test_lower_bound.py` docstring 낡은 문구(수정 금지 파일), get_type_hints NameError(호출처 없음).

### 사람이 직접 볼 지점 3개
1. `src/waam/slicing.py` `_load_mesh`: Validator와 달리 winding 정리·body count 생략, repair 없이 비 watertight는 raise, build plane 아래 메시 거부(`TARGET_BELOW_BUILD_PLANE`, 명세에 없던 가드). 혼합 winding 메시에서는 WKB 정점 순서·면적이 ulp 수준에서 달라질 수 있다(리뷰어 실측 3.6e-12 mm²).
2. `src/waam/slicing.py` 캐시: 키에 소스 파일 sha256 포함(편집할 때마다 무효화), 쓰기 실패는 삼킴(`except OSError`). 기본 캐시 위치 `.cache/waam/slicing/`.
3. `docs/operations.md` §6-3: 단계 정의를 C-23 기준으로 바꾸면서 '자동화 시작점' 문구(2단계 종료 → 3단계 종료)까지 고쳤다 — 요청 범위(단계 정의 정렬)에 포함된다고 판단했으나 해석이 갈릴 수 있다.

### R1 — 모델 03 층당 루프 수 10 vs `docs/spec.md` §8-3의 9.0
**확인** (Validator 함수 `target._horizontal_section_polygons`·`_even_odd_union`·`slice_target_layers`를 직접 호출한 실측, 스크립트 `.cache/waam/analysis/r1_loops_03.py`·`r1_all.py`·`r1_split.py`)
- 모델 03 모든 층(6)에서, 짝-홀 합치기 *전의* 닫힌 단면 루프는 9개(외곽 1 + 8)이고, 합친 *뒤* 최종 지오메트리는 폴리곤 1 + 홀 9 = 10이다. 따라서 층당 9.0 = 합치기 전 루프 수, 10 = 합친 뒤 폴리곤+홀 수와 수치가 일치한다.
- 같은 두 가지 집계를 6개 모델 전체에 적용하면, 01·02·04·05·06은 합치기 전 = 합친 뒤(8.0 / 1.0 / 5.6 / 2.0 / 1.0, spec 표와 일치)이고 03만 9.0 ↔ 10.0으로 갈라진다. 합치기 전 평균은 6개 모델 모두 spec §8-3 표(8.0 / 1.0 / 9.0 / 5.6 / 2.0 / 1.0)와 일치한다.
- 갈라지는 지점: 합치기 전 루프 중 면적 9859.10 mm²인 하나(bounds x ±80.48, y 46.5~175.42)가 자기접촉(shapely `Self-intersection[3.3333 46.5]`, `is_valid=False`)이다. 짝-홀 합치기(대칭차) 후 이 루프는 면적 4929.55 mm²짜리 홀 2개로 나뉜다(최종 홀 면적 목록에 4929.55 ×2가 있고 9859.10은 없다). 나머지 8루프(외곽 + 홀 7)는 그대로다. 합치기 전 루프끼리의 겹침은 외곽과 각 홀 사이뿐이다(홀끼리는 면적 > 1e-6 겹침 없음).
- 이 현상은 모델 03의 6개 층 모두에서 같다(층별 루프 수 10, 폴리곤 1 홀 9).

**가설** (측정되지 않음)
- spec §8-3의 9.0은 합치기 전 루프 수로 센 값일 가능성이 높다 — 수치 일치만 확인했고, spec 값을 만든 실제 계산 절차는 확인하지 못했다.
- 위 "하나의 자기접촉 루프가 홀 2개로 갈라진다"가 STL 형상(예: 한 점에서 닿는 두 삼각 공동)의 실제 특징인지, 단면 선분 연결 방식의 부산물인지는 구분하지 못했다.

**미측정**
- 이 차이가 toolpath(아크 스트라이크 수)에 주는 영향: 어느 집계가 실제 윤곽 패스 수에 맞는지 미측정(toolpath 미구현).
- 중심선(오프셋) 경로에서 이 홀 2개가 어떻게 처리되는지.
- 접촉점 (3.33, 46.5)의 이웃 층(높이 방향) 변화.

