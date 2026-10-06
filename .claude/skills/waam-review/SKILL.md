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
