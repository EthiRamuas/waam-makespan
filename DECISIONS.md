# DECISIONS.md — 코드 결정 로그

번호 규칙: 이 파일의 결정은 **C-xx**. `docs/handoff.md` §4의 D-xx(운영 설계 결정)와 겹치지 않는다.
필드: 일시 / 등급 / 문제 정의 / 충족 조건 / 선택지 / 권고·기본안 / 결정 책임자 / 데드라인 / 영향 받는 자 / 알아야 할 자 / 되돌림 비용 / 상태 / 결과

## 결정 완료

### C-01 — Validator 대조 테스트 36건 실패: 환경 복구
- 일시: 2026-10-10 (13:28 이후, ★1)
- 등급: B (사용자 결정)
- 문제 정의: `.venv`의 polars가 `Polars binary is missing!` → Validator 로더 `NameError: PyDataFrame`, pytest 115 passed / 36 failed (실측).
- 선택지: a) polars만 재설치/핀 고정 b) .venv 재생성 c) 다른 머신에서 검증
- 결정: **a 방향으로 진행**. 실제 조치는 사용자가 수동으로 수행.
- 결과: 원인은 Windows 스마트 앱 컨트롤이 `_polars_runtime.pyd`를 차단한 것. SAC를 끄고 `import polars` 정상 확인. **pytest 151 passed in 76.56s (사용자 보고, Claude 재측정 아님).**
- 상태: 결정
- 메모: 이 환경에서 새로 설치되는 `.pyd`도 같은 차단을 받을 수 있다(미확인).
- 원래 ★1 메모에서의 이름은 D-01. handoff.md D-01과 겹쳐 C-01로 옮겼다.

### C-02 — PROGRESS.md / DECISIONS.md 초기화
- 일시: 2026-10-10 (★1)
- 등급: B
- 선택지: a) 프롬프트 2에서 첫 작업으로 초안 생성 b) 직접 작성 c) 없이 진행
- 결정: **a**. DECISIONS.md는 이 기록으로 생성됨. PROGRESS.md 초안은 ★2 계획의 첫 항목.
- 상태: 결정 (PROGRESS.md는 승인 후 생성)
- 원래 ★1 메모에서의 이름은 D-02.

### C-03 — writer의 좌표·시간 기록 방식
- 일시: 2026-10-10 13:32 (★2) | 등급: B | 결정: **a) repr 그대로** | 상태: 결정
- 이유: 자릿수를 자르면 float32 동등성이 깨짐(handoff 기록).

### C-04 — 스케줄러/writer 호출 규칙을 CLAUDE.md에 추가
- 일시: 2026-10-10 13:32 (★2) | 등급: B | 결정: **a) CLAUDE.md에 추가** | 상태: 결정
- 결과: `CLAUDE.md` 작업 규칙에 한 단락 추가함(미커밋 → 작업 1에서 커밋).

### C-05 — 모델 01 config를 tests/fixtures로 복사
- 일시: 2026-10-10 13:32 (★2) | 등급: B | 결정: **a) config만 복사 + md5 일치 테스트**
- 단서(사용자 지시): settings의 `Edit(**/config.yaml)` deny로 막히면 우회하지 말고 멈춰서 알린다. 복사는 사용자가 PowerShell로 직접 한다.
- 상태: **완료.** 사용자가 `tests/fixtures/model01/config.yaml`을 복사함(md5 bf3b30c6… 일치, Claude도 `md5sum`으로 확인). 일치 테스트: `tests/test_fixtures.py`. Claude는 복사를 시도하지 않았다(deny 규칙이 해당 경로를 덮는다는 것을 settings.json에서 확인).

### C-08 — timing 입력 단위
- 일시: 2026-10-10 (★2 이후) | 등급: B | 결정: **a) Step(pass/travel/wait) 방식** | 상태: 결정
- 이유: 시간 채우기를 한 곳(timing)에 둔다. 이음매는 이전 끝값을 그대로 이어받아 정확한 float 동등성을 보장한다.

### C-09 — 아크 W의 위치
- 일시: 2026-10-10 (★2 이후) | 등급: B | 결정: **a) pass 시작점에서 arc_on(W) → D들 → 끝점에서 arc_off(W)** | 상태: 결정

