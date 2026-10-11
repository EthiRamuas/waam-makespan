# baseline 구현 2부 측정 기록 (작업 26b, 2026-10-11)

> 값은 `.cache/waam/analysis3/`(미커밋)의 스크립트 출력이다. 해석·권고는 쓰지 않는다.
> 구분: **측정** = 스크립트 출력 / **가설** = 측정되지 않은 추정 / **미측정**.
> 스크립트: `table26b.py`(6모델 표), `diag_margin.py`·`diag_p.py`·`diag_p2.py`·`diag_s2.py`·`diag_05.py`(진단, 채택 아님), `t_reach.py`.
> 명세 `docs/specs/baseline.md`(C-46, C-47) 파라미터 그대로이다: 대기 위치 = hull 방식 최소 정수 ρ(`float32_buffer_mm` 0.001 mm), δ = 0, 재시도 조각당 n−1 = 2, 분할점 R − `float32_buffer_mm`. 조정한 값 없음.

## 1. 측정 순서와 중단

- 지시한 순서 01, 06, 03, 02, 04, 05. 각 칸 20분 상한은 어느 칸도 넘지 않았다(최대 7.70 s).
- **중단 조건에 해당:** 6모델 중 01·02·03·04·05에서 S도 P도 prevalidate를 통과하지 못했다(`BaselineError`, 결과 없음 예외). 06에서만 S가 통과했다. 이에 따라 측정은 아래 6모델 × {S, P} 표까지만 하고 멈췄다.
- Validator는 실행하지 않았고 `results.csv`에도 쓰지 않았다.

## 2. 6모델 × {S, P} (측정, `table26b.json`)

계산 시간 `compute_s` = 그 전략의 조각 분할·배정·스케줄·prevalidate(실패하면 실패한 시점까지). toolpath 생성은 별도(`toolpath_s`).

| 모델 | 전략 | prevalidate | makespan_s | compute_s | notes | 이유 (Verdict) |
|---|---|---|---:|---:|---|---|
| 01 | S | FAIL | — | 0.49 | — | S: piece rejected by prevalidate (ARM_ENVELOPE at t=170.80009536627455) |
| 01 | P | FAIL | — | 0.15 | failed_proposals=5, deadlocks=1 | P: deadlock: too many rejected proposals (ARM_ENVELOPE at t=29.899979958485275) |
| 02 | S | FAIL | — | 1.35 | — | S: piece rejected by prevalidate (ARM_ENVELOPE at t=1171.6494122960744) |
| 02 | P | FAIL | — | 1.04 | failed_proposals=3, deadlocks=1 | P: deadlock: too many rejected proposals (ARM_ENVELOPE at t=15.174862883096345) |
| 03 | S | FAIL | — | 0.13 | — | S: piece rejected by prevalidate (ARM_ENVELOPE at t=61.49398672120582) |
| 03 | P | FAIL | — | 0.25 | failed_proposals=5, deadlocks=1 | P: deadlock: too many rejected proposals (ARM_ENVELOPE at t=78.43885105720729) |
| 04 | S | FAIL | — | 0.36 | — | S: piece rejected by prevalidate (ARM_ENVELOPE at t=64.90924645125622) |
| 04 | P | FAIL | — | 0.43 | failed_proposals=4, deadlocks=1 | P: deadlock: no other robot to wait for (ARM_ENVELOPE at t=67.66527731161266) |
| 05 | S | FAIL | — | 7.70 | — | S: piece rejected by prevalidate (ARM_ENVELOPE at t=106.69689853099923) |
| 05 | P | FAIL | — | 1.83 | failed_proposals=5, deadlocks=1 | P: deadlock: no other robot to wait for (ARM_ENVELOPE at t=364.55772510029425) |
| 06 | S | PASS | 6174.838943 | 0.20 | handovers 0, retreats 0 | — |
| 06 | P | FAIL | — | 0.06 | failed_proposals=5, deadlocks=1 | P: deadlock: too many rejected proposals (ARM_ENVELOPE at t=19.958538700884617) |

