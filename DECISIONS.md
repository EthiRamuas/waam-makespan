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
- **보정 (C-30, 2026-10-10):** 2단계 종료 기준(실제 config PASS 1회)은 toolpath v0 뒤로 이동한다(탐침이 toolpath v0를 재사용).
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

### C-28 — 우선순위
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §1
- 문제 정의: 설계 선택이 서로 부딪칠 때 무엇을 먼저 지킬지 기준이 없다.
- 충족 조건: 평가 3축(makespan·계산 시간·일반화)과 "Validator 미통과 = Fail"을 반영하고, 자체 부과 제약이 makespan과 거래되지 않는다.
- 선택지: a) 초안 §1 출발안 그대로 b) 초안 §1 지적 1~4 반영
- 결정: **1 Validator PASS, 2 일반화, 3 makespan/ratio, 4 계산 시간, 5 구현 위험·일정(동률 깨기).** 자체 부과 제약(국소 선후관계·아크 시간·속도 규칙)은 순위가 아니라 **제약**이다. 일반화 측정 = PASS 여유 + 모델 간 ratio 편차(최대/최소). 3·4의 가중은 미공개이며 교수님께 질문하지 않는다.
- 되돌림 비용: 낮음 — 판단 기준이며 코드에 박히지 않는다.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: 모든 설계 결정 | 알아야 할 자: 팀, waam-architect
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): Validator 미통과는 점수에서 제외되므로 PASS를 최우선에 두고, 물리적 타당성 제약은 점수와 맞바꾸지 않았다.

### C-29 — C-24 마감 변경 (toolpath 파라미터 노출)
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §2-2 H2
- 문제 정의: C-24는 탐침 근거가 필요한데 마감이 "3단계 toolpath 설계 시작 전"이라 탐침(C-30: toolpath v0 재사용)과 순환 의존한다.
- 충족 조건: 순환을 끊되, C-24 결정 전에 채움 감소가 몰래 쓰이지 않는다.
- 선택지: a) 현행 마감 유지 b) toolpath를 파라미터화하고 마감을 탐침 뒤로
- 결정: **b.** toolpath는 간격 s·인셋 o·윤곽 수 n_c를 파라미터로 노출하고 **기본값은 완전 채움(s = w)**. 기본값을 벗어나는 값은 **C-24 사람 결정 전 사용 금지**. C-24 마감: "3단계 toolpath 설계 시작 전" → **"탐침 스윕 결과 후"**.
- 되돌림 비용: 낮음 — 기본값만 쓰는 동안은 a와 결과가 같다.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: C-24, toolpath, 탐침 | 알아야 할 자: 야간 세션(기본값 외 값 금지)
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 채움 정책은 실측(탐침 스윕) 전에 정하지 않았고, 그 전까지 모든 결과는 완전 채움 기준이다.

### C-30 — 탐침 생성기 = toolpath v0 재사용 (C-23 보정)
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §2-1 H3
- 문제 정의: 탐침 경로 생성기를 버리는 프로토타입으로 둘지, toolpath v0로 만들지.
- 충족 조건: 테스트 없는 코드가 `src/`에 들어가지 않고, 2단계 종료 기준(실제 config PASS 1회)을 잃지 않는다.
- 선택지: a) `experiments/` 버리는 프로토타입 b) 프로토타입을 나중에 승격 c) toolpath v0를 먼저 명세·구현하고 탐침이 그것을 씀
- 결정: **c.** 탐침 생성기 = toolpath v0(`src/`, 명세·테스트 포함). 탐침은 `experiments/`의 구동 스크립트(모델 06, 로봇 1대). **폴백:** 2026-10-13(월)까지 06 PASS가 없으면 버리는 탐침 프로토타입(a)으로 PASS 1회를 먼저 확보한다. **C-23 보정:** 2단계 종료 기준(실제 config PASS 1회)이 toolpath v0 뒤로 이동한다.
- 되돌림 비용: 중간 — 폴백 날짜로 상한을 둠.
- 결정 책임자: 사용자 | 데드라인: 폴백 판정 2026-10-13(월) | 영향 받는 자: C-23 단계 정의, toolpath, 탐침 | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 탐침과 제출 경로가 같은 toolpath 코드를 쓰므로 탐침 측정값이 제출 해의 형상 품질을 그대로 대변한다.

