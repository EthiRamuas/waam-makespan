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
