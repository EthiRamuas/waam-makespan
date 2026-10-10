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

### C-07 — docs/experiments.md는 사람이 작성
- 일시: 2026-10-10 13:32 | 등급: C | 결정: **그대로 유지** | 상태: 결정

## 결정 대기

(handoff.md §3 "결정 대기 (사용자) 5건"을 옮김. 근거 시점 10-07 01:11 문서 기준.)

### C-06 — Lipschitz 여유 `max_step_mm=2.5` 유지 여부
- 등급: B | 상태: **대기** (다음 구간으로 이월)
- 내용: 근접 통과 오거절률은 실제 스케줄이 생긴 뒤 측정할 수 있다. 지금은 측정 불가.
