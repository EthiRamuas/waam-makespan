# probe_driver 명세 (v0)

상태: **확정(C-41).** 구현: 작업 19. 근거: DECISIONS C-23·C-29·C-30·C-31·C-32·C-33, `docs/specs/toolpath.md`, `src/waam/{timing,writer,results,geometry,prevalidate,segment}.py`와 각 테스트(읽기), Validator 도움말·산출물(읽기). 이 파일과 `docs/spec.md`가 어긋나면 `docs/spec.md`가 맞다.
표기: **확정**(코드·소스·실측) / **가설**(근거 없는 값) / **미측정** / **미확인**. 규칙 번호는 P1~P22만 쓴다.
목적: 2단계 종료 기준 "모델 06에서 실제 Validator PASS 1회"(C-30)를 얻는 구동 스크립트 `experiments/` 한 개를 정의한다. 새 알고리즘이 아니라 기존 모듈(toolpath v0, timing, prevalidate, writer, results)을 이어 붙이는 배관이다.
채팅 검토 반영(C-41에 포함, 2026-10-11 16시): P16·P18·P22·T-20 수정, T-26 추가.

## 0. 핵심 사실

- 로봇 1은 모델 06 전체에 도달한다(여유 +33.9 mm, `docs/measurements/reach_analysis.md` 인용). 오늘 재확인: `toolpath.generate` 결과 06의 패스 102개 전부 `reachable_robots`에 1이 있다(실측, 스크립트 `.cache/waam/analysis/p18_prechain.py`).
- 6개 모델 `config.yaml`은 md5가 모두 `bf3b30c6e762bcc93ff44d8f80bcb46d`로 같다(실측). 06 config: arc_on 1.0 / arc_off 1.0 s, `tcp_z_reference: center`, `fail_on_speed_violation: true`, 로봇 home = (−1000, 0, 1000) / (500, 866.025404, 1000) / (500, −866.025404, 1000).
- Validator는 `home_xyz_mm`을 판정에 쓰지 않는다(`grep`으로 확인한 범위 — `ui`·`report` 폴더 제외 — 에서 사용처는 `config/models.py` 정의와 `dashboard/` 표시뿐, 판정 모듈에는 없음. 제외한 폴더는 미확인). 따라서 "home에서 시작"은 우리 규약이며 Validator 요구가 아니다(확정, 읽기).
- **사전 실측 (Validator 미실행, 이 명세의 설계를 그대로 `build_chain`·`prevalidate`로 돌린 값; 레포 코드 변경 없음):** 로봇 1 chain 세그먼트 1934개, 끝 시각 6174.838943466003 s, 모드 합 T 25.839 / D 5945.0 / W 204.0 s, 로봇 2·3을 home에 두고 `prevalidate.check_all` ok(위반 0), prevalidate 0.17 s. 우리 하한 `lower_bound_s` = 1656.5625 s → 1대 작업이라 ratio(우리 계산) = 6174.84 / 1656.5625 = 3.727 (**성능 주장이 아님**).
- **미측정:** 06에서 `waam-validator run`의 wall 시간(샘플 job은 2.0 s이나 06은 시뮬레이션 시간이 6174 s라 훨씬 길 것으로 가설), 06 슬라이싱 시간.

## 1. 범위와 모듈 경계

| 하는 것 | 하지 않는 것 | 넘기는 곳 |
|---|---|---|
| 06의 `slice_stl` → `toolpath.generate` → 로봇 1 chain → 주차 로봇 chain → `write_trajectory` | 할당·스케줄 탐색(로봇 1대 고정), 파라미터 튜닝(C-29) | assign·schedule(4단계) |
| job 폴더 조립, Validator 1회 실행, 산출물 파싱 | Validator 결과의 가공·추정·보간 | `summary.json` 값 그대로 기록 |
| 자체 층별 지표 vs Validator 층별 지표 비교(가설 검증) | 형상 FAIL 원인 분석·경로 수정 | 사람(주간) |
| `experiments/results.csv`에 행 추가, 실행별 `probe.json` | `results.py` 스키마 변경 | 사람 결정(§10 D12) |
| 실패 분류와 제한된 자동 재시도 | 무제한 재시도, 형상 FAIL 재시도 | 사람 |

## 2. 고정 조건

| 조건 | 출처 |
|---|---|
| 대상 = 모델 06, 작업 로봇 = 1번만 | 작업 18 지시, C-26 입력 2 |
| toolpath v0 기본값(s = w, o = w/2, n_c = 1, 기본 `wall_mode`)만 사용. 기본값 밖의 값은 C-24 사람 결정 전 금지 | C-29 |
| 적층 속도 공칭 8 mm/s, 이동 150 mm/s (config에서 읽음) | C-33, `TimingParams.from_config` |
| 패스마다 arc_on + arc_off W (config 값, 생략 금지) | CLAUDE.md 자체 제약, `timing.py` |
| 리프트 Δz = `ToolpathParams.lift_dz_mm` (= 2h = 4 mm, **가설값**) | C-32 |
| 로봇 3대가 모두 CSV에 있고, 첫 시각 0.0, 시각 엄격 증가, 마지막 행 mode W | CLAUDE.md 계약, `writer.lint_csv` |
| 탐침 코드는 `experiments/`, 산출물은 `.cache/waam/probe/<run>/`, 기록은 `experiments/results.csv` | C-30, C-31, A3 |
| 탐침에서 Validator는 1회 실행뿐이고, 탐침은 제출 알고리즘이 아니다 | C-31 |
| `config.yaml`·`target.stl`·Validator 레포 수정 금지 | CLAUDE.md |

