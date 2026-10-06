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
