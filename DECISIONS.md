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

### C-07 — docs/experiments.md는 사람이 작성
- 일시: 2026-10-10 13:32 | 등급: C | 결정: **그대로 유지** | 상태: 결정

## 결정 대기

(handoff.md §3 "결정 대기 (사용자) 5건"을 옮김. 근거 시점 10-07 01:11 문서 기준.)

### C-06 — Lipschitz 여유 `max_step_mm=2.5` 유지 여부
- 등급: B | 상태: **대기** (다음 구간으로 이월)
- 내용: 근접 통과 오거절률은 실제 스케줄이 생긴 뒤 측정할 수 있다. 지금은 측정 불가.

### C-15 — writer 게이트에 선후관계·아크 검사를 둘지
- 등급: B | 상태: **대기** (작업 3 리뷰에서 발생, 다음 구간)
- 문제 정의: 현재 writer 게이트는 Validator 의미(`check_all`)와 타임라인-체인 동일성만 본다. 아크 W와 국소 선후관계는 보지 않는다. 아크는 timing.py만 보장하고 `precedence.py`는 아직 없다.
- 선택지: a) 3단계에서 `precedence.py`를 만든 뒤 writer 게이트에 연결 b) 스케줄러 쪽에서만 보장 c) 연결하지 않음
- 권고(초안): a — 제출 경로의 마지막 게이트가 우리가 부과한 제약을 보지 않으면 "Validator만 통과하는 비물리 해"가 나갈 수 있다. 단 precedence.py 설계 이후에 정할 수 있으므로 지금은 결정하지 않는다.