### C-31 — 탐침 스윕 설계
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §2-1 H4·A1~A3, §3-1
- 문제 정의: C-24 근거를 만들 스윕의 격자·측정·판정 마진·실행 규칙.
- 충족 조건: 측정값만으로 C-24 대응표(초안 §3-1)의 시나리오를 판정할 수 있고, Validator 실행 비용에 상한이 있다.
- 선택지: 격자 범위, 마진 m, 점 수 규칙 (초안 H4·A1)
- 결정:
  - 격자: s ∈ {0.9, 1.0, 1.1, 1.2, 1.3}·w, o ∈ {w/4, w/2}, n_c = 1.
  - 측정: coverage·overfill·전체/층 IoU·실패 층·PASS·D/T/W 시간 분해(`robot_metrics.csv`)·계산 시간. **판 층/벽 층 구분 보고.**
  - 판정 마진 **m = 0.03** (전체 IoU ≥ 0.93).
  - 점 수 규칙(자동): Validator 1회 ≤ 120 s면 10점, 넘으면 o = w/2 고정 5점.
  - 비작업 로봇: home 유지, 위반 시 base 쪽 첫 안전 위치(자동).
  - job 폴더: `.cache/waam/probe/<run>/`.
  - 스윕은 **개발 실험**이며 제출 알고리즘에 Validator 호출 스윕을 넣지 않는다.
- 되돌림 비용: 낮음 — 재실행.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: C-24, 탐침 스크립트 | 알아야 할 자: 야간 세션(스윕 실행은 측정만, 해석은 주간)
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 채움 정책은 사전 등록한 격자·마진으로 측정한 뒤 정했고, 제출 알고리즘의 계산 시간에는 Validator 호출이 없다.

### C-32 — toolpath v0 설계
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §2-2 H5·H6·T5·A4·A6
- 문제 정의: toolpath v0의 경로 구성·연결·출력 단위·수치 규칙.
- 충족 조건: 형상 PASS(1순위), 4단계 비차단(초안 §4), 모델별 상수 없음.
- 선택지: 초안 H5(a 윤곽+해칭 / b 동심 / c 해칭만), H6(연결 규칙·교대 각), T5(a 패스 리스트 / b 층별 폴리라인)
- 결정:
  - 경로: **윤곽 1개 + 내부 평행 해칭**.
  - 연결: **단면 안에 머무는 연결만 허용**, 층간 **0°/90° 교대**.
  - 출력: **패스 리스트**(층, 꼭짓점, 길이, 발자국, 도달 로봇 집합).
  - chord 오차 ≤ 0.1 mm (**가설값**, 탐침 1회 후 재확인).
  - 층간 리프트 **채택**, Δz = 2h (**가설값**).
  - D 비드 외곽은 workspace 반경 700 mm 안.
  - z = build_plane_z + (k+0.5)·h를 **config에서 읽음**(상수 금지).
  - (C-29) s·o·n_c는 파라미터, 기본값 완전 채움.
- 되돌림 비용: 중간 — 출력 단위(패스 리스트)는 이후 assign·schedule 인터페이스가 된다.
- 결정 책임자: 사용자 | 데드라인: toolpath 명세 작성 전 | 영향 받는 자: toolpath, baseline_sector, precedence(4단계) | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 윤곽 + 평행 해칭은 표준 구성이며, 패스 단위 출력으로 할당·순서를 경로 생성과 분리했다.
- **보정 (C-38):** 두께 ≈ w 벽은 윤곽 + 해칭 대신 medial 패스(폴백 b).

### C-33 — 적층 속도 공칭 고정
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §2-2 H7
- 문제 정의: Validator가 허용하는 속도 ±10%를 적층 시간 단축에 쓸지.
- 충족 조건: 상용 SW 교차검증에서 물리적으로 성립하고, lower_bound와 같은 기준으로 ratio를 보고한다.
- 선택지: a) 공칭 8 mm/s 고정 b) 허용폭 안에서 가속
- 결정: **a.** 적층 속도는 공칭 8 mm/s 고정. ±10% 허용폭을 속도 단축에 쓰지 않는다.
- 되돌림 비용: 낮음 — `timing`이 이미 공칭을 쓴다(현행 유지).
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: timing, ratio 보고 | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 상용 SW 교차검증과 lower_bound가 같은 공칭 속도를 쓰므로, Validator 허용 오차를 성능으로 보고하지 않았다.