### C-10 — travel 시간 = 길이/150 mm/s
- 일시: 2026-10-10 | 등급: A (기본안 진행) | 상태: 기록만, 진행. 되돌림 비용 낮음(build_chain 한 곳).
- 근거: Validator는 travel 속도를 상한(150×1.1)만 검사한다.

### C-11 — D/T 구간 시간은 float32 양자화한 길이로 계산
- 일시: 2026-10-10 | 등급: A (기본안 진행, 구현 중 발견) | 상태: 기록만, 진행. 되돌림 비용 낮음.
- 근거: Validator는 float32로 읽은 좌표로 속도를 계산한다. 원 좌표 길이로 시간을 정하면 짧은 구간에서 8 mm/s ±10%를 벗어날 수 있다. `prevalidate.quantize_f32`를 재사용한다.

### C-12 — model01 config fixture 줄바꿈 변환 금지
- 일시: 2026-10-10 13:5x | 등급: B | 결정: **a) `.gitattributes`에 `tests/fixtures/model01/config.yaml -text` 추가** | 상태: 완료
- 결과: 커밋 213b23a. `git ls-files --eol`: `i/lf w/lf attr/-text`. 커밋된 바이트 md5(`git show HEAD:…`) = bf3b30c6e762bcc93ff44d8f80bcb46d (원본과 일치, 읽기 전용 확인). fixture 파일은 삭제·재체크아웃하지 않았다.

### C-13 — writer 좌표 문자열 형식
- 일시: 2026-10-10 14:0x | 등급: B | 결정: **a) 좌표는 `repr(float(np.float32(v)))`, 시간은 `repr(float)`** | 상태: 결정
- 이유: 지금까지의 Validator 대조 테스트(수천 건)가 이 형식(`vref.write_csv`)으로 돌았다. 단 `vref.write_csv`는 Windows에서 CRLF로 쓰므로 writer는 LF로 쓰고, 테스트는 CRLF를 LF로 바꾼 뒤 바이트 일치를 확인한다.

### C-14 — 작업 4 "1단계 종료 검증"의 대상
- 일시: 2026-10-10 14:0x | 등급: B | 결정: **a) sample_job을 build_chain + writer로 재현해 `waam-validator run` 전체 검증** | 상태: 결정
- 조건(사용자): (1) arc=0 `TimingParams`는 테스트 파일 안에서만 명시적으로 만들고 주석에 "레퍼런스 재현용, 제출 경로 아님"을 적는다. `src/`와 `from_config`의 아크 필수 규칙은 그대로 둔다. (2) 완료 기준은 writer가 쓴 CSV로 `waam-validator run` 전체 exit 0이다. reference CSV와의 바이트 일치는 요구하지 않는다.

### C-16 — 남은 시간의 사용처
- 일시: 2026-10-10 14:2x | 등급: B | 결정: **a의 변형** | 상태: 결정
- 내용: 작업 5(results.csv 스키마)만 진행한다(인터페이스 제안 → 사용자 승인 → 구현 → 리뷰 → 커밋). `slicing.py`는 구현하지 않고 명세만 코드 없이 올린다(야간 큐 후보 심사용). toolpath 설계는 하지 않는다.
- 근거: toolpath(해칭·아크 스트라이크 수)는 해공간을 정하는 결정이라 하루 계획 안에서 서두르지 않는다.

### C-17 — results.csv 추가 컬럼과 passed 의미
- 일시: 2026-10-10 14:4x | 등급: B | 결정: **a) 필수 6컬럼 + 추가 7컬럼(run_at, commit, seed, lower_bound_s, validator_status, validator_version, notes); passed는 Validator PASS일 때만 True, 미실행이면 비움** | 상태: 결정
- 추가 요구: `results.py`의 `compute_s` 정의를 docstring에 적는다("우리 알고리즘 실행 시간, Validator 실행 시간 제외").
- 작업 5 인터페이스(`ResultRow`, `make_row`, `append_result`, `read_results`) 승인.