## 3. 규칙 (검증 가능)

| ID | 규칙 | 검증 방법(§8) |
|---|---|---|
| **P1** 입력 | `source_dir` 기본 `C:/Github/WAAM_Validator/tests/06`(읽기 전용). `config.yaml`, `target.stl`만 읽는다. 로봇 id 1이 작업, 2·3은 주차 | T-01 |
| **P2** 입력 불변 | job 폴더로 `config.yaml`, `target.stl`을 `shutil.copyfile`로 복사하고, 복사 뒤 sha256이 원본과 같음을 확인한다(다르면 abort `PROBE_INPUT_COPY`). config의 md5 = `bf3b30c6e762bcc93ff44d8f80bcb46d`도 로그에 남긴다(불일치는 경고, 중단 아님) | T-01 |
| **P3** 파라미터 | `ToolpathParams.from_config(cfg)` 그대로. 스크립트에 s·o·n_c·wall_mode를 바꾸는 옵션을 만들지 않는다. 사용한 `ToolpathParams` 전체를 `probe.json`에 기록 | T-02 |
| **P4** 도달 | 모든 패스에서 `1 in reachable_robots`. 하나라도 아니면 abort `PROBE_REACH`(재시도 없음, 해당 패스 수 보고) | T-03 |
| **P5** 순서 | 패스 순서는 `Toolpath.passes` 그대로(층 오름차순, 층 안 정준 순서 V9). 재배열·분할 없음 | T-04 |
| **P6** 이동 | 로봇 1 chain = home에서 시작. 첫 패스: `T`로 `(x0, y0, z0+Δz)`까지, 이어서 `T`로 `(x0, y0, z0)`까지 하강. 패스 k→k+1: 다음 시작점이 현재 위치와 float32로 같으면 이동 없음. 아니면 `z_lift = max(z_cur, z_next) + Δz`로 ① 수직 상승 T ② 수평 T(z_lift 유지) ③ 수직 하강 T. 마지막 패스 뒤에는 이동하지 않는다(복귀 없음) | T-05, T-06, T-07 |
| **P7** 아크 | 각 패스 = `Step("pass", …)`. `build_chain`이 첫 꼭짓점에서 `arc_on` W, 끝 꼭짓점에서 `arc_off` W를 넣는다. 값은 `TimingParams.from_config`(06: 1.0/1.0 s). 06 기준 패스 102개 → 아크 W 합 204.0 s(실측) | T-08 |
| **P8** 속도·시간 | 모든 이동·적층 지속시간은 `build_chain`이 float32로 양자화된 끝점 3D 거리 ÷ 공칭 속도로 계산한다. 속도 보정·스케일링 금지. 속도 검사는 `fail_on_speed_violation: true`, ±10% | T-09 |
| **P9** 정밀도 | 시각은 float64 `repr`(반올림 없음), 좌표는 float32로 반올림한 값의 `repr`(`writer._num`). **좌표를 1e-6 mm 이상으로 쓰는 것은 불가능하다**: Validator 로더가 float32로 읽으므로 |x| 512~1024 mm 구간의 간격은 6.1e-5 mm, 128~256 mm는 1.5e-5 mm다(float32 간격, 산술). "정밀도 1e-6"은 시각에만 해당한다(§10 D1) | T-10 |
| **P10** 시간 간격 금지 | 한 로봇의 chain은 `check_chain`(경계에서 시각·위치 정확히 일치, 첫 시작 0.0)을 통과하고, CSV에서 로봇별 `T+D+W` 시간 합 = 마지막 행 시각(`rel 1e-12`, `abs 1e-9`, `writer.lint_csv`의 `MODE_TIME_SUM_MISMATCH`)이어야 한다. 빈 시간은 W로 채운다 | T-11 |
| **P11** 주차 | 로봇 2·3은 시작 위치 = home(후보 0), `Step("wait", duration_s=T_end)` 하나. `T_end` = 로봇 1 chain의 마지막 `end_time_s`(float 그대로). 그러면 세 로봇의 마지막 시각이 모두 같고, 로봇 2·3의 CSV 행은 W 두 줄(시작, 종료)이다. 먼저 끝난 로봇이 없으므로 makespan = `T_end` | T-12, T-13 |
| **P12** 주차 후보 | 로봇 1 chain을 먼저 `Timeline`에 넣고 `close_timeline`한 뒤, 주차 로봇을 `try_append`·`close_timeline`한다. 충돌(`ARM_ENVELOPE`·`TCP_RADIUS`)이면 그 로봇의 위치를 다음 후보로 바꾼다: XY = home + λ·(base − home), λ ∈ (0, 0.25, 0.5, 0.75, 1.0)(**가설값**), z = home z. 모든 후보가 실패하면 abort `PROBE_PARK_NONE`. 최종 `check_all`이 ok여야 쓴다 | T-14, T-15 |
| **P13** 쓰기 | `writer.write_trajectory(path, chains, rules, timelines)`만 쓴다(`require_submittable`·재파싱 린트 포함). 린트 실패는 파일이 남지 않으므로 abort `PROBE_CSV`(분류는 §6) | T-16 |
| **P14** job 폴더 | `.cache/waam/probe/<run>/`, `<run>` = `YYYYMMDD-HHMMSS-06-<git short hash>`(로컬 시각). 폴더가 이미 있으면 abort(덮어쓰기 금지). 내용: `config.yaml`, `target.stl`, `trajectory.csv`, `validator_out/`(Validator `--output`, 새 폴더), `validator_stdout.json`, `probe.json`, `probe.log` | T-17 |
| **P15** Validator 실행 | venv 자체 실행 파일(`Path(sys.executable).parent / "waam-validator.exe"`; 없으면 abort)로 `run <job> --output <job>/validator_out --json`. 종료 코드, wall 시간(`time.perf_counter`, subprocess 호출 전후만)을 `probe.json`에 기록. 타임아웃 `T_v`(**가설값 1800 s**, §10 D3). 타임아웃은 FAIL이 아니라 abort `PROBE_VALIDATOR_TIMEOUT` | T-18 |
| **P16** results.csv | Validator가 판정한 **모든 시도(PASS·FAIL 모두)**마다(판정 전 abort는 행 없음) `results.make_row(model="06", algo=<§10 D8>, compute_s, seed=None, commit, trajectory_path, lower_bound_s=lower_bound(stack, cfg).lower_bound_s, summary_path=validator_out/summary.json)` → `append_result`. `makespan_s`·`passed`·`validator_*`는 summary.json 값 그대로. `ratio`는 `make_row`가 우리 하한으로 계산한 값이며 `notes`에 "ratio=ours, 3-robot lower bound, 1-robot probe"와 run id, 시도 번호(`a<n>`)를 적는다. 파일이 없으면 `append_result`가 헤더를 만든다. 이 파일의 첫 행이 이 탐침의 첫 Validator 실행이다 | T-19 |
| **P17** 확장 기록 | `results.csv`에 없는 항목(§B)은 `<run>/probe.json`에 쓴다: coverage, overfill, 전체 IoU, 층별 IoU 최소, 실패 층 수, 로봇별 D/T/W 초, 충돌 이벤트 수, Validator wall, 생성 시간, git 해시 + dirty 여부, chain 행 수, trajectory.csv sha256 | T-20 |
| **P18** 가설 검증 | 자체 층별 지표 = toolpath 패스 발자국의 층별 합집합을 Validator 방식으로 정규화(`normalize_polygon` 규칙)해 목표 단면과 비교한 coverage·overfill_ratio·iou(테스트 13과 같은 식). `validator_out/layer_metrics.csv`의 같은 층 값과 층별·전체 모두 절대 오차 ≤ **0.005(가설값)**인지 본다. 층 수가 다르면 불일치. 초과해도 재시도하지 않고 `probe.json`에 불일치 목록과 최대 오차를 기록하고 종료 코드 4로 보고한다. `results.csv` 행은 Validator 판정 그대로 둔다(PASS면 PASS) | T-21 |
| **P19** 형상 FAIL | `summary.json`의 `shape.passed == false`(IoU < 0.9, coverage < 0.8, overfill > 0.30, 실패 층 > 5% 중 하나)이면 **멈추고 사람에게 보고**한다. 재시도·파라미터 변경 없음. 수치 전부 `probe.json` | T-22 |
| **P20** 재시도 | 아래 §6 표. 최대 **3회 재시도**(처음 시도 포함 4회), 모든 오류 종류가 한 예산을 공유한다. 시도마다 새 run 폴더(`<run>-a<n>`) | T-23 |
| **P21** A1 | 06의 **첫 Validator 실행이 끝난 뒤** 그 wall 시간 `t_v`로 스윕 점 수를 정한다: `t_v ≤ 120 s` → 10점(s ∈ {0.9, 1.0, 1.1, 1.2, 1.3}·w × o ∈ {w/4, w/2}, n_c = 1), 아니면 5점(o = w/2, s는 같은 5점). 이 스크립트 v0는 점 수만 `probe.json`(`a1_points`)에 기록하고 스윕을 실행하지 않는다(§10 D13) | T-24 |
| **P22** 쓰기 범위·종료 코드 | 쓰는 곳은 `.cache/waam/probe/<run>/`와 `experiments/results.csv`뿐이다. 종료 코드: 0 = Validator PASS이고 P18 허용 안, 1 = 형상 FAIL(P19), 2 = 재시도 소진 후 비형상 FAIL 또는 오류, 3 = Validator 전 abort(P2·P4·P12·P13·P15), 4 = PASS이나 P18 불일치(`results.csv`에는 PASS로 기록, C-30의 "PASS 1회" 기준은 충족으로 본다) | T-25 |