### C-34 — 제출물 선택 규칙
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §2-4 A5
- 문제 정의: 여러 전략의 결과 중 무엇을 `out/NN/`에 둘지.
- 충족 조건: PASS이고 자체 제약을 만족한 결과만 후보.
- 선택지: a) 모델별 ratio 최소 b) 사람이 매번 선택
- 결정: **a.** 모델별로 PASS이고 자체 제약을 만족한 결과 중 ratio 최소를 `out/NN/`에 둔다.
- 되돌림 비용: 낮음 — 재선택.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: run_all, out/ | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 제출 해는 사전 규칙으로 선택했고 모델별 수동 선택은 없다.

### C-35 — below-plane 가드 동등성 테스트 명세 승인
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) §5, C-27 (b)
- 문제 정의: `slicing._load_mesh`의 build plane 가드(`TARGET_BELOW_BUILD_PLANE`)가 Validator `load_target_mesh`와 같은 조건인지 미확인(C-27 b).
- 충족 조건: 같은 입력에서 실패·통과가 일치함을 테스트가 보인다.
- 선택지: a) 동등성 테스트 b) 가드 즉시 삭제 c) 현행 유지
- 결정: **a.** 합성 메시 3종(build plane 아래로 ε **초과** / 정확히 **경계** / ε **이내**)을 Validator `load_target_mesh`와 우리 `_load_mesh`에 넣어 실패·통과가 일치하는지 본다. **다르면 가드를 삭제한다**(C-27 b). 구현은 **야간 큐 후보**.
- 되돌림 비용: 낮음 — 신규 테스트 추가뿐.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: slicing | 알아야 할 자: 야간 세션
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): Validator와 다른 입력 거부 조건을 두지 않도록 동등성을 테스트로 확인했다.

### C-36 — 결정 기록 양식에 "보고서 논거" 칸
- 일시: 2026-10-10 21:02~21:05 (사람 결정) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/design_plan_draft.md`(초안, 미수정) (작업 12 지시)
- 문제 정의: 결정의 근거가 보고서 작성 때 흩어진다.
- 충족 조건: 각 결정이 보고서에 쓸 한 줄을 갖는다.
- 선택지: a) 결정마다 "보고서 논거" 한 줄 b) 보고서 작성 때 별도 정리
- 결정: **a.** 결정 기록 양식에 "보고서 논거" 한 줄 칸을 둔다. 첫 적용: C-28~C-36. (`docs/prompts/_common.md` §4-1 양식 본문은 이번 작업에서 수정하지 않았다.)
- 되돌림 비용: 낮음.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: DECISIONS.md | 알아야 할 자: 모든 세션
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 설계 결정마다 근거를 같은 형식으로 남겨 보고서의 논증과 연결했다.

### C-37 — 윤곽 인셋 o의 정의 = I1 (작업 13 P1)
- 일시: 2026-10-10 21:3x (사람 결정, 작업 14) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/toolpath_v0_spec_draft.md`(작업 13 초안, 미수정) → 확정 명세 `docs/specs/toolpath.md` §9 P1
- 문제 정의: `design_plan_draft.md`는 "윤곽 인셋 o(예: 0, w/4, w/2)"만 적었고 식이 없어 두 해석(I1 중심선 기준 / I2 비드 외곽 기준)이 가능했다.
- 충족 조건: C-31 스윕 격자 {w/4, w/2}가 의미 있는 비교가 된다.
- 선택지: I1) 윤곽 중심선 = P ⊖ o  I2) 비드 외곽 = P ⊖ o (중심선 = P ⊖ (w/2 + o))
- 결정: **I1.** 윤곽 중심선 = P ⊖ o (round join). o = w/2면 비드 외곽이 경계와 일치, o = w/4면 w/4 돌출.
- 되돌림 비용: 낮음 — 구현 전.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: toolpath, C-31 탐침 스윕 | 알아야 할 자: 야간 세션
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거: C-31 스윕 격자 {w/4, w/2}가 "경계 일치 vs 돌출" 비교가 되는 유일한 정의.

