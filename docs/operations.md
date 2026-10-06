# Claude Code 운영 설계 — WAAM IC-PBL

> 작성 2026-10-04 · **개정 rev.2 2026-10-06** · 레포 경로 `docs/operations.md`
>
> 📌 **rev.2 개정 사유** — 로컬 환경을 실제로 구축하면서 초판 설정의 **오류 5건**을 공식 문서 기준으로 바로잡았고(§2-2), 서브에이전트·스킬은 **실제로 배포한 파일 그대로** 옮겼다. 초판의 `.claude/settings.json`·스킬을 그대로 쓰면 안 된다.
>
> | # | 초판 | 문제 | rev.2 |
> |---|---|---|---|
> | 1 | `Write(...)` deny 규칙 | **무시된다** (Write 규칙은 적용되지 않음) | `Edit(...)` 규칙만 쓴다 — Edit 규칙이 쓰기 전반을 막는다 |
> | 2 | deny 경로 `C:\\Github\\...\\**` | Windows 경로 표기 오류 | `Edit(//c/Github/WAAM_Validator/**)` — 경로는 POSIX로 정규화된다 |
> | 3 | `"fallbackModel": "sonnet,haiku"` | 값은 **배열** 타입이라 문자열은 오류 | 항목 삭제 (필수 아님) |
> | 4 | 스킬 이름 `status`·`review`·`verify` | 내장 `/status`와 충돌, `/review`는 별칭 충돌, **`verify`는 번들 스킬을 대체해 커밋 전마다 자동 실행될 수 있음** | **`waam-` 접두**로 전부 개명 |
> | 5 | `` !`cmd` `` 주입 | 명령이 **비정상 종료하면 스킬 전체가 중단**, 실행에 권한도 필요 | `\|\| echo "(…)"` 폴백 + `allowed-tools` 명시 |
>
> ⚠️ **모델 이름** — 초판은 "Sonnet 5.5가 존재하는지 확인 못 했다"고 적었다. **rev.2: 존재한다**(`claude-sonnet-5-5`, 같은 계열 `claude-opus-5-5`, `claude-haiku-4-5-20251001`). 그래도 **별칭(`opus` / `sonnet` / `haiku`)을 쓴다** — 버전이 올라가도 설정이 깨지지 않는다. 세션에서 `/model`로 확인.

---

## 2. 본격 작업 전 세팅

### 2-0. 먼저 — 모델 배분에 대한 반론

제안된 배분은 이랬다.

| 역할 | 제안 모델 |
|---|---|
| 보고 받고 지시·제안 | Sonnet |
| 코드 작성·검토·수정제안 | Opus |

**이 프로젝트에서는 뒤집는 편이 낫다.** 이 과제의 난이도는 코드가 아니라 설계에 있다.

`src/` 전체가 평범한 Python이다. numpy·shapely·CSV 쓰기. 구현 난이도가 높은 구간이 없다. 판단이 어려운 것들은 전부 설계 쪽이다:

- 전용 부하 41%의 불균형을 공유 영역 56%로 어떻게 상쇄할지
- 파이프라이닝을 어디까지 허용하고 국소 선후관계를 어떤 자료구조로 강제할지
- CP-SAT 완화 문제를 어떻게 세워야 의미 있는 하한이 나오는지
- 실험 결과를 보고 "이게 할당 문제인지 순서 문제인지" 가르는 판단
- 보고서에서 taxonomy의 빈칸을 주장하는 논증

**코드가 틀리면 Validator가 FAIL로 잡아준다. 설계가 틀리면 아무도 안 잡아준다.** 그래서 비싼 모델은 "무엇을 만들지 정하는 자리"에 놓는 게 맞다.

| 역할 | 모델 | 왜 |
|---|---|---|
| **설계·전략·결과 해석·보고서 논증** | **opus** `effort: high` | 되돌리기 비싼 판단. 여기가 병목 |
| **명세 확정된 모듈 구현·리팩토링·테스트 작성** | **sonnet** | 양이 많고 판정이 기계적(테스트·Validator) |
| **로그 요약·결과표 정리·린트 수정·커밋 메시지** | **haiku** | 완전 기계적 |
| **코드 리뷰** | **opus** 서브에이전트 | 리뷰는 "무엇이 틀렸는지 찾는 설계 작업"에 가깝다 |

코드 리뷰만 원래 안대로 Opus이고, 작성은 Sonnet으로 내리고, 대신 **방향 지시를 Opus로 올리는** 구성이다. 비용은 비슷하거나 낮아진다 — 토큰 대부분은 코드 작성에서 나간다.

> 그래도 원래 안대로 가고 싶으면 그것도 작동한다. 다만 **새벽 무인 배치에서 설계 판단을 맡기지 말 것** — 모델 선택과 무관하게 위험하다 (§5).

### 2-1. 작업 디렉토리와 실행 위치 ← 가장 중요한 세팅

**Validator 레포와 우리 레포를 분리한다.** 섞으면 교수님 코드를 건드릴 위험이 생긴다.