`toolpath_s`(캐시 없음): 01 5.00 / 02 14.28 / 03 8.96 / 04 1.88 / 05 14.98 / 06 0.14 s.
포트폴리오 선택: 06 = S. 01~05 = 결과 없음(예외 `BaselineError`).
재시도 횟수·후퇴 횟수·교착 횟수: 위 notes 열(P 실패 칸의 `failed_proposals`, `deadlocks`). 후퇴 `retreats`는 0이었다.

## 3. 06에서 S와 탐침, W 하한 (측정)

| 값 | s |
|---|---:|
| S makespan (prevalidate 통과) | 6174.838943466011 |
| 탐침 run 1 makespan (`probe_06_run1.md`, Validator summary) | 6174.838943466003 |
| 차이 (S − 탐침) | 8e-12 |
| M8 직렬 하한 W (L/8 + 2 s × 102) | 6149.0 |
| S − W | 25.838943466011 |

01의 W(1872.25 s)와의 비교는 01에서 통과한 전략이 없어 **미측정**.

## 4. 단위 시간 (측정)

- `split_at_reach`(05, 분할점 R − `float32_buffer_mm`): 7.65 s (3593 조각; 작업 26a의 같은 함수 R + eps/2 규칙은 14.6 s였고, 측정 시점의 기계 부하가 달랐다 — 부하 차이는 미분석).
- S의 05 `compute_s` 7.70 s 중 `split_at_reach` 7.65 s. 이 S는 t = 106.7 s에서 실패한 칸이며, 통과한 S의 compute_s는 **미측정**.
- 테스트 소요: 아래 §6 (전체 pytest 마지막 한 번).

## 5. 진단 (채택 아님 — 원인 조사. 명세 파라미터는 그대로 두었다)

### 5-1. 실패한 구간의 실제 기하 여유 (S, `diag_s2.py`)

실패한 `append_checked` 구간에서 두 로봇의 TCP 경로를 400점 보간해 `geometry.arm_margin`의 최솟값을 구했다 (mm, 양수 = 충돌 아님, config 기준 팔 간 요구 250 mm 초과분).

| 모델 | 실패 구간 (로봇 vs 상대, 모드, t) | 실제 최소 팔 여유 mm | TCP 충돌 | 상대 로봇 상태 |
|---|---|---:|---|---|
| 01 | 3 vs 2, D, 170.8 | 0.881 | 없음 | 대기 위치(타임라인 끝 7.89 s) |
| 03 | 3 vs 1, D, 61.49 | 0.127 | 없음 | 대기 위치(끝 7.74 s) |
| 02 | 3 vs 2, D, 1171.65 | 0.763 | 없음 | 대기 위치(끝 7.78 s) |
| 04 | 2 vs 1, T, 64.91 | 0.729 | 없음 | 대기 위치(끝 7.52 s) |
| 05 | 3 vs 2, D, 106.7 | **−0.615** | 없음 | 대기 위치(끝 7.26 s) |

(prevalidate의 구간 판정은 `geometry.min_arm_margin_over_interval`처럼 구간 최소값의 하한(Lipschitz 여유, `INTERVAL_MAX_STEP_MM` = 2.5 mm)을 쓴다. 위 여유 0.13~0.88 mm는 이 하한의 여유 이내다 — 판정식 자체는 이 문서에서 재검증하지 않았다.)

### 5-2. P의 실패 구간 (`diag_p2.py`)

| 모델 | 실패 구간 | 실제 최소 팔 여유 mm | TCP 충돌 |
|---|---|---:|---|
| 04 | 로봇 3 vs 2, T, t=0.0~8.98 | −250.0 | 있음 |
| 04 | 로봇 1 vs 2, T, t=65.93~67.72 | −172.5 | 있음 |
| 04 | 로봇 3 vs 1, D, t=98.6~99.98 | −6.925 | 없음 |
| 02 | 로봇 3 vs 2, T, t=0.0~9.04 | −250.0 | 있음 |
| 02 | 로봇 3 vs 2, T, t=11.09~17.24 | −249.999 | 있음 |