### C-18 — slicing 명세 후보 결정
- 일시: 2026-10-10 14:4x | 등급: B | 상태: 결정 (명세: `docs/specs/slicing.md`)
- 1) **재구현.** Validator import는 오라클 테스트에만.
- 2) 출력은 **shapely 객체.**
- 3) 메시 결함은 **우선 raise** (repair는 필요해질 때 결정).
- 4) 캐시는 **`.cache/waam/slicing/`** + `.gitignore`에 `.cache/` 한 줄 (dc76f73).
- 5) 부피 오차는 **야간에 단언하지 않고 측정·기록만.** 통과/실패는 오라클 2·3으로만 판정.
- 읽기 전용 확인(2026-10-10, 수정 없음): 모델 01~06 `target.stl`은 trimesh 기본 처리(정점 병합) 후 **6개 모두 watertight, winding 일치.** 원본 그대로는 모두 False(STL이 면마다 정점을 따로 저장). zmax = 12, 16, 12, 100, 700, 102 mm → 층 수 ceil(zmax/2) = 6, 8, 6, 50, 350, 51로 spec 표와 같다.

### C-22 — lower_bound 명세 결정 (docs/specs/lower_bound.md)
- 일시: 2026-10-10 14:57 (커밋 8b51481) | 등급: B | 상태: 결정 (명세 확정, ★4 승인 대기)
- L-1) **정의 그대로 구현한다.** 한계(완전 채움 가정, 형상 기준을 만족하는 범위에서 덜 채우면 ratio<1 가능)를 명세 §4와 보고서 항목에 명시한다. coverage 활용은 **별도 전략 결정(C-24)으로 남긴다.**
- 정정(2026-10-10, C-24 "확인 결과"): 이 결정을 적을 때의 "coverage 80%면 PASS"는 판정식 확인 전의 표현이었다. 실제로 최소 채움 비율을 정하는 것은 전체 IoU 0.9다(coverage 0.8은 구속하지 않는다).
- L-2) **순수 함수(`lower_bound_from_areas`)와 래퍼(`lower_bound`)로 분할.**
- L-3) **로봇 수는 `len(config.robots)`에서 읽는다.**
- L-4) **아크 하한은 toolpath 이후로 미룬다.**
- C-21(config·target sha 대조)은 run_all 설계 때 결정한다. 변경 없음.
- 보충 측정(읽기 전용, 05 재측정): 하한 80,953.5032 s (22.4871 h), Validator 함수 결과이며 우리 구현이 아니다.
- L-5) (2026-10-10 15:48, 등급 A: 시그니처 불변·테스트 한정) 래퍼의 `config`는 Validator config **또는** `.robots`(길이를 가진 시퀀스)와 `.process.bead_width_mm`, `.process.deposition_speed_mm_s`를 가진 객체다. 오라클 7은 `SimpleNamespace` 등 대체 객체로 2대/4대를 만들어 `len(config.robots)` 사용을 확인하고, 실제 Validator config(3대)로 한 번 더 확인한다. 근거: Validator `config/models.py`의 `robots`가 정확히 3대만 받는다(작업 6 확인). 야간 큐 자격 ②는 여전히 ✓.

### C-23 — 2단계 범위 = B′ (단계 재정의)
- 일시: 2026-10-10 15:32 (사용자 결정, 앱 채팅에서 강의자료·녹취를 근거로 검토) | 등급: B | 상태: **결정**
- **2단계:** slicing → lower_bound(야간) → 안전망 탐침(모델 03, `experiments/`, `src/` 아님) + 형상 판정식 확인 + 해칭 간격 스윕. 종료 기준: 실제 config 경로로 Validator PASS 1회 + coverage 안건(C-24)의 실측 근거.
- **3단계** (목표: 중간평가 10/20(화) 전, 중간평가는 진행 상황만 봄): toolpath v0 → baseline_sector(3대, 섹터 전용, 층 동기화) → run_all(C-21 결정). 종료 기준: 공개 6개 모델 전부 PASS + results.csv에 ratio.
- **4단계** (9주차 이후): 층 동기화 제거·파이프라이닝 → precedence.py + C-15 → Local Search / SA / GA 등 → 비공개 모델 일반화 시험.
- 근거(강의자료): Validator 미통과는 Fail로 점수 제외 · 평가자 재현 기준 · 평가 = makespan + 계산 시간(학습 제외) + 일반화(공개 6 + 비공개 N) · 상용 SW 교차 검증 · 9주차 이후 강의 순서(Greedy+LS → SA → GA → NCO).
- 이전 단계 정의(`docs/operations.md` §6-3: 2단계 lower_bound·runner·tests / 3단계 slicing·toolpath·baseline / 4단계 설계)와 달라졌다. 충돌하는 문서 수정은 이번 작업의 범위가 아니며 이 기록이 현재 기준이다.