## 4. 경우의 수와 엣지 케이스

| 경우 | 처리 |
|---|---|
| 첫 패스 | home(z = 1000)에서 시작 시점까지 대각선 T로 이동(`(x0, y0, z0+Δz)`), 이어서 수직 하강. 상승 없음(home z가 이미 높음) |
| 닫힌 고리 패스 직후 같은 점에서 시작하는 패스 | float32로 같으면 이동 없이 `arc_off` W → `arc_on` W(패스 경계의 아크는 생략하지 않는다) |
| 층 전환 | 다음 패스의 z가 +h: 규칙 P6의 `z_lift = z_next + Δz`. 수직 상승이 층 높이보다 길다 |
| 양자화 후 길이 0인 이동 | `build_chain`이 건너뛴다(travel). 적층 변은 0이면 `ValueError`(toolpath가 0 길이를 이미 제거) |
| 06 단면 급변(23,940 → 3,420 mm²) | 패스 수가 층마다 다르다. 규칙 변경 없음 |
| 로봇 1의 TCP·팔과 주차 로봇이 XY로 겹침 | prevalidate가 판정, 사전 실측 위반 없음(home 후보 0) |
| Validator가 prevalidate와 다른 충돌 판정 | prevalidate의 건전성 계약 위반 신호 → §6, 재시도 1회 사용 뒤 보고 |

