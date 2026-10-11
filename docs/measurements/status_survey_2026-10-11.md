# 현황 조사 (작업 17, 읽기 위주, 2026-10-11)

기준: `session/2026-10-10` 작업 트리. 시그니처는 `inspect.signature`로 읽은 값(공개 = `_`로 시작하지 않고 그 모듈에서 정의된 함수·클래스). 명세 존재 = `docs/specs/` 안의 파일 유무만 본다.

## 1. src/waam 모듈 현황

| 모듈 | 존재 | 공개 함수·클래스 시그니처 | 관련 테스트 | `docs/specs/` 명세 |
|---|---|---|---|---|
| geometry | 있음 | `CellGeometry(base_xy, reach_mm, tcp_radius_mm, arm_radius_mm, arm_clearance_mm, touching_is_collision, check_arm_envelope, check_tcp_radius, eps_mm, ws_center_xy, ws_radius_mm, bead_width_mm)`(+`from_config(cfg)`); `reach_margin(g, robot_id, xy)`; `in_reach(g, robot_id, xy)`; `reachable_mask(g, xy)`; `seg_seg_dist(a0, a1, b0, b1)`; `arm_margin/arm_collides/tcp_collides/pair_collides(g, ra, tcp_a, rb, tcp_b)`; `IntervalResult(collides, arm_margin, tcp_margin, t)`; `min_arm_margin_over_interval(g, ra, p0a, p1a, rb, p0b, p1b, t0, t1, *, max_step_mm=2.5)`; `interval_margins_batch(…, *, max_step_mm=2.5)`; `interval_aabb_gap(…)`; `interval_clear_mask(…, *, buffer_mm=0.0)`; `intervals_collide(…, *, buffer_mm=0.0, max_step_mm=2.5, prefilter=True)`; `deposition_in_workspace(g, p0_xy, p1_xy)`; `dist3(p0_xyz, p1_xyz)` | `test_geometry.py`, `test_geometry_batch.py` | 없음 |
| prevalidate | 있음 | `Code`(IntEnum); `Verdict(ok, code, t=nan, robot=0, other=0)`; `Report(ok, violations, warnings)`; `float32_buffer_mm(g, min_buffer_mm=0.001)`; `PrevalidateRules(geom, deposition_speed_mm_s, travel_speed_mm_s, speed_relative_tolerance, fail_on_speed_violation, layer_height_mm, build_plane_z_mm, tcp_z_center, layer_z_tolerance_mm, wait_position_tolerance_mm, buffer_mm, max_step_mm, geom_arm_only, geom_tcp_only)`; `quantize_f32(xyz)`; `Timeline(robot_id, capacity=64)`; `new_timelines()`; `check_segment_local(rules, seg)`; `check_pair(rules, tla, tlb, t_from=0.0, t_to=inf, *, hold_open=False)`; `check_hold(rules, timelines, robot_id, xy, t_from)`; `try_append(rules, timelines, seg)`; `close_timeline(rules, timelines, robot_id)`; `check_all(rules, timelines)`; `require_submittable(rules, timelines)` | `test_prevalidate.py`, `test_prevalidate_review.py` | 없음 |
| segment | 있음 | `Mode`(str Enum); `SegmentError`; `Segment(robot_id, mode, start_time_s, end_time_s, start_xyz_mm, end_xyz_mm)`; `check_chain(segments)` | `test_segment.py` | 없음 |
| timing | 있음 | `TimingParams(deposition_speed_mm_s, travel_speed_mm_s, arc_on_s, arc_off_s)`; `Step(kind, points=(), duration_s=None)`; `build_chain(rid, start_xyz, steps, params)` | `test_timing.py` | 없음 |
| writer | 있음 | `LintIssue(code, robot=0, row=0, detail="")`; `render_rows(chains)`; `lint_csv(path, rules)`; `write_trajectory(path, chains, rules, timelines)` | `test_writer.py` | 없음 |
| toolpath | 있음 | `ToolpathError(code, message)`; `ToolpathParams(s_mm, o_mm, n_c, chord_mm, lift_dz_mm, eps_w_mm, wall_mode, medial_sample_mm=0.5, medial_tol_mm=0.02, medial_simplify_mm=0.01, medial_min_chain_mm=0.0, connect_slack_mm=0.001, zone_min_inradius_mm=0.05)`(+`from_config(config)`); `Pass(layer, z, kind, vertices, length, footprint, reachable_robots)`; `Toolpath(passes, params, thin_lost_mm2, empty_reach_count, medial_fallback_regions)`; `generate(stack, config, params=None, *, cache_dir=None, use_cache=True)` | `test_toolpath.py` | 있음 (`toolpath.md`) |
| slicing | 있음 | `SlicingError(code, message)`; `Layer(index, z_bottom, z_top, z_slice, geometry, area_mm2)`; `LayerStack(layers)`; `slice_stl(stl_path, config, *, cache_dir=None, use_cache=True)` | `test_slicing.py`, `test_below_plane_guard.py` | 있음 (`slicing.md`) |
| lower_bound | 있음 | `LowerBound(total_area_mm2, centerline_mm, deposition_s, n_robots, lower_bound_s)`; `lower_bound_from_areas(areas_mm2, *, bead_width_mm, deposition_speed_mm_s, n_robots)`; `lower_bound(stack, config)` | `test_lower_bound.py`, `test_lower_bound_wrapper.py` | 있음 (`lower_bound.md`) |
| assign | **없음** | — | — | 없음 |
| schedule | **없음** | — | — | 없음 |
| precedence | **없음** | — | — | 없음 |