### C-26 — 부품 기준 도달범위: 3단계 toolpath·C-24 설계 입력 메모
- 일시: 2026-10-10 | 상태: **입력 메모(결정 아님)** — B등급 결정이 아니므로 결정 형식은 쓰지 않는다. 새 배분 방침도 정하지 않는다.
- 근거: 작업 9 측정, `docs/measurements/reach_analysis.md` (원본 `.cache/waam/analysis/REPORT.md`, 미커밋). CLAUDE.md의 41.2/55.6/3.2/0%는 작업공간 원판(반경 700) 기준이며 부품 기준이 아니다.
- 입력 1) 3단계 toolpath 설계: 부품 기준 전용(1대) 면적은 모델 04(2.3%)·05(27.1%)에만 있고 01·02·03·06은 0%다. segment 도달 가능 로봇 집합이 모델마다 크게 달라진다(예: 06은 2대 6.3% / 3대 93.7%, 05는 3대 0%). toolpath가 segment마다 도달 가능 로봇 집합을 남겨야 하는지는 설계 때 정한다.
- 입력 2) C-24(coverage 전략)의 안전망 탐침: 프로브 대상을 모델 03에서 **모델 06으로 바꿔야 한다.** 03은 1대로 도달 불가(여유 -82.5/-85.5/-71.4 mm)라 1대 단독 경로로 PASS를 볼 수 없고, 06은 로봇 1 한 대로 전체 도달 가능(여유 +33.9 mm)이다. 06은 단일 윤곽(층당 루프 1.0)이라 해칭 간격 스윕에도 단순하다(후자는 추정).
- 입력 3) 한계: 도달 판정은 단면 폴리곤 기준이다. 중심선 기준과 약 4 mm 차이 가능성은 미분석이다. 06의 +33.9 mm 여유가 이 차이보다 크다는 것은 산술이며 중심선 기준 실측은 아니다.
- 미측정: 부품 기준에서 "전용 부하 먼저, 공유 영역으로 상쇄" 골격이 유효한지, 도달 분할이 makespan에 주는 영향.

### C-27 — slicing 구현의 명세 밖 판단 추인 (3건)
- 일시: 2026-10-10 | 등급: C(기록) | 상태: **결정 (사람 추인)** | 대상: `src/waam/slicing.py` (야간 Q1, 커밋 de7c96b)
- (a) **법선(winding) 정리·body count 생략.** `docs/specs/slicing.md` §3은 전처리 끝에 "법선 정리"를 적었으나 구현은 하지 않는다. 판단: 단면 선분 집합은 방향을 제외하면 같고 even-odd 합집합(대칭차)은 방향과 무관하다 — **가설**. 알려진 한계: 혼합 winding 메시에서 WKB 정점 순서와 면적이 ulp 수준에서 달라질 수 있다(리뷰어 실측 3.6e-12 mm², 모델 01의 면 절반을 뒤집은 경우; **우리가 재현하지 않았다**). 균일 winding은 리뷰어 실험에서 WKB 동일. 또한 Validator `repair_normals_and_count_bodies`가 방향을 결정할 수 없을 때 raise하는 검사도 **하지 않는다**(Validator는 거부하고 우리는 통과시킬 수 있는 경로, 재현 메시는 못 만듦 — 추정).
- (b) **build plane 아래 메시 거부** (`TARGET_BELOW_BUILD_PLANE`). 명세에 없던 가드다. **조건부 추인:** Validator `target.py` 81–85행의 `TARGET_TRAJECTORY_FRAME_MISMATCH`와 같은 조건인지는 **미확인**(비교식 `bounds[0,2] < build_plane_z − geometry_epsilon`이 텍스트로 같아 보이는 것까지만 읽었고, 같은 입력에서 같은 판정을 내는지 동등성 테스트는 하지 않았다). 다른 조건으로 드러나면 **가드를 삭제한다.**
- (c) **캐시.** 키에 소스 파일 sha256과 라이브러리 버전(shapely·GEOS·trimesh·numpy)을 포함하고(명세 §4는 STL sha256 + 5개 파라미터 + 알고리즘 버전 상수), 캐시 쓰기의 `OSError`는 삼켜서 슬라이싱 결과를 돌려준다. 근거: 야간 리뷰 3번·1번 지적.
- 후속: (b)의 동등성 테스트(PROGRESS 미결, 야간 큐 후보). 명세 문서 반영은 작업 11.