### C-38 — 두께 ≈ w 벽 = medial 단일 패스 + 자동 폴백 (작업 13 P2, C-32 보정)
- 일시: 2026-10-10 21:3x (사람 결정, 작업 14) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/toolpath_v0_spec_draft.md`(작업 13 초안, 미수정) → 확정 명세 `docs/specs/toolpath.md` §0·§9 P2
- 문제 정의: 모델 01~03은 거의 전부가 두께 = w 벽이라(실측) 윤곽 오프셋 o = w/2가 중심선으로 퇴화하고, C-32 구성(윤곽 1개 + 해칭)으로는 FAIL이 예상된다(가설).
- 충족 조건: 01~03 PASS(C-28 1순위), 모델별 분기·상수 없음.
- 선택지: a) 중심선 단일 패스(kind medial)  b) o = w/2 − ε_w 윤곽(같은 선 2회)  c) 처리 안 함
- 결정: **a + 자동 폴백 b.**
  - 판정: opening(P, w/2 − ε_w)는 남고 opening(P, w/2)에서 사라지는 영역. 이 영역은 중심선 단일 패스(kind `medial`, V12 voronoi 방식).
  - 폴백(자동): 실모델 형상 테스트(명세 §8 #13)에서 01~03 중 어느 모델이든 전체 IoU < 0.93 또는 실패층 > 5%이거나, medial 추출이 예외로 실패하면 해당 영역을 b(o = w/2 − ε_w 윤곽 = 같은 선 2회)로 처리하는 모드로 전환한다. 전환 사실과 a·b 두 모드의 지표를 보고한다. 사람 승인 없이 전환 가능.
  - 모델별 분기·상수 금지. 판정은 기하 규칙으로만 한다.
- 되돌림 비용: 중간 — medial은 새 알고리즘이고 패스 종류(kind)가 하나 늘어난다.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: toolpath, 01~03 형상·makespan | 알아야 할 자: 야간 세션
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거: 01~03 벽 두께가 정확히 w(실측: opening 3.99 mm 손실 ≤ 0.01%, 4.0 mm에서 58~86%). C-28 PASS > makespan, a가 b보다 벽 적층 시간이 약 절반.

### C-39 — toolpath 명세 확정 + 야간 큐 승인(★4) (작업 13 P6)
- 일시: 2026-10-10 21:3x (사람 결정, 작업 14) | 등급: B | 상태: **결정** | 근거 문서: `docs/drafts/toolpath_v0_spec_draft.md`(작업 13 초안, 미수정) → 확정 명세 `docs/specs/toolpath.md` §9 P6
- 문제 정의: toolpath v0 명세 초안을 확정하고 야간에 구현할지.
- 충족 조건: J-1 4조건(명세 확정 + ★4, 설계 결정 없음, 자동 판정, 되돌림 가능).
- 선택지: a) P1·P2 반영해 확정 + 야간 큐 승인  b) 수정 후 재제출
- 결정: **a.** `docs/specs/toolpath.md` 확정. 야간 큐(`docs/prompts/night-2026-10-10b.md`) 승인: N1 toolpath v0 구현, N2 below-plane 가드 동등성 테스트(C-35), N3 측정 기록.
- 되돌림 비용: 낮음 — `nightly/2026-10-10b` 로컬 커밋, 병합은 사람.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: 야간 세션 | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 경로 생성 명세를 사람이 확정한 뒤에만 구현했고, 구현 합격은 사전 등록한 자동 판정(테스트·형상 지표)으로 정했다.

### C-40 — toolpath 합격 기준 재고정 (#1·#2·#5 double·#14)
- 일시: 2026-10-11 (사람 지시, 작업 15) | 등급: B | 상태: **결정** | 근거 문서: `docs/specs/toolpath.md` §8, `PROGRESS.md` "N1 미합격 기록"(측정 출처)
- 문제 정의: 야간 구현이 #1(L·w/A 0.97~1.03)·#2(coverage 0.99)·#14(03 발자국 ⊂ P)를 못 맞췄고 #5 double의 "발자국 ⊂ P"는 달성 불가였다.
- 충족 조건: 새 기준은 형상에서 산술로 유도하고, 측정값을 그대로 복사하지 않으며, xfail·skip 없이 자동 판정한다.
- 선택지: a) 유도식으로 재고정 b) 구현을 바꿔 기존 기준에 맞춤 c) 기준 삭제
- 결정: **a.** (1) #1: 구간 삭제, 100×100 산술 분해 단언 — 윤곽 4(a−2o) + 행 수×H 변 + (행 수−1)×s, 행 수 = ceil(H 변/s) = 11, 합 1372, 상대오차 0.5%. coverage ≥ 0.99·발자국 ⊂ P 유지. (2) #2: coverage 0.99 → 0.98 (측정 0.9873: 구멍 윗변 바깥 폭 2.2 mm 띠 91.7 mm² + 코너 손실, 전역 행 격자 V8의 어긋남; Validator 한도 0.80, 우리 마진 IoU 0.93 안쪽). (3) #5 double: "발자국 ⊂ P" → "P⊕ε_w(0.01 mm) 이내". (4) #14: 한도 = L_medial·(w − t_min) + 1e-6·A, t_min = 층의 medial 꼭짓점에서 경계까지 거리 최솟값×2; 한 변 초과 (w−t)/2, 양변 (w−t). 추가로 overfill 비율 ≤ 0.03(Validator 한도 0.30의 1/10).
- 되돌림 비용: 낮음 — 테스트·명세 문구뿐, 구현 불변.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: toolpath | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 합격 기준을 사전 가설값 대신 형상에서 유도한 식으로 다시 세웠고, 유도식과 실측(03 층별 t_min 7.992~, 중앙값 7.9955)을 분리해 기록했다. 근거: 폭 8 mm 비드는 두께 8 mm 미만 벽을 반드시 삐져나간다.

### C-41 — probe_driver 명세 확정과 D1~D18 결정
- 일시: 2026-10-11 (사람 결정, 작업 19) | 등급: B | 상태: **결정** | 근거 문서: `docs/specs/probe_driver.md` §10 (작업 18 초안 + 채팅 검토 반영)
- 문제 정의: C-30의 "06에서 Validator PASS 1회"를 얻는 탐침 구동 스크립트의 명세 미결 18건(D1~D18).
- 충족 조건: 구현이 명세만으로 가능하고, 근거 없는 값은 가설로 표시되며, 스윕 실행은 사람 결정 전 막힌다.
- 선택지: 명세 §10 각 행의 후보 (기본값 후보 채택 여부)
- 결정: **명세 §10의 기본값 후보를 모두 채택.**
  - D1 시각 float64 1e-6 이상, 좌표는 float32 값 | D2 충돌만 다음 주차 후보로 재시도, CSV·속도 오류는 새 run 폴더 1회 재생성 후 재현되면 중단 | D3 타임아웃 1800 s (가설) | D4 주차 로봇 W 하나, 마지막 시각 = T_end | D5 λ (0, .25, .5, .75, 1.0), z = home z (가설) | D6 첫 접근 대각선 후 하강, Δz 4 mm (가설)
  - D7 compute_s = generate(캐시 없음) + chain + prevalidate + write, 슬라이싱 제외, probe.json에 slicing_s·toolpath_s·chain_s 별도 | D8 algo = `probe_v0_robot1_only` | D9 seed 빈칸 | D10 commit = HEAD, dirty면 notes에 표시 | D11 ratio = 우리 3대 하한 기준, notes에 "ratio=ours, 3-robot lower bound, 1-robot probe"
  - D12 results.py 스키마 유지, 빠진 8항목은 probe.json | D13 v0는 `a1_points`만 기록, 스윕 실행은 사람 결정 전 금지 (C-29·C-31 관계 미결) | D14 허용 오차 0.005 (가설), 불일치는 보고만 | D15 형상 FAIL = `shape.passed == false` | D16 비교는 toolpath 발자국 기준 | D17 `experiments/probe_06.py` | D18 재시도 3회(시도 최대 4회)
  - 채팅 검토 반영: P16 모든 시도(PASS·FAIL)마다 results.csv 행(notes에 run id·시도 번호), P18·P22 PASS이나 불일치(코드 4)도 PASS로 기록, T-26 추가·T-20 개명·키 추가.
- 되돌림 비용: 낮음 — 구현 전/탐침 코드뿐.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: experiments/probe_06.py, C-31 스윕 | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 탐침의 모든 가설값(타임아웃·리프트·주차 후보·허용 오차)을 가설로 표시하고, 모든 Validator 시도를 결과표에 남기며 스윕 실행을 별도 승인으로 분리했다.

### C-42 — baseline 구조 = 포트폴리오 (전략 S 직렬 인계 + 전략 P 섹터 병렬)
- 일시: 2026-10-11 19:2x (사람 결정, 채팅) | 등급: B | 상태: **결정** | 근거 문서: `docs/measurements/design_inputs_3stage.md`(M1·M3·M5·M8), 명세 초안 `docs/specs/baseline.md`
- 문제 정의: 3단계 baseline을 섹터 병렬 하나로 둘지, 모델에 따라 병렬이 불리할 수 있는 구조를 함께 둘지.
- 충족 조건: 모델별 분기 없이 모든 모델에 같은 규칙으로 더 짧은 쪽이 선택된다. 선택이 결정적이다.
- 선택지: a) 섹터 병렬(P)만 b) 직렬 인계(S)만 c) S와 P를 둘 다 구현해 포트폴리오
- 결정: **c.** 전략 S(직렬 인계: 부품 영역에는 한 번에 1대, 인계 최소화)와 전략 P(섹터 병렬)를 모두 구현한다. 모델마다 prevalidate를 통과한 체인의 makespan(마지막 시각)이 작은 쪽을 자동 선택하고 동률이면 S. 선택은 결정적이다(실행 시간 등 비결정 요소 금지). 모든 모델에 같은 규칙이며 모델별 분기가 아니다. Validator는 제출 후보에만 부른다(C-34 유지).
- 근거(산술): 모델 01·06은 D 꼭짓점 집합 지름이 222.2 / 216.9 mm(M5)로 팔 간 요구 거리 250 mm(= 2×arm_envelope_radius + arm_clearance, config 값 100+100+50)보다 작다. 팔 간 선분 거리 ≤ TCP 간 거리이므로 두 로봇이 모두 부품 위 D·아크 W 위치에 있는 시각은 겹칠 수 없다 → makespan ≥ ΣD + Σ아크 (06: 47560/8 + 102×2 = 6149 s, 탐침 6174.84 s). 02·03은 M3에서 3대 동시 통과 표본이 20000개 중 20 / 127(0.1% / 0.6%).
- 되돌림 비용: 낮음 — 한쪽 전략을 끄면 된다.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: assign, schedule, run_all | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 공개 6모델에서 "부품이 팔 간 요구 거리보다 작으면 병렬이 불가능하다"는 산술 하한을 보이고, 병렬이 이득인 모델과 아닌 모델을 같은 사전 규칙(makespan 비교)으로 가른다.

### C-43 — P의 섹터 = base 각도 기준 섹터 + 회전 δ 자동
- 일시: 2026-10-11 19:2x (사람 결정, 채팅) | 등급: B | 상태: **결정** | 근거 문서: `docs/measurements/design_inputs_3stage.md`(M6), `docs/specs/baseline.md`
- 문제 정의: 전략 P가 부품을 로봇별로 어떻게 나누는가. 로봇 수·base 위치는 config에서 읽어야 한다(일반화 원칙).
- 충족 조건: 로봇 수·base 위치·reach를 상수로 쓰지 않는다. 공개 config(3대, 120° 간격)에서 소유 로봇이 항상 조각에 도달한다.
- 선택지: a) 균등 각도 분할 b) base 각도 기준 섹터(이웃 base 방향과의 이등분선) c) 도달 영역 기반 비용 최소화 분할
- 결정: **b.** 각 로봇의 섹터는 원점(워크스페이스 중심)에서 본 자기 base 방향을 중심으로, 각도상 이웃한 base 방향과의 이등분선까지다(공개 config에서는 120°). 근거(산술, 공개 config): 섹터 안의 점은 자기 방향과 60° 이내이고, base 거리 1400 mm·원점 반경 r ≤ 700 mm에서 base까지 최대 거리는 sqrt(1400² + r² − 1400·r) ≤ 1212.4 mm < 1500이라 소유 로봇이 항상 도달한다. 일반 규칙: 조각마다 소유 로봇의 도달을 검사하고, 못 닿으면 닿는 이웃 로봇 중 섹터 경계가 가까운 쪽으로 넘긴다(폴백, 공개 config에서 발동 0이어야 하며 테스트로 고정). 전 층 공통 회전 δ는 자동(R4)이다. 로봇 i의 base 거리 d_i·reach R_i·부품 D 꼭짓점 최대 반경 r_max로 φ_max,i = acos((d_i² + r_max² − R_i²) / (2·d_i·r_max)), δ_max = min over 로봇 i (φ_max,i − 섹터 반폭) 안의 2° 격자에서 최대 섹터 부하(D 시간 + 아크 시간)를 최소화하는 δ를 고르고 동률이면 |δ| 작은 쪽. 측정 전 기본값 δ = 0.
- 되돌림 비용: 낮음 — 섹터 정의는 한 함수.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: assign(P), 섹터 계산 | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 섹터를 config의 base 위치에서 유도해 2대·4대 cell로 일반화되고, 도달 보장을 산술로 보였다.

### C-44 — P의 경계 충돌 = 대기 안전망 + 순서 규칙
- 일시: 2026-10-11 19:2x (사람 결정, 채팅) | 등급: B | 상태: **결정** | 근거 문서: `docs/measurements/design_inputs_3stage.md`(M7), `docs/specs/baseline.md`
- 문제 정의: 섹터 경계 근처에서 인접 로봇의 팔·TCP가 충돌하는 경우를 어떻게 피하는가.
- 충족 조건: prevalidate를 통과한 체인만 쓴다. 규칙이 결정적이다.
- 선택지: a) 경계 완충 띠(조각 제외) b) 충돌 시 대기 위치로 물러나 W + 순서 규칙 c) 충돌 시 조각 재배정
- 결정: **b.** prevalidate `try_append`가 실패하면 그 로봇은 자기 방향 대기 위치(M7 규칙)로 물러나 W한다. 섹터 안 조각 순서는 부품 중심에서 먼 조각 먼저(바깥→안).
- 되돌림 비용: 낮음.
- 결정 책임자: 사용자 | 데드라인: — | 영향 받는 자: schedule(P) | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 충돌 회피를 휴리스틱 하나(대기 후퇴)와 순서 규칙 하나로 정하고 prevalidate가 건전성을 보증한다.

### C-45 — 3단계 범위·순서
- 일시: 2026-10-11 19:2x (사람 결정, 채팅) | 등급: B | 상태: **결정** | 근거 문서: C-23, `docs/measurements/design_inputs_3stage.md`
- 문제 정의: C-23의 3단계(baseline → run_all)에 toolpath 개선을 넣을지와 순서.
- 충족 조건: 중간발표(10/20) 전 공개 6모델 결과표가 나온다.
- 선택지: a) baseline → run_all b) baseline(S+P) → run_all(C-21) → toolpath v0.1(스트라이크 감소, 02 조각화 D1)
- 결정: **b.** 모두 중간발표(10/20) 전 목표.
- 되돌림 비용: 낮음 — 순서 변경.
- 결정 책임자: 사용자 | 데드라인: 2026-10-20 | 영향 받는 자: 전체 | 알아야 할 자: 팀
- 무응답 시: 해당 없음(결정됨)
- 보고서 논거 (초안, 사람 확인): 비교 가능한 baseline과 재현 가능한 일괄 실행기를 먼저 만들고, 그 위에서 경로 개선 효과를 측정한다.

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
- **마감 변경 (C-29, 2026-10-10):** 데드라인은 "탐침 스윕 결과 후"로 바뀌었다. toolpath는 s·o·n_c를 파라미터로 노출하고 기본값은 완전 채움(s = w)이며, 기본값 밖의 값은 이 안건 결정 전 사용 금지.
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