## 5. 인터페이스

```
experiments/probe_06.py                 # python -m experiments.probe_06 [--source-dir PATH] [--run-id ID]
  main() -> exit code (P22)
  build_robot1_steps(toolpath, home_xyz, lift_dz_mm) -> list[Step]            # P5~P7
  park_candidates(config, robot_id) -> list[tuple[float, float, float]]        # P12
  assemble_chains(config, toolpath, park_choice) -> dict[int, list[Segment]]   # P6, P11
  make_job_dir(source_dir, run_id) -> Path                                      # P2, P14
  run_validator(job_dir, timeout_s) -> (exit_code, wall_s)                      # P15
  read_validator_outputs(out_dir) -> dict                                       # summary.json, layer_metrics.csv, robot_metrics.csv
  own_layer_metrics(stack, toolpath, config) -> list[LayerMetric]               # P18
  compare_layers(own, validator_rows, tol=0.005) -> Comparison                  # P18
  classify_failure(outputs) -> FailureClass                                     # §6
```
- 옵션에 s·o·n_c·wall_mode가 없다(P3). 스크립트는 `src/waam`을 수정하지 않고 import만 한다. Validator 모듈 import는 `experiments/`(자체 지표 계산)에서만 허용한다(`src/`는 금지, CLAUDE.md).
- 종료 코드와 출력 파일은 P14·P22.

## 6. 실패 처리

| 분류 | 판별(확정/미확인) | 자동 재시도 | 재시도 때 바뀌는 것 | 그 외 |
|---|---|---|---|---|
| **형상 FAIL** | `summary.json`의 `shape.passed == false` (확정: 필드 존재, 샘플 job summary.json에서 확인) | **없음** | — | 멈추고 보고(P19) |
| **충돌** | prevalidate 위반 코드 `ARM_ENVELOPE`/`TCP_RADIUS`, 또는 `summary.json`의 `collision.passed == false` | 있음 | 충돌에 관여한 주차 로봇을 다음 주차 후보로(P12). 후보 소진이면 abort | Validator가 잡았는데 prevalidate가 못 잡은 경우는 prevalidate 결함 신호로 `probe.json`에 표시 |
| **CSV 계약 오류** | `writer`의 `ValueError`(린트 코드) 또는 Validator 입력 오류 코드 | 있음(**§10 D2**) | 입력이 같으면 결과도 같다 — 재시도로 바뀌는 것이 없다. 후보: 새 run 폴더에서 1회 재생성(파일 잠금 등 I/O 경쟁 대비), 같은 코드가 재현되면 중단 | 코드 이름을 보고 |
| **속도 반올림 오류** | `DEPOSITION_SPEED_VIOLATION`/`TRAVEL_SPEED_VIOLATION` | 있음(**§10 D2**) | 같음: `build_chain`은 양자화 길이로 시각을 계산하므로 재현되면 구현 결함 | 중단·보고 |
| **도달 오류** | `PROBE_REACH` 또는 `ROBOT_XY_REACH_VIOLATION` | 없음 | — | 06은 로봇 1이 전부 도달(여유 +33.9 mm)이므로 발생하면 결함 |
| **타임아웃** | subprocess 타임아웃 | 없음 | — | abort 3, wall 시간 하한 기록 |
| **기타 Validator 오류** | `summary.json` 없음 또는 status가 PASS/FAIL이 아님(`error.json`은 C-19에서 판정 결과가 아님) | 없음 | — | abort, 출력 폴더 보존 |

- 재시도 예산 3회는 위 모든 분류가 공유한다(P20). 소진하면 종료 코드 2.
- `failure_reasons` 항목의 문자열 형식은 **미확인**(샘플 PASS summary에서는 빈 목록). 분류는 필드(`shape.passed`, `collision.passed`, `reach.passed`)로 한다.

## 7. 의사코드