- 목록에 없는 모듈 `results.py`는 있다: `ResultRow(…13개 열)`, `make_row(…)`, `append_result(path, row)`, `read_results(path)`; 테스트 `test_results.py`; 명세 파일 없음. 종단 테스트 `test_stage1_end_to_end.py`도 있다.
- 명세 `docs/specs/`에는 `lower_bound.md`, `slicing.md`, `toolpath.md` 세 개뿐이다(`docs/spec.md`는 Validator 확정명세로 별개 문서).

## 2. experiments/

- 파일: `__init__.py`, `bench_prevalidate.py`, `bench_prevalidate.csv`.
- `run_all.py`: **없음**. `sweep.py`: **없음**. `experiments/results.csv`: **없음**(파일이 아직 만들어지지 않음).
- results.csv 스키마 정의: **있음** — `src/waam/results.py`의 `COLUMNS`(13열): model, algo, makespan_s, ratio, compute_s, passed, run_at, commit, seed, lower_bound_s, validator_status, validator_version, notes. 쓰기 `append_result`는 헤더가 다르면 거부.

## 3. Validator 1회 실행 — **샘플 job (`tests/fixtures/sample_job`), 모델 01~06이 아님**

| 항목 | 값 |
|---|---|
| 대상 | `tests/fixtures/sample_job`의 복사본(scratchpad, 레포 파일 불변). 실제 6개 모델이 아니라 Validator 샘플이며 config가 다르다(xy_reach 2500 mm 등 summary.json 값) |
| 명령 | `waam-validator run <복사본> --output <새 폴더>` (`.venv`의 1.0.1) |
| 종료 코드 | 0 |
| 실행 시간(wall) | 2.0 s (bash `date` 차, 1회 실측, 파이썬 시작·저장 포함) |
| status | PASS, summary.json `makespan_s` = 18.0, `trajectory_rows` = 8, 경고 2건 |

## 4. 빈 도달 패스 수 재측정 (`in_reach` 변경 후, 캐시 없음)

| 모델 | 빈 도달 패스 / 전체 패스 | 이전 값 |
|---|---|---|
| 04 | 60 / 560 | 60 / 560 |
| 05 | 1286 / 1408 | 1286 / 1408 |

(`.cache/waam/analysis/t17_len.py` 출력. 01·02·03·06은 0.)