### C-07 — docs/experiments.md는 사람이 작성
- 일시: 2026-10-10 13:32 | 등급: C | 결정: **그대로 유지** | 상태: 결정

## 결정 대기

(handoff.md §3 "결정 대기 (사용자) 5건"을 옮김. 근거 시점 10-07 01:11 문서 기준.)

### C-06 — Lipschitz 여유 `max_step_mm=2.5` 유지 여부
- 등급: B | 상태: **대기** (다음 구간으로 이월)
- 내용: 근접 통과 오거절률은 실제 스케줄이 생긴 뒤 측정할 수 있다. 지금은 측정 불가.

### C-15 — writer 게이트에 선후관계·아크 검사를 둘지
- 등급: B | 상태: **대기 유지** (작업 3 리뷰에서 발생) | **데드라인: 4단계 첫머리, 층 동기화 제거 직전** (2026-10-10 갱신, C-23)
- 갱신 이유: 3단계 `baseline_sector`는 층 동기화(층 k의 모든 D가 끝난 뒤 층 k+1의 D 시작)로 국소 선후관계를 구조적으로 보장한다. 따라서 3단계에서는 writer 게이트에 선후관계 검사가 없어도 위반이 나갈 수 없다. 이 동기화 불변식을 테스트로 단언하는 것을 `baseline_sector`의 완료 기준에 넣을 예정이다(아직 구현·명세 없음). 층 동기화를 제거하는 순간부터 구조적 보장이 사라지므로 그 직전에 결정해야 한다.
- 문제 정의: 현재 writer 게이트는 Validator 의미(`check_all`)와 타임라인-체인 동일성만 본다. 아크 W와 국소 선후관계는 보지 않는다. 아크는 timing.py만 보장하고 `precedence.py`는 아직 없다.
- 선택지: a) 3단계에서 `precedence.py`를 만든 뒤 writer 게이트에 연결 b) 스케줄러 쪽에서만 보장 c) 연결하지 않음
- 권고(초안): a — 제출 경로의 마지막 게이트가 우리가 부과한 제약을 보지 않으면 "Validator만 통과하는 비물리 해"가 나갈 수 있다. 단 precedence.py 설계 이후에 정할 수 있으므로 지금은 결정하지 않는다.

### C-19 — results.csv의 passed가 거짓으로 채워질 수 있는 경로 (작업 5 리뷰 1·6번)
- 등급: B | 상태: **결정: a** (2026-10-10) — `make_row`에 `trajectory_path` 필수, `summary_path.name == "summary.json"` 요구, summary 폴더의 `validation_inputs.json`의 `inputs["trajectory.csv"].sha256`과 `trajectory_path`의 sha256을 대조(다르면 raise). config.yaml·target.stl sha 대조는 넣지 않고 C-21로 남김. (원래 상태: 대기)
- 문제 정의: `make_row(summary_path=...)`는 그 summary.json이 *이번* trajectory.csv의 결과인지 확인하지 못한다. 이전 run·다른 모델·다른 config의 PASS가 새 해에 붙을 수 있다("돌리지 않은 것을 돌렸다고 쓰지 않는다" 위반 경로). 호출자(run_all)가 아직 없어 실제 피해는 없다(추정).
- 충족 조건: 기록된 PASS가 해당 trajectory.csv를 실제로 검증한 결과임이 코드로 강제된다.
- 선택지: a) `make_row`에 `trajectory_path`를 필수 인자로 추가하고 summary와 같은 폴더의 `validation_inputs.json`의 `trajectory.csv` sha256과 대조(다르면 raise). 필요하면 config·target sha256도 대조  b) 현행 유지 + docstring 경고만  c) ERROR(error.json)를 별도 경로로 받는 정책까지 함께 정함
- 권고(초안): a — 인터페이스(C-17로 승인된 시그니처)가 바뀌므로 승인이 필요하다. ERROR 처리(c)는 호출자가 생길 때 정해도 된다.
- 현재 상태: 코드는 ERROR 등 PASS/FAIL이 아닌 status를 거부한다. docstring에 한계를 적었다.