```
C:\Github\
├─ WAAM_Validator\        ← 교수님 레포. 읽기 전용. 절대 수정 금지
│   └─ .venv\             ← (교수님 레포 자체 환경; 우리는 쓰지 않는다)
└─ waam-makespan\         ← 우리 레포. Claude Code는 여기서 실행
    ├─ CLAUDE.md          # 레포 루트, 이 이름 그대로
    ├─ .claude\           # settings.json · agents\ · skills\
    ├─ src\waam\
    ├─ experiments\
    ├─ tests\fixtures\sample_job\
    ├─ docs\              # spec · playbook · references · operations · experiments (.md)
    ├─ out\
    └─ .venv\             # 우리 환경 (validator를 -e 로 참조)
```

**실제로 구축한 순서** (상세·함정 목록은 `docs/playbook.md` §3):

```powershell
cd C:\Github\waam-makespan
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned      # 1회
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.prefix)"                # .venv 확인
python -m pip install -r C:\Github\WAAM_Validator\requirements.lock
python -m pip install -e C:\Github\WAAM_Validator --no-deps
python -m pip install scipy rtree networkx ortools pymoo matplotlib pandas pytest
waam-validator run .\tests\fixtures\sample_job           # exit 0
```

**Claude 실행** — venv를 활성화한 같은 PowerShell에서:

```powershell
cd C:\Github\waam-makespan
claude
```

초판의 `claude --add-dir C:\Github\WAAM_Validator`는 **불필요**하다. `settings.json`의 `permissions.additionalDirectories`가 같은 일을 하고(읽기), 수정은 deny가 막는다. 단, `additionalDirectories`는 **파일 접근만** 열어줄 뿐 그 폴더의 설정·스킬을 로드하지 않는다 — 그게 원하는 동작이다.

**이중 방어 (필수):**

```powershell
attrib +R C:\Github\WAAM_Validator\* /S
```

`Edit` deny는 Claude Code의 **내장 도구와 인식 가능한 bash 파일 명령**에만 적용된다. 임의 스크립트(`python -c "open(...,'w')"` 같은)가 쓰는 건 못 막는다 → OS 속성으로 한 번 더. `CLAUDE.md` 금지 규칙 4번이 세 번째 방어선이다.

**첫 실행 때 신뢰 대화상자에서 Yes** — 프로젝트의 `allow` 규칙과 `additionalDirectories`는 **워크스페이스 신뢰를 수락한 뒤에만** 적용된다.

### 2-2. `.claude/settings.json` — 배포한 실제 파일

```json
{
  "model": "sonnet",
  "effortLevel": "medium",
  "env": {
    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"
  },
  "permissions": {
    "additionalDirectories": ["C:\\Github\\WAAM_Validator"],
    "allow": [
      "Bash(python -m experiments.*)",
      "Bash(python -m pytest *)",
      "Bash(pytest *)",
      "Bash(waam-validator *)",
      "Bash(git status *)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git switch *)"
    ],
    "deny": [
      "Edit(//c/Github/WAAM_Validator/**)",
      "Edit(**/config.yaml)",
      "Edit(**/target.stl)",
      "Bash(git push --force *)",
      "Bash(git push -f *)"
    ]
  }
}
```

기본 모델을 `sonnet`으로 두고, 설계 작업에서만 `/model opus`로 올린다. 반대로 하면 평범한 구현에 계속 비싼 모델이 붙는다.

- `config.yaml` / `target.stl` deny는 **금지 규칙 1번을 기계적으로 강제**하는 장치다. 프롬프트로만 막으면 언젠가 샌다. 단, 같은 이름 파일이 `tests\fixtures\sample_job\` 안에도 있다 — 이것도 막히는 게 맞다(골든 레퍼런스).
- `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`은 기본값일 뿐이다. 서브에이전트 frontmatter의 `model`이 **우선**하므로(v2.1.251+) `waam-reviewer`·`waam-architect`는 opus로 돈다.
- `git switch *`는 `waam-sweep`이 `nightly/<날짜>` 브랜치로 옮기기 위해 허용했다. `git push`는 허용 목록에 **없다** — 제출·푸시는 사람이 한다.
- 설정 변경은 `/permissions`로 **실제 반영된 규칙을 눈으로 확인**한다.

### 2-3. 서브에이전트 — `.claude/agents/` (배포본)

리뷰와 설계를 별도 에이전트로 분리하면 모델을 역할에 묶어둘 수 있고, 메인 대화 컨텍스트를 오염시키지 않는다.

**`waam-reviewer.md`** — 코드 리뷰 (Opus)

```markdown
---
name: waam-reviewer
description: WAAM 파이프라인 코드를 검토한다. 커밋 전, 또는 새 전략 모듈을 작성한 뒤 호출.
model: opus
effort: high
tools: Read, Grep, Glob, Bash
color: red
---

너는 이 레포의 코드 검토자다. CLAUDE.md의 금지 규칙과 확정 사양을 기준으로 본다.

우선순위대로 검사한다:

1. **금지 규칙 위반** — config.yaml/target.stl 수정, Validator 레포 수정,
   특정 tests/NN 에 맞춘 하드코딩·분기·상수
2. **사양 위반** — 좌표 단위(mm), 층 z=(k+0.5)×2.0, 캡슐 ≥250mm / TCP ≥200mm,
   reach는 XY 투영만, 속도 ±10%, 마지막 행 mode=W, 시간 공백 없음