```
main():
  cfg ← load_config(source/config.yaml); stack ← slice_stl(source/target.stl, cfg)
  t0 ← clock
  tp ← toolpath.generate(stack, cfg, from_config(cfg), use_cache=False)          # P3
  assert all(1 in p.reachable_robots for p in tp.passes) else abort(PROBE_REACH) # P4
  steps1 ← build_robot1_steps(tp, home_1, tp.params.lift_dz_mm)                  # P5~P7
  c1 ← build_chain(1, home_1, steps1, TimingParams.from_config(cfg))             # P8
  for candidate in park candidates:                                              # P12
     chains ← {1: c1, 2: park(2, candidate), 3: park(3, candidate)}              # P11
     timelines ← try_append / close_timeline robot 1, 2, 3; check_all
     if ok: break
  else abort(PROBE_PARK_NONE)
  write_trajectory(job/trajectory.csv, chains, rules, timelines)                 # P13
  compute_s ← clock − t0
  exit_code, wall_s ← run_validator(job)                                         # P15
  out ← read_validator_outputs(job/validator_out)
  row ← make_row(...); append_result(experiments/results.csv, row)               # P16
  probe.json ← all extra items                                                    # P17
  if shape FAIL: stop(1)                                                          # P19
  compare own vs Validator layers (tol 0.005)                                     # P18
  a1_points ← 10 if wall_s ≤ 120 else 5                                           # P21
```

## 8. 단위 테스트

공통: Validator 없이 도는 것은 `experiments/` 함수를 직접 부르고, Validator 실행이 필요한 것만 `waam-validator`를 쓴다. 이름은 제안이다.

| ID | 이름 | 한 줄 기준 |
|---|---|---|
| T-01 | `test_probe_job_inputs_are_byte_identical_copies` | job의 config.yaml·target.stl sha256이 원본과 같고 원본 폴더에 새 파일이 없다 |
| T-02 | `test_probe_uses_toolpath_defaults_and_exposes_no_knobs` | 기록된 `ToolpathParams`가 `from_config`와 같고 CLI에 s·o·n_c·wall_mode가 없다 |
| T-03 | `test_probe_aborts_when_robot1_cannot_reach_a_pass` | 도달 집합에 1이 없는 패스가 있는 합성 입력에서 `PROBE_REACH`, 파일·Validator 호출 없음 |
| T-04 | `test_probe_keeps_toolpath_pass_order` | chain의 D 구간 순서가 `Toolpath.passes` 순서와 같다 |
| T-05 | `test_probe_transit_is_lift_horizontal_descend` | 패스 사이가 T 3개이고 z가 `max(z_cur, z_next)+Δz`다 |
| T-06 | `test_probe_skips_transit_when_next_start_equals_current_in_float32` | 같은 점에서 시작하는 패스 사이에 T 행이 없다 |
| T-07 | `test_probe_robot1_does_not_return_home` | 로봇 1의 마지막 위치가 마지막 패스 끝점이고 home이 아니다 |
| T-08 | `test_probe_arc_w_surrounds_every_pass_with_config_times` | 모든 패스의 앞뒤 W 길이가 config의 arc_on/off이고 D가 그 사이다 |
| T-09 | `test_probe_speeds_match_nominal_on_float32_lengths` | D·T 구간 속도가 8·150 ±1e-9 상대 오차 안이다 |
| T-10 | `test_probe_csv_numbers_are_writer_format` | 시각은 float64 repr, 좌표는 float32 repr이고 `lint_csv`가 비어 있다 |
| T-11 | `test_probe_mode_time_sum_equals_last_time_per_robot` | 로봇마다 T+D+W 합 = 마지막 행 시각, 시각 엄격 증가 |
| T-12 | `test_probe_parked_robots_have_only_two_w_rows_and_same_last_time` | 로봇 2·3 행이 W 두 줄이고 마지막 시각이 로봇 1과 비트 단위로 같다 |
| T-13 | `test_probe_all_three_robots_present_first_time_zero_final_w` | 세 로봇 모두 존재, 첫 시각 0.0, 마지막 모드 W |
| T-14 | `test_probe_parking_moves_to_next_candidate_on_collision` | home이 충돌하는 합성 config에서 두 번째 후보가 선택되고 `check_all` ok |
| T-15 | `test_probe_parking_aborts_when_no_candidate_is_safe` | 모든 후보 충돌이면 `PROBE_PARK_NONE`, trajectory.csv 없음 |
| T-16 | `test_probe_rejected_write_leaves_no_trajectory_file` | 린트 실패를 주입하면 파일이 없고 abort 3 |
| T-17 | `test_probe_run_folder_is_never_overwritten` | 같은 `<run>` 폴더가 있으면 abort, 기존 파일 불변 |
| T-18 | `test_probe_validator_timeout_is_abort_not_fail` | 가짜 실행기가 시간 초과하면 abort 3, results.csv 행 없음 |
| T-19 | `test_probe_results_row_is_bound_to_trajectory_sha` | `make_row`가 summary.json·trajectory.csv sha256을 검증하고 행이 하나 추가된다 |
| T-20 | `test_probe_json_has_all_required_items` | probe.json에 요청 항목 13개 키와 `slicing_s`, `toolpath_s`, `chain_s` 키가 모두 있고 값이 summary/robot_metrics 값 그대로다 |
| T-21 | `test_probe_layer_comparison_flags_error_above_tolerance` | 가짜 layer_metrics.csv에서 0.0051 차이는 불일치, 0.0049는 일치(경계 포함) |
| T-22 | `test_probe_shape_fail_stops_without_retry` | `shape.passed=false`인 가짜 summary에서 시도 1회, 종료 코드 1 |
| T-23 | `test_probe_retry_budget_is_three_and_shared` | 충돌→CSV→속도 연속 실패에서 재시도 3회 뒤 종료 코드 2, 시도 4회 |
| T-24 | `test_probe_a1_threshold_boundary` | `t_v = 120.0` → 10점, `120.001` → 5점(o = w/2) |
| T-25 | `test_probe_writes_only_inside_cache_and_results_csv` | 임시 작업 디렉터리 감시에서 그 밖의 쓰기가 없고 종료 코드가 P22 표와 같다 |
| T-26 | `test_probe_written_d_segments_match_toolpath_vertices` | 쓴 CSV의 D 구간 끝점이 toolpath 패스 꼭짓점의 float32 양자화 값과 같다(D16 a의 보조 검사: 비교 불일치 시 가설 문제와 배관 문제를 가른다) |