### C-20 — waam-status 한 줄 명령 / results.csv 줄바꿈 (작업 5 리뷰 3·4·9번)
- 등급: B | 상태: **결정: a** (2026-10-10) — 한 줄을 `d[(d.passed==True)&d.ratio.notna()]`로, `read_csv`에 `dtype={'model':str,'commit':str,'algo':str}`, `operations.md` §2-4와 `.claude/skills/*/SKILL.md` 모두 수정, `.gitattributes`에 `experiments/results.csv text eol=lf` 추가. xfail 표시 제거. (원래 상태: 대기) (`.claude/skills/*/SKILL.md`와 `docs/operations.md`, `.gitattributes`를 건드려야 해서 임의로 하지 않음)
- 문제 정의: (1) `waam-status`의 모델별 최고 기록 한 줄이 PASS 행의 ratio가 비어 있으면 `idxmin ... all NA`로 죽고 "(집계할 기록 없음)"이라고 거짓으로 출력한다. `lower_bound.py`가 없는 지금 첫 Validator 실행 행은 ratio가 비어 있을 가능성이 높다(실측: 합성 행으로 재현, 테스트가 xfail로 고정). (2) autocrlf=true 환경에서 results.csv를 커밋·체크아웃하면 CRLF가 되어 append가 영구 거부된다(리뷰어 실측). (3) 한 줄 출력에서 model "01"이 정수 1, 7자리 hex 커밋이 가끔 float로 표시된다.
- 선택지: a) 한 줄을 `d=d[(d.passed==True)&d.ratio.notna()]`로 바꾸고 `pd.read_csv(..., dtype={'model':str,'algo':str,'commit':str})`을 쓴다(operations.md §2-4와 SKILL.md 둘 다), `.gitattributes`에 `experiments/results.csv text eol=lf` 추가  b) 한 줄만 고치고 줄바꿈은 나중에  c) 그대로 두고 lower_bound.py 이후로 미룸
- 권고(초안): a — 세 항목 모두 작고 되돌림이 쉽다. 테스트(`test_best_per_model_survives_a_pass_row_without_ratio`)는 xfail(strict)이라 수정하면 바로 통과로 바뀌며 xfail 표시를 지워야 한다.

### C-21 — Validator 실행 결과가 공식 config.yaml·target.stl로 돌았는지 대조
- 등급: B | 상태: **대기** (run_all 설계 때 결정, C-19에서 분리됨)
- 문제 정의: C-19는 summary.json이 *이 trajectory.csv*의 결과임을 보장하지만, 그 Validator 실행이 *공식 config.yaml·target.stl*(모델 원본)로 돌았는지는 보장하지 않는다. `validation_inputs.json`에 두 파일의 sha256이 기록돼 있다(실측: sample_job fixture).
- 선택지(초안): a) run_all이 모델 원본의 sha256을 알고 있다가 `make_row`에서 대조 b) run_all이 job 디렉터리를 만들 때 원본을 그대로 복사했음을 보증하고 대조는 생략 c) 대조하지 않음
- 고려할 점: 원본 sha는 모델별 `target.stl`만 다르고 config.yaml은 6개 모두 같다(`bf3b30c6…`). 모델 목록을 코드에 박지 않고 어떻게 알려 줄지가 설계 항목이다.