3. **스스로 부과한 제약 누락** — 국소 선후관계 검사, 아크 시간 반영
4. **탐색 성능** — 루프 안에서 waam-validator 호출, 타임스텝 루프,
   후보 평가마다 전체 재계산
5. **재현성** — 시드 고정, 전역 상태, 측정 코드의 부작용

출력은 심각도순 목록. 각 항목에 **파일:줄 + 왜 문제인지 + 구체적 수정안**.
문제가 없으면 "없음"이라고 쓴다. 억지로 찾아내지 않는다.
추측과 확인을 구분해 표기한다.
```

**`waam-architect.md`** — 설계·전략 (Opus, plan 모드)

```markdown
---
name: waam-architect
description: 할당·스케줄링 전략 설계, 실험 결과 해석, 다음 실험 설계. 코드를 쓰지 않는다.
model: opus
effort: high
tools: Read, Grep, Glob, Bash
permissionMode: plan
color: purple
---

너는 이 프로젝트의 설계자다. **코드를 쓰지 않는다.** 결정과 근거만 낸다.

판단 기준:
- 평가 3축(makespan / 계산시간 / 일반화)을 **동시에** 본다. 하나만 좋아지는 제안은 거절한다.
- 성능은 절대값이 아니라 `ratio = makespan / 이론하한`으로 말한다.
- 도달범위 구조(전용 41% / 2대 공유 56%)를 전제로 생각한다. 3자 자유 배분이 아니다.
- 적층 총량은 줄일 수 없다. 줄이는 것은 (불균형 + 이동 + 대기)뿐이다.

항상 이렇게 답한다:
1. **진단** — results.csv 숫자를 근거로, 지금 병목이 할당(③)인지 순서(④)인지
   D/T/W 비율로 가른다
2. **선택지 2~3개** — 각각 예상 효과와 비용(구현 시간 · 계산시간 증가)
3. **권고 1개** — 왜 그것인지
4. **측정 계획** — 무엇을 보면 성공/실패를 알 수 있는지 (사전에 정한다)

근거 없는 낙관을 쓰지 않는다. 모르면 "측정이 필요하다"고 쓴다.
```

**`log-summarizer.md`** — 결과 요약 (Haiku)

```markdown
---
name: log-summarizer
description: results.csv와 실행 로그를 표로 요약한다. 해석하지 않는다.
model: haiku
tools: Read, Bash
color: cyan
---

results.csv와 로그를 읽어 표로 정리한다. **해석·제안을 하지 않는다.**
모델별 ratio, 계산시간, PASS/FAIL, 직전 run 대비 변화만 낸다.
파일에 없는 숫자를 쓰지 않는다. 비어 있으면 "데이터 없음".
```

> **개선 후보 (rev.2 메모)** — 이 에이전트들은 아직 `국소 선후관계`와 `아크 시간`이 `CLAUDE.md`에 있다는 전제로 짧게 쓰여 있다. 첫 실제 리뷰에서 빠뜨리는 항목이 나오면 reviewer의 3번 항목에 구체 기준(예: "`precedence.py` 호출 없이 `schedule.py`가 segment를 확정하면 지적")을 추가한다.

### 2-4. 슬래시 명령어 — `.claude/skills/<name>/SKILL.md` (배포본)

동적 셸 주입(`` !`cmd` ``)을 쓰면 명령어 자체가 현재 상태를 끌어온다. **명령이 0이 아닌 코드로 끝나면 스킬 전체가 중단**되므로 전부 `|| echo` 폴백을 붙였다. 이름은 내장 명령과 충돌하지 않게 `waam-` 접두.

| 스킬 | 호출 | 자동 호출 | 용도 |
|---|---|---|---|
| `waam-status` | `/waam-status` | 허용 | 레포·실험 현재 상태 3줄 요약 |
| `waam-sweep` | `/waam-sweep topk 01,02,03` | **금지** | 야간 스윕 (`disable-model-invocation`) |
| `waam-verify` | `/waam-verify` | **금지** | 제출 후보 6모델 전수 검증 |
| `waam-review` | `/waam-review` | 허용 | 변경분을 `waam-reviewer`에 위임 |
| `waam-decide` | `/waam-decide <질문>` | 허용 | `waam-architect`에 설계 결정 위임 |

**`waam-status/SKILL.md`**

```markdown
---
name: waam-status
description: 레포와 실험의 현재 상태를 요약한다. 지금 어디까지 왔는지, 최고 기록이 무엇인지 물을 때.
allowed-tools:
  - Bash(git log *)
  - Bash(git status *)
  - Bash(python -c *)
  - Bash(echo *)
---

## git
!`git log --oneline -5 2>&1 || echo "(커밋 없음)"`
!`git status --short 2>&1 || echo "(git 상태 확인 불가)"`

## 최근 실험 (results.csv 마지막 10줄)
!`python -c "import pandas as pd; d=pd.read_csv('experiments/results.csv'); print(d.tail(10).to_string())" 2>&1 || echo "(results.csv 아직 없음)"`

