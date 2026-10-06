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