### C-24 — coverage 활용 전략
- 등급: B | 상태: **대기** (사용자 결정 전까지 어떤 코드도 이 안건을 전제로 하지 않는다)
- 문제 정의: 해칭 간격·채움 목표를 완전 채움 기준으로 둘지, Validator 형상 기준의 여유를 makespan 단축에 쓸지
- 충족 조건: Validator PASS + 상용 SW 교차 검증에서 형상 성립 + 보고서의 ratio 해석이 정직
- 선택지: a) 완전 채움 고정(간격 ≤ 비드폭)  b) 채움 목표를 탐색 변수로 두고 안전 마진(IoU 목표는 실측 후) + 완전 채움 결과 병기  c) 형상 기준 경계까지 적극 활용
- 권고: **보류** — 아래 "확인 결과"와 안전망 탐침의 간격 스윕 실측 후 사용자가 결정
- 되돌림 비용: toolpath 설계 전 낮음 / 4단계 탐색 후 높음
- 결정 책임자: 사용자 | 데드라인: 3단계 toolpath 설계(plan) 시작 전 | 영향: toolpath, baseline_sector, 보고서
- 메모: `docs/specs/lower_bound.md` §4의 "기본 방침상 취하지 않는다"는 전제가 아니다(사용자 지시, 문구 삭제함).

**확인 결과** (2026-10-10, `C:\Github\WAAM_Validator` 소스 읽기만, 수정·실행 없음. 식에서 바로 나오는 것은 "확인", 추론은 "가설")

① 판정식과 등호 — 확인. `shape/metrics.py` (층별 → 전체)
- 층별 `:74` `coverage = _unit_interval(intersection_area / target_area)`, `:76` `overfill_ratio = overfill_area / target_area`, `:60` `union_area = target_area + deposited_area - intersection_area`, `:77-79` `iou = _unit_interval(intersection_area / union_area if union_area > epsilon else 1.0)`, `:80` `passed = iou >= config.shape_validation.minimum_layer_iou`
- 전체는 층 두께를 곱해 합한 체적 가중: `:102-106` `totals["target"] += target_area * height` 등, `:116` `coverage = _unit_interval(totals["intersection"] / totals["target"])`, `:118` `overfill_ratio = totals["over"] / totals["target"]`, `:119-120` `union_volume = totals["target"] + totals["deposited"] - totals["intersection"]` / `iou = _unit_interval(totals["intersection"] / union_volume if union_volume > 0 else 1.0)`, `:121` `failed_ratio = _unit_interval(failed_layers / evaluated_layers if evaluated_layers else 0.0)`
- PASS `:126-131`: `coverage >= config.shape_validation.minimum_overall_coverage and overfill_ratio <= config.shape_validation.maximum_overall_overfill_ratio and iou >= config.shape_validation.minimum_overall_iou and failed_ratio <= config.shape_validation.maximum_failed_layer_ratio` → **경계값은 통과(≥, ≤)**.
- 최종 status는 `pipeline.py:144` `if shape.coverage < thresholds.minimum_overall_coverage:`, `:149` `if shape.overfill_ratio > thresholds.maximum_overall_overfill_ratio:`, `:154` `if shape.iou < thresholds.minimum_overall_iou:`, `:158` `if shape.failed_layer_ratio > thresholds.maximum_failed_layer_ratio:`로 실패 사유를 만들고 `:368` `status = "PASS" if not failure_reasons else "FAIL"`. metrics.py의 PASS 식과 정확히 서로 보완 관계이며 정의가 다르지 않다(확인, 중단 조건 해당 없음).
- 임계값(공개 6개 config 동일, md5 `bf3b30c6…`): `minimum_overall_coverage: 0.80`, `maximum_overall_overfill_ratio: 0.30`, `minimum_overall_iou: 0.9`, `minimum_layer_iou: 0.8`, `maximum_failed_layer_ratio: 0.05`, `area_epsilon_mm2: 1.0e-06`.
- 실패 층: `:53` `if target_area <= epsilon and deposited_area <= epsilon:`는 평가에서 제외(`continue`). `:61-66` target이 비었는데 deposited가 있으면 `passed = False`, `:67-72` `elif deposited_area <= epsilon:` target은 있는데 안 쌓였으면 `coverage = 0.0 … iou = 0.0 … passed = False`. `:81-82` `evaluated_layers += 1` / `failed_layers += int(not passed)`.

② D 선분 buffer — 확인. `shape/deposition.py`
- `:28` `radius = config.process.bead_width_mm / 2.0`
- `:50-57` `line.buffer(radius, quad_segs=config.shape_validation.polygon_buffer_resolution, cap_style="round", join_style="round",)` → 선분 한 개가 만드는 폭은 `bead_width`(반지름 = bead_width/2), 끝은 둥근 캡. `polygon_buffer_resolution`은 config에서 8.