## 모델별 최고 기록 (PASS만, ratio 최소)
!`python -c "import pandas as pd; d=pd.read_csv('experiments/results.csv'); d=d[d.passed==True]; print(d.loc[d.groupby('model').ratio.idxmin()][['model','algo','makespan_s','ratio','compute_s']].to_string())" 2>&1 || echo "(집계할 기록 없음)"`

위 상태를 3줄로 요약하고, 다음에 결정할 것 하나만 제시해.
results.csv가 없으면 "아직 실험 기록 없음"이라고만 쓰고 지어내지 않는다.
```

> ⚠️ **`results.csv` 스키마 약속** — `waam-status`·`waam-decide`는 컬럼명이 **`model, algo, makespan_s, ratio, compute_s, passed`** 라고 가정한다. 2단계에서 `results.csv`를 만들 때 **이 이름 그대로** 쓰거나, 바꾸면 이 스킬들의 `python -c` 한 줄을 같이 고친다.

**`waam-sweep/SKILL.md`**

```markdown
---
name: waam-sweep
description: 하이퍼파라미터 스윕을 실행하고 results.csv에 적재한다. 야간 배치용.
arguments: [algo, models]
argument-hint: "[topk|sector|ga] [01,02,03]"
disable-model-invocation: true
allowed-tools:
  - Bash(python -m experiments.*)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git switch *)
  - Bash(git status *)
model: sonnet
---

`$algo` 전략을 모델 `$models`에 대해 스윕한다.

1. 현재 브랜치가 `nightly/*`가 아니면 `git switch -c nightly/<오늘날짜>`로 전환한다.
   **main에 직접 커밋하지 않는다.** 커밋되지 않은 변경이 있으면 멈추고 보고한다.
2. `python -m experiments.sweep --algo $algo --models $models --seed 42`
3. results.csv에 새 기록이 적재되었는지 확인한다.
4. results.csv만 `nightly/` 브랜치에 커밋한다.
5. 아래 형식으로 3줄 보고한다.

변경: <무엇을 돌렸는지 한 줄>
측정: 모델별 ratio = 01:x.xx 02:x.xx 03:x.xx | 계산시간 xx s | PASS n/3
판단: <다음에 무엇을 결정해야 하는지 한 줄>

실패하면 **원인만 보고하고 멈춘다.** 알고리즘을 임의로 바꾸지 않는다.
측정하지 않은 값은 "미측정"이라고 쓴다.
```

**`waam-verify/SKILL.md`**

```markdown
---
name: waam-verify
description: 제출 후보를 6개 모델 전체에 회귀 실행하고 Validator로 전수 검증한다.
disable-model-invocation: true
allowed-tools:
  - Bash(python -m experiments.*)
  - Bash(waam-validator *)
model: sonnet
effort: medium
---

제출 후보를 전수 검증한다.

1. `python -m experiments.run_all --all`
2. `out/01` ~ `out/06` 각각에 `waam-validator run out/<번호>`를 실행하고 exit code를 수집한다.
3. 하나라도 0이 아니면 **즉시 멈추고** 어느 모델이 왜 실패했는지 보고한다.
4. 전부 0이면 모델별 makespan · ratio · 계산시간 표를 낸다.

**측정값만 쓴다.** 돌리지 않은 모델의 숫자를 추정하지 않는다.
Validator의 `summary.json`에 적힌 값만 기록한다.
```

**`waam-review/SKILL.md`**

```markdown
---
name: waam-review
description: 커밋 전에 변경분 코드를 waam-reviewer 에이전트로 검토한다.
allowed-tools:
  - Bash(git diff *)
---

## 변경분
!`git diff HEAD --stat 2>&1 || echo "(변경 없음 또는 커밋 이력 없음)"`

waam-reviewer 에이전트로 위 변경분을 검토하게 해.
변경이 없으면 "검토할 변경 없음"이라고만 답한다.
```

**`waam-decide/SKILL.md`**

```markdown
---
name: waam-decide
description: 실험 결과를 근거로 다음 설계 결정을 waam-architect 에이전트에게 맡긴다.
argument-hint: "[무엇을 결정할지]"
allowed-tools:
  - Bash(python -c *)
  - Bash(echo *)
---

waam-architect 에이전트에게 다음을 결정하게 해: $ARGUMENTS

최근 실험 데이터:
!`python -c "import pandas as pd; d=pd.read_csv('experiments/results.csv'); print(d.tail(20).to_string())" 2>&1 || echo "(results.csv 아직 없음)"`