### 5-3. 대기 위치를 바깥쪽(자기 base 방향 쪽)으로 옮긴 S 재실행 (`diag_margin.py`)

대기 위치 = B7 결과 + 추가 거리 e (mm). 값은 prevalidate 통과 시 makespan_s.

| 모델 | e=0 | e=1 | e=2 | e=3 | e=5 |
|---|---|---:|---:|---:|---:|
| 01 | FAIL | 2005.287 | 2005.365 | 2005.443 | 2005.600 |
| 02 | FAIL | 10733.184 | 10733.285 | 미측정 | 미측정 |
| 03 | FAIL | 미측정 | 2237.185 | 미측정 | 2237.421 |
| 04 | FAIL | 미측정 | 59950.311 | 미측정 | 미측정 |

P는 위 모든 e에서 01·02·03·04 모두 FAIL(같은 교착 이유). 05의 e 재실행은 §5-4.

### 5-4. 05: 조각 꼭짓점으로 만든 대기 위치 (`diag_05.py`)

B7의 K_j를 패스 꼭짓점 대신 `split_at_reach` 조각 꼭짓점(B3 분할점 포함)으로 만들면 ρ가 패스 기준 558 / 559 / 559 mm에서 조각 기준 560 / 560 / 560 mm로 바뀐다 (측정). S를 조각 기준 대기 위치로 다시 돌린 결과:

| 추가 거리 e (mm) | 결과 | 소요 s |
|---|---|---:|
| 0 | FAIL — ARM_ENVELOPE at t=106.69689853099923 (§2와 같은 구간) | 0.1 |
| 1 | FAIL — ARM_ENVELOPE at t=108.4126432491761 | 0.1 |
| 2 | PASS — makespan_s 336441.628378598, handovers 700, retreats 700 | 848.9 |

(e=2의 소요 848.9 s는 20분 상한 안이다. 이 PASS는 진단이며 채택한 baseline 값이 아니다.)

### 5-5. P를 "일을 끝낸 로봇은 항상 대기 위치로 후퇴"로 바꾼 재실행 (`diag_p.py`, e=2)

| 모델 | 결과 |
|---|---|
| 04 | FAIL — deadlock: no other robot to wait for (ARM_ENVELOPE at t=65.93), failed_proposals=2, retreats=2 |
| 02 | FAIL — deadlock: too many rejected proposals (t=13.17), failed_proposals=3, retreats=1 |
| 03 | FAIL — deadlock: too many rejected proposals (t=73.88), failed_proposals=4, retreats=2 |

## 6. 테스트 소요 (측정)

| 명령 | 결과 | 소요 |
|---|---|---:|
| `python -m pytest -q` (전체, 마지막 한 번) | 649 passed | 305.89 s (21:47~21:53) |
| `python -m pytest -q -m "not slow"` | 635 passed, 14 deselected | 162.01 s |

이전 실측 615 passed(작업 26a)에 신규 34개(B18′·분할점·PARK 비교 11, 배정·스케줄·포트폴리오 20, AST 확장 3).

## 7. 미측정

- 01~05에서 통과하는 전략의 makespan, 포트폴리오 선택, 후퇴 횟수(통과 실행), 통과한 S의 compute_s.
- 01·06 W 하한 대비 비: 06만 S 통과(§3). 01은 미측정.
- Validator 판정(실행하지 않음), `results.csv` 기록(하지 않음), T-B27(6모델 `require_submittable` 테스트)은 만들지 않았다.
- δ = "auto"의 6모델 효과, 대기 위치 z(U-13) 효과, U-19 방향 선택 효과.