## 9. 가설과 검증 방법

| 가설 | 검증 |
|---|---|
| 패스 발자국의 합집합 = Validator 증착 형상(toolpath §11) | P18: 06의 층별 지표 비교(허용 0.005, **가설값**) |
| 로봇 2·3을 home에 두면 06 전 구간에서 충돌이 없다 | 사전 실측: prevalidate ok(§0). Validator 확인은 이 탐침 실행 |
| Validator 1회 시간 `t_v` | **미측정**. 이 탐침의 첫 실행이 값을 준다(P15, P21) |
| 리프트 Δz = 4 mm, 주차 후보 λ 목록, 타임아웃 1800 s | **가설**, 근거 없음 |

## 10. 사람 결정 필요

결정 열: 전 항목 기본값 후보 채택(C-41). 근거 없는 숫자는 가설로 남는다.

| # | 결정 | 후보 | 기본값 후보 | 근거 / 비고 | 결정 (C-41) |
|---|---|---|---|---|---|
| D1 | 좌표 정밀도 요구 "1e-6 이상" | a) 시각만 1e-6 이상, 좌표는 float32 값 b) 지시대로 좌표 1e-6 | **a** | b는 불가능(P9). Validator 로더가 float32로 읽는다(확정) | a |
| D2 | CSV·속도 오류의 "자동 재시도" 의미 | a) 새 run 폴더에서 같은 입력으로 1회 재생성, 재현되면 중단 b) 재시도 없이 즉시 중단 c) 로직을 바꿔 재시도(예: 후보 변경) | **a** | 입력이 같으면 결과가 같아 재시도로 바뀌는 것이 없다(결정적 코드). 충돌만 후보 변경으로 의미가 있다 | a |
| D3 | Validator 타임아웃 `T_v` | 600 / 1800 / 3600 s | 1800 s (**가설**) | 06 wall 시간 **미측정**. 테스트는 600 s를 쓴 적이 있다(`test_stage1_end_to_end.py`) | 1800 s (가설) |
| D4 | 주차 로봇의 마지막 시각 | a) `T_end`와 같게(W 하나) b) 짧은 W(예: 1.0 s)만 | **a** | 두 방식의 Validator 판정은 같다(끝난 로봇은 makespan까지 위치 유지). a는 stage-1 테스트와 같고 시간 합 검사가 단순 | a |
| D5 | 주차 후보 λ 목록과 z | (0, .25, .5, .75, 1.0), z = home z | 좌동 (**가설**) | A2 "home 유지, 위반 시 base 쪽 첫 안전 위치". 사전 실측에서 후보 0이 통과해 실제로 쓰일지 미정 | 채택 (가설) |
| D6 | 첫 접근과 Δz | a) home → `(x0,y0,z0+Δz)` 대각선 후 하강 b) home z에서 수평 이동 후 수직 하강 | **a**, Δz = 4 mm (**가설**, C-32) | b는 이동이 길다. 충돌 판정은 XY만이라 Validator 차이 없음 | a, Δz 4 mm (가설) |
| D7 | `compute_s` 범위 | a) `toolpath.generate`(캐시 없음) + chain + prevalidate + write b) 슬라이싱 포함 | **a**, 슬라이싱 시간은 `probe.json`에 따로 | `results.py` 정의: 배정·스케줄·timing·쓰기, Validator 제외. 슬라이싱 포함 여부는 정의되어 있지 않다(미확인) | a |
| D8 | `algo` 문자열 | 예: `probe_v0_robot1_only` | 좌동 | 비교군으로 남을 이름 | 채택 |
| D9 | `seed` 열 | 빈칸 / 0 | 빈칸 | 무작위성이 없다 | 빈칸 |
| D10 | `commit` 열과 dirty 작업 트리 | a) HEAD만 b) dirty면 실행 거부 c) HEAD + notes에 dirty | **c** | 재현성 | c |
| D11 | ratio 표시 | a) 우리 3대 하한으로 계산한 값을 그대로, notes에 "성능 아님" b) 빈칸 | **a** | 지시: "ratio(우리 계산값 표시)". 사전 추정 3.727은 1대 작업 값 | a |
| D12 | `results.csv`에 없는 항목(§B 8개) | a) 스키마 유지, `probe.json`에 기록 b) 스키마 확장(C-17 변경) | **a** | 작업 지시: 스키마를 바꾸지 않는다. 확장은 사람 결정 | a |
| D13 | 스윕(A1)의 실행 승인 | a) v0는 점 수만 정하고 실행은 별도 승인 b) 자동 실행 | **a** | C-29(기본값 밖 값 금지, C-24 전)와 C-31(스윕 격자 결정)의 관계를 사람이 확정해야 한다 | a |
| D14 | 가설 검증 허용 오차와 불일치 처리 | 0.005 / 0.01 / 0.002; 불일치 시 보고만 / 중단 | 0.005 (**가설**), 보고만(종료 코드 4) | 근거 없음 | 0.005 (가설), 보고만 |
| D15 | 형상 FAIL 정의 | a) `shape.passed == false` b) 전체 IoU < 0.9만 | **a** | a가 IoU·coverage·overfill·실패 층을 모두 포함. 지시문은 IoU < 0.9를 예로 든다 | a |
| D16 | 비교 수준 | a) toolpath 발자국만(P18) b) 쓴 CSV의 D 행으로 발자국 재구성도 | **a** | b는 timing·writer의 z→층 배정까지 독립 검증하나 구현이 더 든다 | a |
| D17 | 스크립트 이름·위치 | `experiments/probe_06.py` / `experiments/probe.py --model 06` | `probe_06.py` | 모델 일반화는 run_all 설계(C-21) 때 | probe_06.py |
| D18 | 재시도 3회의 셈 | a) 재시도 3회(시도 4회) b) 총 시도 3회 | **a** | 지시: "최대 3회 자동 재시도" | a |