데이터가 없으면 측정 계획부터 세우게 한다. 숫자를 지어내지 않는다.
```

### 2-5. 모드 사용 지침

| 모드 | 진입 | 쓸 때 |
|---|---|---|
| **plan** | `Shift+Tab` ×2 또는 `--permission-mode plan` | **설계 논의 전부.** 파일을 안 건드리니 마음껏 탐색 가능 |
| **default (manual)** | 기본 | 새 모듈 작성, 구조 변경 — 승인하며 진행 |
| **acceptEdits** | `Shift+Tab` | 명세가 확정된 반복 편집 (테스트 추가, 린트 수정) |
| **auto** | `--permission-mode auto` | 분류기가 안전한 것만 자동 승인. 긴 구현 세션에 |
| **bypassPermissions** | — | **쓰지 않는다.** 야간 배치도 allowlist로 해결 |

핵심: **설계는 plan mode에서 끝내고 나와서 구현한다.** plan에서 결론을 내기 전에 파일을 고치기 시작하면 되돌리기가 비싸다.

### 2-6. 커넥터(MCP)와 플러그인 — 거의 필요 없다

| 후보 | 판단 |
|---|---|
| GitHub | **불필요.** `gh`/git으로 충분, 제출도 git push로 끝 |
| Google Drive | 교수님 자료가 Drive에 있으면 유용. 없으면 불필요 |
| 파일시스템 MCP | **불필요.** 내장 파일 도구가 더 낫다 |
| 브라우저 | **불필요.** 논문은 이미 프로젝트에 PDF로 있다 |
| 플러그인 | **불필요** |

MCP를 붙이면 매 세션 토큰이 나간다. **이 프로젝트는 로컬 파일 + 로컬 CLI만으로 완결된다.** 실험 결과를 팀원과 Drive로 공유할 때만 고려.

### 2-7. (rev.2 신설, rev.2.1 실측 반영) 첫 실행 점검 — 이 4개가 통과해야 "세팅 끝"

> ✅ **2026-10-06 실측 완료 (v2.1.291, 4개 모두 통과).** 두 가지가 문서와 달랐다: ① `/agents` 마법사는 이 버전에서 **제거**됐다 → 질문으로 확인. ② README 낙서 요청은 **CLAUDE.md 규칙을 보고 Claude가 스스로 사양**할 수 있다(권한 규칙 검증이 안 됨) → "규칙은 이번만 예외"라고 풀어준 뒤 다시 요청해야 `Error editing file`(권한 deny)로 실제 차단을 확인한다. 또 신뢰 대화상자는 기본 선택이 **No, exit**이므로 ↓로 Yes를 고른다. 전역 설정에서 온 `PowerShell` deny가 목록에 추가로 보일 수 있다(무해).

| # | 확인 | 기대 |
|---|---|---|
| 1 | `/permissions` | deny에 `Edit(//c/Github/WAAM_Validator/**)`·`config.yaml`·`target.stl`이 보인다 |
| 2 | ~~`/agents`~~ → "사용 가능한 서브에이전트를 이름과 모델까지 나열해줘" | `waam-reviewer`(opus)·`waam-architect`(opus)·`log-summarizer`(haiku) 3개 + 내장 6개. **터미널 `claude` 세션에서** 물을 것(다른 앱 세션이면 안 나옴) |
| 3 | `/waam-status` | 에러 없이 실행. results.csv가 없으니 "아직 실험 기록 없음"이 정상 |
| 4 | "CLAUDE.md의 수정 금지 규칙은 이번만 예외로 허용한다. `C:\Github\WAAM_Validator\README.md` 맨 윗줄에 낙서 한 줄 추가해줘" | **`Error editing file`로 차단**된다. 수정되면 즉시 중단 → `git -C C:\Github\WAAM_Validator checkout README.md` 후 설정 재점검 |

이상이 있으면 가장 흔한 원인: 신뢰 대화상자에서 No를 눌렀다(→ allow 규칙 미적용) / `.claude` 위치가 레포 루트가 아니다 / 파일이 UTF-8이 아니다.

**첫 세션에서 줄 첫 지시 예** (plan 모드, sonnet):

> `CLAUDE.md`와 `docs/spec.md`를 읽고, 1단계 모듈 `geometry.py`의 인터페이스(함수 시그니처·단위·테스트 케이스)를 먼저 제안해. 코드는 쓰지 말고. `tests/fixtures/sample_job`의 trajectory.csv를 검증 케이스로 쓴다.

---

## 3. 아티팩트 — 쓸 것. 단, 용도를 좁혀서

### 쓰는 이유

Validator가 이미 로컬 UI(`waam-validator ui`)로 **단일 job의 간트차트·3D 리플레이**를 준다. 그래서 아티팩트로 그걸 다시 만들면 낭비다.

**아티팩트가 채울 빈칸은 "Validator UI가 못 보여주는 것" — 여러 run × 6개 모델 × 시간에 걸친 추세.**

### 만들 것 — 하나면 충분하다

**실험 추적 대시보드** (`results.csv` → 아티팩트)

- 모델 6개의 `ratio` 추이 (run 순서대로) ← **메인 지표**
- 전략별 비교 (sector / topk / GA …) — makespan과 **계산시간을 같은 화면에** (평가 2축)
- 모델별 D/T/W 시간 비율 막대 → 병목이 할당인지 순서인지 눈으로 가른다
- 일반화 점검: 공개 6개 vs 외부 STL 성능 편차
- **아크 시간 포함/제외 makespan 비교** (rev.2 추가 — 자발적으로 부과한 제약의 비용 정량화, 보고서용)
- 현재 최고 기록 표 (제출 후보)

### 만들지 말 것

- 단일 job 간트·리플레이 → Validator UI
- 코드 뷰어 → GitHub
- 실시간 모니터링 → 아티팩트는 정적 페이지. 야간 배치 진행은 로그로

### 운영 방식

아티팩트는 **Claude Code 터미널의 기능이 아니다.** 역할을 나눈다.

| | 어디서 |
|---|---|
| `results.csv` 생성·누적 | Claude Code (로컬) |
| 아티팩트 발행·갱신 | 이 Claude 프로젝트 / claude.ai |

새벽 배치가 `results.csv`를 갱신하고 커밋 → 아침에 이 세션에서 **같은 URL로 재발행**. 이게 **8주차·15주차 발표에 그대로 쓰인다.**

> 주의: 아티팩트는 발행 시점에 **비공개**지만 링크를 한 번 공유하면 끝이다. 제출 전 전략이 담긴 페이지를 팀 외부에 공유하지 말 것.

---

## 4. 루틴 구성

### 4-1. 무인 실행의 안전장치부터

새벽에 아무도 안 보는데 Claude가 돌아간다. **먼저 울타리를 친다.**

```powershell
claude -p "..." `
  --model sonnet `
  --allowedTools "Bash(python -m experiments.*)" "Bash(git add *)" "Bash(git commit *)" "Read" "Edit(experiments/results.csv)" `
  --max-turns 40 `
  --output-format json
```

> ⚠️ **미검증 항목 (rev.2)** — 초판은 `--permission-prompts none`, `--max-budget-usd 3.00`, `--add-dir`을 썼다. **이 플래그들이 2.1.291에 실제로 존재하는지 확인하지 않았다.** 첫 야간 배치 전에 `claude --help`로 확인하고 없는 것은 뺀다. 확인 항목:
> - 물어볼 사람이 없을 때 **프롬프트에서 멈추지 않고 거부**하는 방법 (안 걸면 밤을 날린다)
> - 비용/턴 상한 플래그 (`--max-turns`는 print 모드 전용)
> - **헤드리스 실행에서도 프로젝트 `allow` 규칙이 적용되려면** 그 폴더에서 **대화형으로 1회 실행해 신뢰를 수락**해 두어야 한다 (미리 해둘 것)

- `--allowedTools` 화이트리스트 — `--dangerously-skip-permissions`를 **쓰지 않는다.**
- `--output-format json` — 아침에 결과를 기계적으로 읽는다.
- **Windows 작업 스케줄러** 동작 조건: PC가 켜져 있고 잠자기가 아니어야 한다 / 작업 폴더를 `C:\Github\waam-makespan`으로 지정 / **venv의 python이 잡히도록** `.venv\Scripts\Activate.ps1`을 먼저 실행하거나 `.venv\Scripts\python.exe`를 직접 지정 / `claude`의 로그인 상태 유지.

그리고 **브랜치를 분리한다.**

```
main          ← 사람이 머지. 제출 후보만
nightly/*     ← 야간 배치 전용. 여기만 쓴다
```

> 🔒 **원칙: 야간은 탐색과 측정만 한다.** 아키텍처 변경·전략 설계·보고서 작성은 야간에 넣지 않는다. 아침에 검증 불가능한 결과물을 받게 된다.

### 4-2. 스케줄 (KST)

로컬 레포를 건드리는 작업은 **Windows 작업 스케줄러**가 맞다 (계산시간 측정도 로컬 고정 머신에서). **현재 상태: 아직 하나도 걸지 않았다** — 2단계(`results.csv`)가 끝나기 전에 걸면 빈 리포트만 쌓인다.

| 시각 | 루틴 | 모델 | 내용 |
|---|---|---|---|
| **02:00** 매일 | 야간 스윕 | sonnet | 전날 결정한 전략/파라미터를 `01·02·03`에 스윕. results.csv 적재 → `nightly/` 커밋 |
| **05:00** 매일 | 회귀 확인 | sonnet | 밤 결과 중 ratio 최고 후보를 `04·06`에 돌려 일반화 1차 확인 |
| **07:00** 매일 | 아침 브리핑 | haiku→opus | ① haiku가 숫자 표로 정리 → ② opus가 "오늘 결정할 것 1개"만 뽑는다. 파일로 저장 |
| **01:00** 일요일 | 주간 전수 회귀 | sonnet | `--all` 6모델 + Validator 전수. 외부 STL 일반화 점검 |
| **02:00** 토요일 | 레포 위생 | sonnet | 시드 고정·버전 드리프트·한 줄 재현 스크립트 동작 확인. 깨졌으면 리포트만 |
| **8·15주차 D-3** | 발표 동기화 | opus | results.csv ↔ 보고서 수치 일치 확인, 불일치 목록 |

**매일 돌릴 것은 02:00 / 05:00 / 07:00 셋뿐이다.** 루틴을 늘리면 아침에 읽을 게 많아져서 안 읽게 된다.

### 4-3. 아침 브리핑이 담아야 하는 것

**"오늘 결정할 것 하나".**

```
밤새 돌린 것: <전략> × <파라미터 n개> × 모델 01·02·03
최고 기록 변화: 01 1.84→1.71 / 02 2.10→2.10 / 03 1.95→1.88
실패: 없음 (또는 어느 모델이 왜)
오늘 결정할 것: <한 줄>
```

(예시 숫자는 형식 설명용이며 실측이 아니다.) 전체 표는 링크나 파일로 두고, 브리핑 본문은 이 네 줄.

---

## 5. 작업 단계 배분과 시간대

### 5-1. 배분 기준

| 버킷 | 조건 |
|---|---|
| **① Claude 예약 (무인)** | 성공 판정이 **기계적**(exit code, ratio 숫자)이고 · **되돌릴 수 있고** · **설계 결정이 없다** — 셋 다 만족 |
| **② 실시간 채팅 지시** | 명세는 확정됐지만 중간 판단이 필요. 사람이 보고 있다 |
| **③ 사용자 적극 개입** | 설계 결정 · 트레이드오프 선택 · 보고서 논증 — **되돌리기 비싼 것** |

세 조건 중 하나라도 어긋나면 ①에서 ②로 내린다.

### 5-2. 단계별 배치

| 파이프라인 단계 | 버킷 | 모델 | 모드 | 비고 |
|---|---|---|---|---|
| ① 슬라이싱 | ② → 이후 자동 | sonnet | default | 한 번 만들면 다시 안 건드린다 |
| ② 경로 생성 (해칭 전략) | ③ **설계** / ② 구현 | opus / sonnet | plan → default | 해칭 패턴이 segment 정의 = 해공간을 결정한다. **아크 스트라이크 수도 여기서 갈린다** |
| **③ 할당 — 전략 설계** | **③** | **opus** | **plan** | 전용 41% vs 공유 56% 배분 설계. **핵심** |
| ③ 할당 — 구현 | ② | sonnet | default | 설계가 확정된 뒤 |
| **④ 순서·타이밍 — 설계** | **③** | **opus** | **plan** | 충돌 회피 정책, 주차 위치, 파이프라이닝 범위 |
| ④ 구현 | ② | sonnet | acceptEdits | |
| ⑤⑥ 타이밍·CSV | ② 1회 | sonnet | default | 한 번 맞으면 끝. 골든 테스트로 고정 |
| ⑦ 검증 루프 | **①** | sonnet | — | 전수 검증은 기계적 |
| 하이퍼파라미터 스윕 | **①** | sonnet | — | **야간의 주력 작업** |
| 결과 해석 | **③** | opus | plan | 아침. 병목이 ③인지 ④인지 가른다 |
| 코드 리뷰 | ② | opus 에이전트 | — | 커밋 전 (`/waam-review`) |
| 보고서 논증 | **③** | opus | — | 평가자가 저자다. 사람이 쓴다 |
| 로그·표 정리 | **①** | haiku | — | |

### 5-3. 시간대 (KST)

```
23:30–01:00  ③ 사용자 — 오늘 결과 해석 + 내일 실험 설계 (opus, plan mode)
             └ 끝낼 때 "내일 스윕할 전략/파라미터"를 파일에 적는다 ← 야간 배치의 입력
02:00        ① 야간 스윕 시작 (무인)
05:00        ① 회귀 확인
07:00        ① 아침 브리핑 생성
기상 후       ③ 브리핑 읽고 "오늘 결정 1개"만 판단 (5분)
주간          ② 짬나는 대로 실시간 구현 지시 (sonnet)
저녁          ② 구현 마무리 + 리뷰 + 커밋
```

> **새벽은 "어제 결정한 것을 실행하는" 시간이다. 결정은 사람이 깨어 있을 때 한다.**

야간에 설계를 맡기면 아침에 **검증할 수 없는 결과물**을 받는다. 반대로 "스윕할 파라미터 목록"을 전날 밤에 확정해두면 아침에 받는 것은 **숫자**이고, 숫자는 5분에 판단된다.

### 5-4. 주차별 무게 배분

| 시기 | 무게 |
|---|---|
| 지금 ~ 1주 | ③ 개입 90% — 설계와 뼈대. 야간 자동화는 돌릴 게 없다 |
| 뼈대 완성 후 | ② 50% / ① 30% / ③ 20% — 구현과 스윕이 주력 |
| 8주차 전 2주 | ① 50% / ③ 30% — 스윕으로 숫자 쌓고, 발표 논증은 사람이 |
| 9~11주차 (SA/GA 배운 뒤) | ③ 개입 다시 상승 — 메타휴리스틱 설계 |
| 15주차 전 | ① 60% — 전수 회귀와 일반화 점검. 설계는 끝났어야 한다 |

---

## 6. 미리 짜놓을 수 있는 코드

**설계 결정이 전혀 필요 없는 모듈이 전체의 70%다.** 지금 다 만들 수 있다.

### 6-1. 지금 바로 (우선순위순) — 상태 열 추가

| # | 모듈 | 왜 지금 가능한가 | 왜 먼저인가 | 상태 |
|---|---|---|---|---|
| **1** | **`geometry.py`** | Validator 판정식 확정 — reach는 XY 투영, 캡슐은 Base→TCP 선분 최단거리 ≥250mm, TCP ≥200mm, workspace 반경 700 | 아래 전부가 이걸 쓴다 | 🔲 **다음** |
| **2** | **`prevalidate.py`** | 검사 항목과 임계값이 전부 확정 | 🔑 **가장 값나가는 모듈.** 탐색은 후보를 수천 개 평가한다. Validator를 매번 부르면 끝나지 않는다 | 🔲 |
| **3** | `segment.py` | 자료구조는 레포 문서 §9.1이 제시 | 모든 모듈의 공통 언어 | 🔲 |
| **4** | `timing.py` | 속도 8/150 mm/s, 아크 1+1s 확정 | segment → 시각. 공백 없이 채우는 로직 | 🔲 |
| **5** | `writer.py` + 자체 린터 | CSV 계약 6컬럼 확정 | ⑥ 완결. 린터가 FAIL 원인 대부분을 사전에 잡는다 | 🔲 |
| **6** | `lower_bound.py` | 계산식 확정 (Σ중심선 ÷ 8 ÷ 3) | `ratio`의 분모 | 🔲 |
| **7** | `slicing.py` | trimesh API 확정 + scipy/rtree 설치 완료 | ① 완결. STL별 결과 캐싱 | 🔲 |
| **8** | `runner.py` / `results.csv` 스키마 | 평가 3축 확정 | 야간 배치의 그릇 (**컬럼명은 §2-4의 약속**) | 🔲 |
| **9** | `precedence.py` | 부과할 제약을 이미 정의했다 | 국소 선후관계 검사기 | 🔲 |
| **10** | `gantt.py` | D/T/W 구분 확정 | 병목 진단 도구 | 🔲 |
| **11** | `tests/` 골든 테스트 | `tests\fixtures\sample_job`이 정답 레퍼런스 (**로컬 PASS 확인됨**) | 회귀 방지. tB(층 역순) 같은 반증 케이스도 고정 | 🔲 |
| **12** | `baseline_sector.py` | 120° 3분할은 결정이 필요 없다 | 비교군. 버릴 베이스라인이지만 숫자가 필요 | 🔲 |

### 6-2. 못 짜는 것 — 그러나 **인터페이스는 지금 확정한다**

`assign.py`와 `schedule.py`의 **전략 본체**는 설계 결정이 필요하다. 하지만 **프로토콜은 지금 박아둘 수 있다.**

```python
# src/waam/strategy.py — 지금 확정
from typing import Protocol, Sequence

class Assigner(Protocol):
    """③ 각 segment를 로봇에 배정한다. reach 제약을 만족해야 한다."""
    name: str
    def assign(self, tasks: Sequence[Task], cell: Cell) -> dict[int, list[Task]]: ...

class Scheduler(Protocol):
    """④ 로봇별 작업 순서·이동·대기를 정해 segment 리스트를 만든다."""
    name: str
    def schedule(self, assignment: dict[int, list[Task]], cell: Cell) -> list[Segment]: ...
```

`name`은 `results.csv`의 `algo` 컬럼에 그대로 들어가 전략별 비교가 자동으로 된다. **새 전략을 하나 추가하면 자동화가 그날 밤부터 그걸 돌린다.** 자동화를 먼저 세우고 전략을 나중에 꽂는 순서가 맞다.

### 6-3. 권하는 착수 순서

```
0단계 ✅ (완료)    환경: 두 레포 · venv · Claude Code · sample_job PASS · .claude 설정
                   └ 남은 것: docs 저장 · attrib 잠금 · 설정 커밋 · 첫 실행 4점검 (§2-7)
1단계 (오늘~내일)  geometry → prevalidate → segment → timing → writer
                   └ 끝나면: 손으로 만든 1대짜리 해가 PASS 나야 한다 ← 안전망 확보
2단계              lower_bound → runner/results.csv → tests
                   └ 끝나면: 숫자를 기록할 그릇이 생긴다 ← 자동화 가능 시점
3단계              slicing → toolpath → baseline_sector
                   └ 끝나면: 6모델 전부 PASS하는 기준선 + ratio 측정 시작
4단계 (설계 필요)   Assigner/Scheduler 프로토콜에 top k% 구현
                   └ 여기서부터 야간 스윕이 의미를 갖는다
```

> **2단계가 끝나는 순간이 자동화 시작점이다.** 그 전에 루틴을 걸면 적재할 데이터가 없어서 빈 리포트만 쌓인다. 순서를 뒤집지 말 것.

---

## 7. (rev.2 신설) 운영 중 지킬 규칙 요약

1. **커밋 트레일러** — Claude가 만드는 커밋·PR에는 세션 지정 트레일러(Co-Authored-By 등)를 붙인다. 팀 기여 추적(동료평가)에서 "누가 무엇을"을 구분하기 위해 커밋 단위를 작게 유지한다.
2. **`main`은 사람이, `nightly/*`는 야간 배치가.** `git push`는 allow에 없다 — 제출 전에 사람이 한다.
3. **설계 결정은 `docs/experiments.md`에 사람이 적는다.** "왜 그 결정을 했는지"가 거기 남는다. 야간 배치는 이 파일을 건드리지 않는다.
4. **문서 동기화** — `docs/*.md`가 프로젝트의 원본과 어긋나면 **`docs/spec.md`가 사실의 기준**이다. 수치가 바뀌면 `CLAUDE.md`·`spec.md`·이 문서 순으로 고친다.
5. **측정과 추정을 섞지 않는다** — 모든 보고는 `변경 / 측정 / 판단` 3줄, 측정하지 않은 것은 "미측정".
