# WAAM Validator Report

## Overall Result

**PASS**

- WAAM Validator version: 1.0.1

## Input Summary

- Directory: `C:\Github\waam-makespan\.cache\waam\probe\20261011-181549-06-cf0205b`
- Trajectory rows: 1939
- Target watertight: True

## Schedule

- Makespan: 6174.84 s
- R1: completion 6174.84 s; Deposition 5945.00 s; Travel 25.84 s; Wait 204.00 s
- R2: completion 6174.84 s; Deposition 0.00 s; Travel 0.00 s; Wait 6174.84 s
- R3: completion 6174.84 s; Deposition 0.00 s; Travel 0.00 s; Wait 6174.84 s

## Robot XY Reach

- Passed: True
- R1: max XY distance 1461.84 / 1500.00 mm; XY margin 38.16 mm; violating points 0
- R2: max XY distance 400.00 / 1500.00 mm; XY margin 1100.00 mm; violating points 0
- R3: max XY distance 400.00 / 1500.00 mm; XY margin 1100.00 mm; violating points 0

## Collision

- Arm Envelope events: 0
- Minimum Arm Envelope safety margin: 641.71 mm
- Arm centerline distance at worst case:
  891.71 mm
- Arm required centerline distance at worst case:
  250.00 mm
- TCP_RADIUS events: 0
- Minimum TCP distance: 891.71 mm

## Shape

- Target layer-integrated volume: 636120.000 mm³
- Deposited volume: 634686.165 mm³
- Intersection volume: 634686.165 mm³
- Underfill volume: 1433.835 mm³
- Overfill volume: 0.000 mm³
- Coverage: 99.77%
- Underfill: 0.23%
- Overfill: 0.00%
- IoU: 99.77%
- Failed layers: 0 / 51

## Failure Reasons

None

## Warnings

None

## Validation Violations

These findings contribute to a normal `FAIL`; they do not mean that the pipeline ended with
the fatal status `ERROR`.

None

## Output Files

- `summary.json`
- `validation_report.md`
- `robot_metrics.csv`
- `collision_events.csv`
- `layer_metrics.csv`
- `run.log`
- `validation_inputs.json`

## Interpretation Limitations

본 검증기는 각 로봇을 폭이 고정된 Base–TCP 2D Capsule로 단순화하고, XY 평면상 Capsule 안전 여유와 TCP 허용 원 침범만을 로봇 간 충돌로 판단한다. 검사는 adaptive sample 기반이며 연속시간 swept collision을 보증하지 않는다. 실제 로봇 링크, 관절 자세, Z 방향 분리, 지그 및 환경 충돌은 반영하지 않는다. 형상 검증은 일정한 비드 폭과 layer 높이를 가정한 명목 기하 모델이며 열변형, 비드 형상 변화, 용융풀 거동 및 공정 불안정성을 예측하지 않는다.