## A. 재사용 후보 조사 (읽기)

### A-1. 공개 시그니처 · 시간·반올림·간격 규칙

| 모듈 | (a) 탐침이 쓰는 공개 함수·클래스 | (b) W 행·정밀도·시간 간격 처리 (코드에서 확인) |
|---|---|---|
| `timing` | `TimingParams(deposition_speed_mm_s, travel_speed_mm_s, arc_on_s, arc_off_s)`(`from_config(cfg)`: arc 시간이 None이면 `ValueError`, 생략 금지); `Step(kind, points, duration_s)` kind ∈ pass/travel/wait; `build_chain(rid, start_xyz, steps, params) -> list[Segment]` | 패스 = 첫 꼭짓점에서 `arc_on` W(0이면 생략) → 변마다 D → 끝 꼭짓점에서 `arc_off` W. travel = T 한 세그먼트, 길이 0(float32 양자화 뒤)이면 건너뜀. wait는 W 한 세그먼트(`duration_s > 0`). 지속시간 = float32 양자화 끝점의 3D 거리 ÷ 속도. 각 세그먼트는 직전 세그먼트의 끝 값에서 시작하고 `check_chain`을 부른다. 패스 시작점은 현재 위치와 float32로 같아야 한다(아니면 `ValueError`, travel을 넣어야 함). 적층 변 길이 0은 `ValueError` |
| `segment` | `Mode`(T/D/W), `Segment(robot_id, mode, start_time_s, end_time_s, start_xyz_mm, end_xyz_mm)`, `check_chain(segments)` | 시작 ≥ 0, 끝 > 시작(엄격), robot_id ∈ {1,2,3}. `check_chain`: 첫 시작 정확히 0.0, 이웃 세그먼트의 시각·위치 **정확한 float 일치**(간격·겹침·점프 금지). 마지막 세그먼트의 모드는 제약 없음(CSV 종료 행은 writer가 추가) |
| `writer` | `render_rows(chains)`, `lint_csv(path, rules) -> list[LintIssue]`, `write_trajectory(path, chains, rules, timelines) -> Path` | 시각 = float64 `repr`(반올림 없음). 좌표 = float32로 반올림한 값의 `repr`. LF, UTF-8, BOM 없음. 세그먼트마다 한 행(시작 시각·위치·모드) + 로봇별 종료 W 행(마지막 `end_time_s`, 마지막 위치). 정렬 로봇→시각. `write_trajectory`: `require_submittable`(모든 타임라인 닫힘 + 전체 검사) → `_same_schedule` → 임시 파일에 쓰고 `lint_csv` → 통과해야 `os.replace`. 거부 시 파일 없음. 린트의 시간 공백 검사: 로봇별 모드 시간 합 ≈ 마지막 시각(`rel 1e-12`, `abs 1e-9`, `MODE_TIME_SUM_MISMATCH`), W의 위치 변화 ≤ `wait_position_tolerance_mm`, D의 길이 0·수직 이동 검사 |
| `prevalidate` | `PrevalidateRules.from_config(cfg)`, `new_timelines()`, `try_append(rules, timelines, seg) -> Verdict`, `close_timeline(rules, timelines, robot_id)`, `check_all`, `require_submittable`, `quantize_f32` | 좌표는 Validator 로더와 같이 float32로 양자화해 판정(버퍼 없음). 충돌은 Lipschitz 하한과 `buffer_mm`(float32 반올림 상계, 최소 1e-3 mm)을 쓰고 샘플링 밀도로 보수성을 주장하지 않는다. 닫지 않은 타임라인은 쓰기 전에 막힌다 |
| `results` | `COLUMNS`(13열), `ResultRow`, `make_row(model, algo, *, compute_s, seed, commit, trajectory_path, lower_bound_s, summary_path, makespan_s, notes, run_at)`, `append_result(path, row)`, `read_results(path)` | `summary.json`을 `validation_inputs.json`의 trajectory sha256로 해당 `trajectory.csv`에 묶는다(C-19). `passed`는 Validator가 돌고 PASS일 때만 True, 안 돌렸으면 빈칸. 추가만 하고 수정·삭제 없음, 헤더가 다르면 거부, 동시 쓰기 비안전(한 번에 한 쓰기) |
| `geometry` | `CellGeometry.from_config`, `in_reach(g, robot_id, xy)`, `deposition_in_workspace(g, p0, p1)`, `reachable_mask`(로봇 1~3 하드코딩, PROGRESS 열린 항목), 충돌·구간 함수들 | 판정 전용(시간·W 처리 없음). 탐침은 직접 부를 필요가 없다: 도달은 `Pass.reachable_robots`, 충돌은 `prevalidate`가 부른다 |
| `toolpath`·`slicing`·`lower_bound` | `slice_stl`, `generate`, `lower_bound(stack, config) -> LowerBound.lower_bound_s` | toolpath: 패스 `vertices`(XY), `z`, `kind`, `reachable_robots`, `ToolpathParams.lift_dz_mm`(기록만) |
| 관련 테스트 | `test_timing.py`(아크 배치·양자화 속도·골든), `test_writer.py`(형식·린트·게이트·골든), `test_results.py`, `test_geometry*.py`, `test_prevalidate*.py`, `test_stage1_end_to_end.py`(sample_job을 우리 파이프라인으로 재현해 Validator PASS: `Step` → `build_chain` → `try_append`/`close_timeline` → `write_trajectory` → `waam-validator run --output --json`) | 탐침 흐름의 선례는 `test_stage1_end_to_end.py`다 |