③ z → layer 배정 — 확인. `shape/deposition.py:47-48` `representative_z = float((start[2] + end[2]) / 2.0)` / `layer_index = determine_layer_index(representative_z, config)`. `shape/layer_index.py:16-19` (center) `raw_index = (representative_z_mm - process.build_plane_z_mm - process.layer_height_mm / 2.0) / process.layer_height_mm` … `layer_index = round(raw_index)`, `:21` `if layer_index < 0:` 오류, `:23-24` `deviation = abs(representative_z_mm - expected_z)` / `if deviation > config.validation.layer_z_tolerance_mm:` 오류. 평가 층 집합은 `shape/target.py:273-274` `target_count = max(0, math.ceil(target_height / config.process.layer_height_mm))` / `return sorted(set(range(target_count)) | set(deposited_layers))` — 대상 층 전부 + target 범위 밖에 쌓인 층.

④ 덜 채우고 바깥으로 안 넘칠 때 — 확인(식에서 바로)
- deposited ⊆ target이면 intersection = deposited, `union = target + deposited − intersection = target` (`metrics.py:60`, `:119`) → **`iou = intersection/target = coverage`가 성립한다.**
- 일반식: deposited = intersection + overfill이므로 `iou = coverage / (1 + overfill_ratio)`. 전체 기준을 동시에 만족하려면 `coverage ≥ 0.9 × (1 + overfill_ratio) ≥ 0.9`.
- 따라서 **전체 형상 기준이 허용하는 최소 채움 비율은 0.90(overfill 0일 때)이다.** `minimum_overall_coverage: 0.80`은 `minimum_overall_iou: 0.9`에 가려 **구속하지 않는다**(CLAUDE.md의 "Coverage ≥80%"는 틀린 값이 아니라 비구속 조건). 층별 기준(각 층 iou ≥ 0.8, 실패 층 ≤ 5%)은 전체 체적 가중 IoU 0.9를 낮추지 못한다 — 전체 조건이 별도로 걸리므로(확인).
- 이 값은 면적(체적) 기준이다. 시간으로는 이동·아크가 채움에 비례해 줄지 않는다.

가설 (실측 전; 안전망 탐침과 간격 스윕으로 검증):
1. 적층 시간이 채움 면적에 비례한다고 보면 이론상 ratio는 완전 채움 하한의 약 0.9배까지 내려갈 수 있다. 이동·대기·아크는 줄지 않으므로 실제 이득은 더 작을 것이다.
2. 둥근 캡·폭 `bead_width` 비드는 뾰족한 모서리를 채우지 못해 완전 채움 toolpath도 coverage가 1보다 작을 수 있다(그 폭은 실측 필요). 최소 0.90에 가깝게 쓰면 모서리 손실 때문에 FAIL할 수 있으므로 안전 마진이 필요하다.
3. 한 층을 통째로 생략하는 방법은 실패 층 ≤ 5%로 허용되지만, 생략 층의 체적이 전체의 약 10%(= 1 − 0.9)를 넘으면 전체 IoU에서 막힌다(균일 단면 가정).
4. 상용 SW 교차 검증에서 이 정도로 덜 채운 형상이 성립하는지는 이 확인의 범위 밖이다 — 미확인.

### C-25 — 비공개 모델용 메시 repair / fallback 정책
- 등급: B | 상태: **대기** | 데드라인: 15주차 최종 평가 전 (4단계 일반화 항목)
- 현재: C-18 결정 3(`TARGET_NOT_WATERTIGHT`로 raise)을 공개 6개와 야간 구현에서 유지한다.
- 문제 정의: 비공개 모델에 비 watertight 메시가 오면 raise = 그 모델 Fail(점수 제외).
- 선택지 초안: a) 현행 raise  b) trimesh repair 후 면적 오라클로 검증  c) Validator의 동작을 확인하고 그에 맞춤(`shape/target.py`의 `load_target_mesh`는 `attempt_target_repair`가 켜져 있으면 `fill_holes`를 시도한다 — 확인은 읽기만 한 `slicing` 명세 작업에서 함)
- 권고: 4단계 일반화 항목 착수 때 정한다.

