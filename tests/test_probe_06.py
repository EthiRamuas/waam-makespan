"""experiments/probe_06.py: tests T-01..T-26 of docs/specs/probe_driver.md section 8.

No real Validator run here (task 20 does that). ``waam-validator`` is replaced by a fake runner that
writes TEST INPUT files (summary.json, layer_metrics.csv, ...): they are not Validator results.
The input is a small box near robot 1 with the model-01 config fixture (identical to model 06's).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from waam_validator.config.loader import load_config

from experiments import probe_06 as pr
from waam import prevalidate as pv
from waam import results, writer
from waam.prevalidate import PrevalidateRules
from waam.segment import Mode
from waam.slicing import slice_stl
from waam.timing import TimingParams
from waam.toolpath import ToolpathParams, generate

FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "model01" / "config.yaml"


def _make_source(root: Path, center_x: float) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE_CONFIG, root / "config.yaml")
    box = trimesh.creation.box(extents=[40.0, 40.0, 6.0])
    box.apply_translation([center_x, 0.0, 3.0])
    box.export(root / "target.stl")
    return root


@pytest.fixture(scope="module")
def near_source(tmp_path_factory):
    return _make_source(tmp_path_factory.mktemp("src_near"), -380.0)  # robot 1 reaches it


@pytest.fixture(scope="module")
def far_source(tmp_path_factory):
    return _make_source(tmp_path_factory.mktemp("src_far"), 620.0)  # robot 1 does not


@pytest.fixture(scope="module")
def built(near_source):
    cfg = load_config(near_source / "config.yaml")
    stack = slice_stl(near_source / "target.stl", cfg, use_cache=False)
    tp = generate(stack, cfg, ToolpathParams.from_config(cfg), use_cache=False)
    timing = TimingParams.from_config(cfg)
    chains = pr.assemble_chains(cfg, tp, {2: pr.park_candidates(cfg, 2)[0],
                                          3: pr.park_candidates(cfg, 3)[0]}, timing)
    own_overall, own_layers = pr.own_shape_metrics(stack, tp, cfg)
    return SimpleNamespace(cfg=cfg, stack=stack, tp=tp, timing=timing, chains=chains,
                           own_layers=own_layers, own_overall=own_overall)


# ------------------------------------------------------------------ fake Validator


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fake_outputs(job: Path, built, *, status="PASS", shape_ok=True, collision_ok=True,
                 issues=(), layer_shift=0.0, bind_sha=None, coverage=0.97):
    out = job / "validator_out"
    out.mkdir(exist_ok=True)
    traj = job / "trajectory.csv"
    rows = list(csv.DictReader(traj.open(encoding="utf-8")))
    makespan = max(float(r["time_s"]) for r in rows)
    summary = {
        "schema_version": "4.0", "validator_version": "test-fake", "status": status,
        "schedule": {"makespan_s": makespan},
        "shape": {"passed": shape_ok, "coverage": coverage, "overfill_ratio": 0.01, "iou": 0.95,
                  "failed_layer_count": 0 if shape_ok else 3},
        "collision": {"passed": collision_ok, "collision_event_count": 0 if collision_ok else 2},
        "reach": {"passed": True},
        "failure_reasons": [] if status == "PASS" else ["fake"],
        "issues": list(issues),
    }
    for name in pr._COMPARED:  # overall equals ours unless shifted, so P18 sees them
        summary["shape"][name] = getattr(built.own_overall, name) + layer_shift
    (out / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (out / "validation_inputs.json").write_text(
        json.dumps({"inputs": {"trajectory.csv": {"sha256": bind_sha or _sha(traj)}}}),
        encoding="utf-8")
    with (out / "layer_metrics.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["layer_index", "coverage", "overfill_ratio", "iou"])
        for m in built.own_layers:
            w.writerow([m.layer_index, m.coverage + layer_shift, m.overfill_ratio, m.iou])
    with (out / "robot_metrics.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["robot_id", "deposition_time_s", "travel_time_s", "wait_time_s"])
        w.writerows([[1, 11.5, 22.5, 33.5], [2, 0.0, 0.0, makespan], [3, 0.0, 0.0, makespan]])
    return summary


class FakeRunner:
    """Calls ``scenarios[i](job)`` on the i-th run (the last one repeats)."""

    def __init__(self, built, *scenarios):
        self.built, self.scenarios, self.calls = built, scenarios or ({},), []

    def __call__(self, job, timeout_s):
        sc = self.scenarios[min(len(self.calls), len(self.scenarios) - 1)]
        self.calls.append(Path(job))
        if callable(sc):
            return sc(Path(job))
        if sc.get("error"):
            out = Path(job) / "validator_out"
            out.mkdir(exist_ok=True)
            (out / "error.json").write_text(json.dumps({"code": sc["error"]}), encoding="utf-8")
            return 2, 0.5
        fake_outputs(Path(job), self.built, **sc)
        return (0 if sc.get("status", "PASS") == "PASS" else 1), 3.25


def drive(tmp_path, source, runner, **kw):
    kw.setdefault("run_id", "t-run")
    kw.setdefault("git", ("abc1234", False))
    code = pr.run_probe(source, runner=runner, probe_root=tmp_path / "probe",
                        results_path=tmp_path / "results.csv", **kw)
    return code


def read_probe(tmp_path, name="t-run"):
    return json.loads((tmp_path / "probe" / name / "probe.json").read_text(encoding="utf-8"))


def run_dirs(tmp_path):
    return sorted(p.name for p in (tmp_path / "probe").iterdir())


def csv_rows(job, rid):
    rows = list(csv.DictReader((job / "trajectory.csv").open(encoding="utf-8")))
    return [r for r in rows if int(r["robot_id"]) == rid]


@pytest.fixture
def passed_run(tmp_path, near_source, built):
    runner = FakeRunner(built, {})
    assert drive(tmp_path, near_source, runner) == 0
    return tmp_path, tmp_path / "probe" / "t-run"


# ------------------------------------------------------------------ T-01 .. T-04


def test_probe_job_inputs_are_byte_identical_copies(tmp_path, near_source):
    before = sorted(p.name for p in near_source.iterdir())
    hashes = {n: _sha(near_source / n) for n in pr.INPUT_FILES}
    job = pr.make_job_dir(near_source, "r1", tmp_path)
    for n in pr.INPUT_FILES:
        assert _sha(job / n) == hashes[n]
    assert sorted(p.name for p in near_source.iterdir()) == before
    assert {n: _sha(near_source / n) for n in pr.INPUT_FILES} == hashes


def test_probe_uses_toolpath_defaults_and_exposes_no_knobs(passed_run, built):
    tmp_path, _ = passed_run
    rec = read_probe(tmp_path)["toolpath_params"]
    want = json.loads(json.dumps(pr.asdict(ToolpathParams.from_config(built.cfg))))
    assert rec == want
    for flag in ("--s-mm", "--o-mm", "--n-c", "--wall-mode"):
        with pytest.raises(SystemExit):
            pr.main([flag, "1"])


def test_probe_aborts_when_robot1_cannot_reach_a_pass(tmp_path, far_source, built):
    runner = FakeRunner(built)
    assert drive(tmp_path, far_source, runner) == pr.EXIT_ABORT
    assert runner.calls == []
    assert not list((tmp_path / "probe").rglob("trajectory.csv"))
    assert read_probe(tmp_path)["abort"] == "PROBE_REACH"
    assert not (tmp_path / "results.csv").exists()


def test_probe_keeps_toolpath_pass_order(built):
    d_segments = [s for s in built.chains[1] if s.mode is Mode.D]
    want = []
    for q in built.tp.passes:
        for (x0, y0), (x1, y1) in zip(q.vertices, q.vertices[1:]):
            want.append(((x0, y0, q.z), (x1, y1, q.z)))
    assert len(d_segments) == len(want)
    for seg, (a, b) in zip(d_segments, want):
        assert np.array_equal(pv.quantize_f32(seg.start_xyz_mm), pv.quantize_f32(a))
        assert np.array_equal(pv.quantize_f32(seg.end_xyz_mm), pv.quantize_f32(b))


# ------------------------------------------------------------------ T-05 .. T-09


def _fake_toolpath(*passes):
    return SimpleNamespace(passes=tuple(SimpleNamespace(z=z, vertices=tuple(v)) for z, v in passes))


HOME = (-1000.0, 0.0, 1000.0)


def test_probe_transit_is_lift_horizontal_descend():
    tp = _fake_toolpath((1.0, [(0, 0), (10, 0)]), (3.0, [(50, 5), (60, 5)]))
    steps = pr.build_robot1_steps(tp, HOME, 4.0)
    kinds = [s.kind for s in steps]
    assert kinds == ["travel", "travel", "pass", "travel", "travel", "travel", "pass"]
    assert steps[0].points == ((0.0, 0.0, 5.0),)  # diagonal to start + dz
    assert steps[1].points == ((0.0, 0.0, 1.0),)  # descend
    z_lift = max(1.0, 3.0) + 4.0
    assert steps[3].points == ((10.0, 0.0, z_lift),)  # vertical up from the pass end
    assert steps[4].points == ((50.0, 5.0, z_lift),)  # horizontal at z_lift
    assert steps[5].points == ((50.0, 5.0, 3.0),)  # vertical down


def test_probe_skips_transit_when_next_start_equals_current_in_float32():
    tp = _fake_toolpath((1.0, [(0, 0), (10, 0)]), (1.0, [(10 + 1e-9, 0), (20, 0)]))
    steps = pr.build_robot1_steps(tp, HOME, 4.0)
    assert [s.kind for s in steps] == ["travel", "travel", "pass", "pass"]


def test_probe_robot1_does_not_return_home(built):
    last_pass = built.tp.passes[-1]
    x, y = last_pass.vertices[-1]
    end = built.chains[1][-1]
    assert end.mode is Mode.W  # arc_off
    assert np.array_equal(pv.quantize_f32(end.end_xyz_mm), pv.quantize_f32((x, y, last_pass.z)))
    assert tuple(end.end_xyz_mm) != HOME


def test_probe_arc_w_surrounds_every_pass_with_config_times(built):
    chain, p = built.chains[1], built.timing
    runs = [i for i, s in enumerate(chain) if s.mode is Mode.D and
            (i == 0 or chain[i - 1].mode is not Mode.D)]
    assert len(runs) == len(built.tp.passes)
    for i in runs:
        before = chain[i - 1]
        j = i
        while j + 1 < len(chain) and chain[j + 1].mode is Mode.D:
            j += 1
        after = chain[j + 1]
        assert before.mode is Mode.W and before.end_time_s - before.start_time_s == pytest.approx(p.arc_on_s)
        assert after.mode is Mode.W and after.end_time_s - after.start_time_s == pytest.approx(p.arc_off_s)


def test_probe_speeds_match_nominal_on_float32_lengths(built):
    for s in built.chains[1]:
        if s.mode is Mode.W:
            continue
        d = float(np.linalg.norm(pv.quantize_f32(s.end_xyz_mm) - pv.quantize_f32(s.start_xyz_mm)))
        v = d / (s.end_time_s - s.start_time_s)
        want = built.timing.deposition_speed_mm_s if s.mode is Mode.D else built.timing.travel_speed_mm_s
        assert v == pytest.approx(want, rel=1e-9)


# ------------------------------------------------------------------ T-10 .. T-13


def test_probe_csv_numbers_are_writer_format(passed_run, built):
    _, job = passed_run
    for line in (job / "trajectory.csv").read_text(encoding="utf-8").splitlines()[1:]:
        _, t, x, y, z, _mode = line.split(",")
        assert repr(float(t)) == t
        for c in (x, y, z):
            assert repr(float(np.float32(float(c)))) == c
    rules = PrevalidateRules.from_config(built.cfg)
    assert writer.lint_csv(job / "trajectory.csv", rules) == []


def test_probe_mode_time_sum_equals_last_time_per_robot(passed_run):
    _, job = passed_run
    for rid in (1, 2, 3):
        rows = csv_rows(job, rid)
        times = [float(r["time_s"]) for r in rows]
        assert all(b > a for a, b in zip(times, times[1:]))
        total = sum(b - a for a, b in zip(times, times[1:]))
        assert total == pytest.approx(times[-1], rel=1e-12, abs=1e-9)


def test_probe_parked_robots_have_only_two_w_rows_and_same_last_time(passed_run):
    _, job = passed_run
    last1 = csv_rows(job, 1)[-1]["time_s"]
    for rid in (2, 3):
        rows = csv_rows(job, rid)
        assert [r["mode"] for r in rows] == ["W", "W"]
        assert rows[-1]["time_s"] == last1  # bit-identical text of the same float


def test_probe_all_three_robots_present_first_time_zero_final_w(passed_run):
    _, job = passed_run
    for rid in (1, 2, 3):
        rows = csv_rows(job, rid)
        assert rows and float(rows[0]["time_s"]) == 0.0 and rows[-1]["mode"] == "W"


# ------------------------------------------------------------------ T-14 .. T-18


def test_probe_parking_moves_to_next_candidate_on_collision(built, monkeypatch):
    home2 = pr.park_candidates(built.cfg, 2)[0]
    bad = (-380.0, 0.0, 1000.0)  # right above robot 1's work: XY overlap -> TCP collision
    real = pr.park_candidates
    monkeypatch.setattr(pr, "park_candidates",
                        lambda cfg, rid: [bad, home2] if rid == 2 else real(cfg, rid))
    rules = PrevalidateRules.from_config(built.cfg)
    plan = pr.plan_parking(built.cfg, rules, built.chains[1], built.timing)
    assert plan.park_index[2] == 1
    assert pv.check_all(rules, plan.timelines).ok



def test_probe_parking_aborts_when_no_candidate_is_safe(tmp_path, near_source, built, monkeypatch):
    bad = (-380.0, 0.0, 1000.0)
    monkeypatch.setattr(pr, "park_candidates", lambda cfg, rid: [bad, bad])
    runner = FakeRunner(built)
    assert drive(tmp_path, near_source, runner) == pr.EXIT_ABORT
    assert runner.calls == []
    assert read_probe(tmp_path)["abort"] == "PROBE_PARK_NONE"
    assert not list((tmp_path / "probe").rglob("trajectory.csv"))


def test_probe_rejected_write_leaves_no_trajectory_file(tmp_path, near_source, built, monkeypatch):
    def reject(*a, **kw):
        raise ValueError("injected lint failure")
    monkeypatch.setattr(pr.writer, "write_trajectory", reject)
    runner = FakeRunner(built)
    assert drive(tmp_path, near_source, runner) == pr.EXIT_ABORT
    assert runner.calls == []
    assert not list((tmp_path / "probe").rglob("trajectory.csv"))
    assert run_dirs(tmp_path) == ["t-run", "t-run-a2"]  # D2: one regeneration, then stop


def test_probe_run_folder_is_never_overwritten(tmp_path, near_source):
    job = pr.make_job_dir(near_source, "same", tmp_path)
    (job / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(pr.ProbeAbort) as exc:
        pr.make_job_dir(near_source, "same", tmp_path)
    assert exc.value.code == "PROBE_RUN_EXISTS"
    assert (job / "keep.txt").read_text(encoding="utf-8") == "x"


def test_probe_validator_timeout_is_abort_not_fail(tmp_path, near_source, built):
    def timeout(job):
        raise pr.ProbeValidatorTimeout(1800.0)
    assert drive(tmp_path, near_source, FakeRunner(built, timeout)) == pr.EXIT_ABORT
    assert not (tmp_path / "results.csv").exists()
    assert read_probe(tmp_path)["abort"] == "PROBE_VALIDATOR_TIMEOUT"


# ------------------------------------------------------------------ T-19 .. T-20


def test_probe_results_row_is_bound_to_trajectory_sha(tmp_path, near_source, built, passed_run):
    tmp, job = passed_run
    rows = results.read_results(tmp / "results.csv")
    assert len(rows) == 1
    r = rows[0]
    assert (r.model, r.algo, r.passed, r.seed, r.commit) == ("06", pr.ALGO, True, None, "abc1234")
    assert pr.RATIO_NOTE in r.notes and "run=t-run" in r.notes and "a1" in r.notes
    assert r.ratio == pytest.approx(r.makespan_s / r.lower_bound_s, rel=1e-12)
    # a verdict for another trajectory is refused, not recorded
    other = tmp_path / "other"
    runner = FakeRunner(built, {"bind_sha": "0" * 64})
    with pytest.raises(ValueError, match="was not produced for"):
        drive(other, near_source, runner)
    assert not (other / "results.csv").exists()


def test_probe_json_has_all_required_items(passed_run):
    tmp_path, job = passed_run
    probe = read_probe(tmp_path)
    for key in pr.PROBE_JSON_KEYS:
        assert key in probe and probe[key] is not None, key
    assert probe["coverage"] == pytest.approx(probe["coverage"])
    assert probe["robot_dtw_s"]["1"] == {"D": 11.5, "T": 22.5, "W": 33.5}  # as in robot_metrics.csv
    assert probe["collision_event_count"] == 0 and probe["failed_layer_count"] == 0
    assert probe["validator_wall_s"] == 3.25
    assert probe["git_commit"] == "abc1234" and probe["git_dirty"] is False
    assert probe["trajectory_sha256"] == _sha(job / "trajectory.csv")
    assert probe["compute_s"] == pytest.approx(probe["toolpath_s"] + probe["chain_s"]
                                               + probe["prevalidate_s"] + probe["write_s"])
    assert probe["a1_points"] in (5, 10)


# ------------------------------------------------------------------ T-21 .. T-24


def _own(*vals):
    return [SimpleNamespace(layer_index=i, coverage=v, overfill_ratio=0.0, iou=v)
            for i, v in enumerate(vals)]


def _rows(*vals):
    return [{"layer_index": str(i), "coverage": repr(v), "overfill_ratio": "0.0", "iou": repr(v)}
            for i, v in enumerate(vals)]


def test_probe_layer_comparison_flags_error_above_tolerance():
    assert pr.compare_layers(_own(0.9), _rows(0.9 + 0.0049)).ok
    bad = pr.compare_layers(_own(0.9), _rows(0.9 + 0.0051))
    assert not bad.ok and bad.mismatches and bad.max_abs_err == pytest.approx(0.0051)
    assert pr.compare_layers(_own(0.5), _rows(0.75), tol=0.25).ok  # exactly tol: inside
    assert not pr.compare_layers(_own(0.5), _rows(0.75), tol=0.2499).ok
    assert not pr.compare_layers(_own(0.5, 0.5), _rows(0.5)).ok  # layer count differs


def test_probe_shape_fail_stops_without_retry(tmp_path, near_source, built):
    runner = FakeRunner(built, {"status": "FAIL", "shape_ok": False})
    assert drive(tmp_path, near_source, runner) == pr.EXIT_SHAPE
    assert len(runner.calls) == 1
    rows = results.read_results(tmp_path / "results.csv")
    assert len(rows) == 1 and rows[0].passed is False  # P16: FAIL attempts are logged too


def test_probe_retry_budget_is_three_and_shared(tmp_path, near_source, built):
    speed = {"status": "FAIL", "issues": [{"severity": "error", "code": "DEPOSITION_SPEED_VIOLATION"}]}
    runner = FakeRunner(built,
                        {"status": "FAIL", "collision_ok": False},
                        {"error": "MODE_TIME_SUM_MISMATCH"},
                        speed,
                        {"status": "FAIL", "collision_ok": False})
    assert drive(tmp_path, near_source, runner) == pr.EXIT_EXHAUSTED
    assert len(runner.calls) == 4
    assert run_dirs(tmp_path) == ["t-run", "t-run-a2", "t-run-a3", "t-run-a4"]
    rows = results.read_results(tmp_path / "results.csv")
    assert len(rows) == 3  # attempt 2 had no verdict
    assert [("a%d" % n) in r.notes for n, r in zip((1, 3, 4), rows)] == [True] * 3


def test_probe_same_csv_or_speed_error_twice_stops_early(tmp_path, near_source, built):
    runner = FakeRunner(built, {"error": "MODE_TIME_SUM_MISMATCH"})
    assert drive(tmp_path, near_source, runner) == pr.EXIT_EXHAUSTED
    assert len(runner.calls) == 2  # D2: regenerated once, reproduced -> stop


def test_probe_a1_threshold_boundary():
    assert pr.a1_points(120.0) == 10
    assert pr.a1_points(120.001) == 5


# ------------------------------------------------------------------ T-25 .. T-26


def _tree(root: Path):
    return {str(p.relative_to(root)) for p in root.rglob("*")}


@pytest.mark.parametrize("scenario,code", [({}, 0), ({"layer_shift": 0.02}, 4),
                                           ({"status": "FAIL", "shape_ok": False}, 1)])
def test_probe_writes_only_inside_cache_and_results_csv(tmp_path, near_source, built, monkeypatch,
                                                        scenario, code):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    src_before = {n: _sha(near_source / n) for n in pr.INPUT_FILES}
    src_tree = _tree(near_source)
    out = tmp_path / "out"
    out.mkdir()
    runner = FakeRunner(built, scenario)
    got = pr.run_probe(near_source, "t-run", runner=runner, probe_root=out / "probe",
                       results_path=out / "results.csv", git=("abc1234", True))
    assert got == code
    assert os.listdir(cwd) == []
    assert _tree(near_source) == src_tree
    assert {n: _sha(near_source / n) for n in pr.INPUT_FILES} == src_before
    assert {p.split(os.sep)[0] for p in _tree(out)} == {"probe", "results.csv"}
    # PASS with a P18 mismatch (code 4) is still recorded as PASS; dirty tree is noted (D10)
    row = results.read_results(out / "results.csv")[0]
    assert row.passed is (scenario.get("status", "PASS") == "PASS")
    assert "dirty" in row.notes


def test_probe_written_d_segments_match_toolpath_vertices(passed_run, built):
    _, job = passed_run
    rows = csv_rows(job, 1)
    want = []
    for q in built.tp.passes:
        for (x0, y0), (x1, y1) in zip(q.vertices, q.vertices[1:]):
            want.append(((x0, y0, q.z), (x1, y1, q.z)))
    got = []
    for a, b in zip(rows, rows[1:]):
        if a["mode"] == "D":
            got.append((tuple(float(a[k]) for k in ("x_mm", "y_mm", "z_mm")),
                        tuple(float(b[k]) for k in ("x_mm", "y_mm", "z_mm"))))
    assert len(got) == len(want)
    for (ga, gb), (wa, wb) in zip(got, want):
        assert np.array_equal(np.float32(ga), pv.quantize_f32(wa).astype(np.float32))
        assert np.array_equal(np.float32(gb), pv.quantize_f32(wb).astype(np.float32))


# ------------------------------------------------------------------ extras (classification)


def test_classify_failure_uses_fields_not_text():
    def out(**sec):
        base = {"status": "FAIL", "shape": {"passed": True}, "collision": {"passed": True},
                "reach": {"passed": True}, "failure_reasons": [], "issues": []}
        base.update(sec)
        return {"summary": base, "error": None}
    C = pr.FailureClass
    assert pr.classify_failure({"summary": {"status": "PASS"}, "error": None}) is C.PASS
    assert pr.classify_failure(out(shape={"passed": False})) is C.SHAPE
    assert pr.classify_failure(out(collision={"passed": False})) is C.COLLISION
    assert pr.classify_failure(out(reach={"passed": False})) is C.REACH
    assert pr.classify_failure(out(issues=[{"severity": "warning",
                                            "code": "TRAVEL_SPEED_VIOLATION"}])) is C.OTHER
    assert pr.classify_failure({"summary": None, "error": {"code": "DEPOSITION_SPEED_VIOLATION"}}) is C.SPEED
    assert pr.classify_failure({"summary": None, "error": {"code": "FIRST_TIME_NOT_ZERO"}}) is C.CSV
    assert pr.classify_failure({"summary": None, "error": None}) is C.OTHER


def test_park_candidates_follow_the_home_to_base_line(built):
    c = pr.park_candidates(built.cfg, 1)
    assert c[0] == (-1000.0, 0.0, 1000.0)
    assert c[-1] == (-1400.0, 0.0, 1000.0)  # lambda = 1: above the base, z = home z
    assert c[2] == (-1200.0, 0.0, 1000.0)