### A-2. 탐침에 재사용할 수 있는 것 / 새로 필요한 것

| 재사용(코드 변경 없음) | 새로 필요(experiments/) |
|---|---|
| `slice_stl`, `toolpath.generate`, `lower_bound`, `TimingParams.from_config`, `build_chain`, `PrevalidateRules`·`Timeline` API, `write_trajectory`(게이트 포함), `make_row`·`append_result`, `test_stage1_end_to_end.py`의 Validator 호출 방식 | ① 로봇 1 `Step` 생성(리프트·하강, 같은 점 건너뛰기) ② 주차 후보 선택과 반복 ③ job 폴더 생성·복사·sha256 검증 ④ Validator subprocess 실행과 wall 시간 ⑤ `summary.json`·`layer_metrics.csv`·`robot_metrics.csv` 파서 ⑥ 자체 층별 지표와 비교 ⑦ `probe.json` 작성 ⑧ 실패 분류·재시도 제어 ⑨ A1 점 수 규칙 ⑩ 종료 코드 |
| **미확인** | `waam-validator run`의 06 wall 시간, `failure_reasons`의 문자열 형식, Validator가 `--output`에 쓰는 `validation_inputs.json`의 trajectory sha256 키가 모든 실행에서 같은지(샘플 job에서는 `inputs["trajectory.csv"]["sha256"]` 확인) |

## B. `results.py` COLUMNS(13열) 대 탐침 기록 항목

COLUMNS: model, algo, makespan_s, ratio, compute_s, passed, run_at, commit, seed, lower_bound_s, validator_status, validator_version, notes. 스키마는 바꾸지 않는다.

| 기록 항목 | 대응 열 | 상태 |
|---|---|---|
| PASS 여부 | `passed`, `validator_status` | 있음 |
| makespan | `makespan_s` | 있음(summary.json 값 그대로) |
| ratio(우리 계산값 표시) | `ratio`, `lower_bound_s` | 있음(둘 다 우리 하한 기준, `notes`에 표시) |
| 생성 시간 | `compute_s` | 있음(범위는 D7) |
| git 해시 | `commit` | 있음(dirty 여부는 `notes`, D10) |
| coverage | — | **없음** → `probe.json` |
| overfill | — | **없음** → `probe.json` |
| 전체 IoU | — | **없음** → `probe.json` |
| 층별 IoU 최소 | — | **없음** → `probe.json` (`layer_metrics.csv`에서) |
| 실패 층 수 | — | **없음** → `probe.json` (`shape.failed_layer_count`) |
| D/T/W 초 | — | **없음** → `probe.json` (`robot_metrics.csv`: `deposition_time_s`, `travel_time_s`, `wait_time_s`, 로봇별) |
| 충돌 이벤트 수 | — | **없음** → `probe.json` (`collision.collision_event_count`) |
| Validator 실행 시간 | — | **없음**(`compute_s`는 Validator 시간을 제외한다고 정의됨) → `probe.json` |

없는 열 8개: coverage, overfill, 전체 IoU, 층별 IoU 최소, 실패 층 수, D/T/W 초, 충돌 이벤트 수, Validator 실행 시간.
