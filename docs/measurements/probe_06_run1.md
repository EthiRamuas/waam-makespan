# probe_06 run 1 (작업 20) — 숫자만

실행: `.venv\Scripts\python.exe -m experiments.probe_06` 1회, 커밋 cf0205b. 시도 1회(재시도 없음).
기록 오류: 실행 직전 출력 리다이렉트용 로그 파일을 레포 루트에 만들어 트리가 untracked 1개 상태로 시작했다 → results.csv notes와 probe.json `git_dirty`가 dirty로 기록됨(코드·입력 변경 없음).

| 항목 | 값 | 사전 실측(작업 18) |
|---|---|---|
| run id | 20261011-181549-06-cf0205b | — |
| 종료 코드 | 0 | — |
| 시도 a1: Validator 종료 코드 / wall | 0 / 3.6025 s | 미측정 |
| summary.json status | PASS | — |
| makespan_s | 6174.838943466003 | 6174.838943466003 (차이 0) |
| 로봇 1 D / T / W (s) | 5945.0 / 25.838943466002736 / 204.0 | 5945.0 / 25.839 / 204.0 |
| 로봇 2, 3 D / T / W (s) | 0 / 0 / 6174.838943466003 | — |
| 로봇 1 세그먼트 수 | chain_rows 1939 = 로봇1 1935 + 로봇2·3 각 2 | 1934 (차이 0: 1934+1 종료행) |
| ratio (우리 3대 하한, lower_bound_s 1656.5625) | 3.7275013429713657 | 3.727 |
| coverage / overfill / iou | 0.9977459672292008 / 0.0 / 0.9977459672292008 | — |
| layer_iou_min / failed_layer_count | 0.9958897049473677 / 0 | — |
| evaluated_layer_count | 51 | — |
| collision_event_count | 0 | prevalidate 위반 0 |
| slicing_s / toolpath_s / chain_s | 0.0315 / 0.1750 / 0.0186 | prevalidate 0.17 s |
| prevalidate_s / write_s / compute_s | 0.1729 / 0.0917 / 0.4582 | — |
| a1_points | 10 | — |
| park_index (로봇 2, 3) | 0, 0 | 후보 0 |
| pass_count | 102 | 102 |
| git_commit / git_dirty | cf0205b / true (위 기록 오류) | — |
| config_md5 | bf3b30c6e762bcc93ff44d8f80bcb46d | 같음 |
| trajectory_sha256 | edf9ff50d0a638bc51bb5bd7fb03713b0405bba3a997ea550610c9c3bc2d138e | — |

P18 비교: ok = true, max_abs_err = 6.661338147750939e-16 (허용 0.005), 자체 층 51 / Validator 층 51, 불일치 0개.

summary.json issues: [] / failure_reasons: [].

results.csv 추가 행(1행):
`06,probe_v0_robot1_only,6174.838943466003,3.7275013429713657,0.4582402999512851,True,2026-10-11T18:15:53+09:00,cf0205b,,1656.5625,PASS,1.0.1,"ratio=ours, 3-robot lower bound, 1-robot probe; run=20261011-181549-06-cf0205b; a1; dirty"`

원자료: `.cache/waam/probe/20261011-181549-06-cf0205b/` (커밋하지 않음).
