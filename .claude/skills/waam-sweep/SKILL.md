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

```
변경: <무엇을 돌렸는지 한 줄>
측정: 모델별 ratio = 01:x.xx 02:x.xx 03:x.xx | 계산시간 xx s | PASS n/3
판단: <다음에 무엇을 결정해야 하는지 한 줄>
```

실패하면 **원인만 보고하고 멈춘다.** 알고리즘을 임의로 바꾸지 않는다.
측정하지 않은 값은 "미측정"이라고 쓴다.
