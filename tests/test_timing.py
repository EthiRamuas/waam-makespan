"""timing.build_chain: unit rules + golden tests that run the real Validator on its CSV.

Golden tests write the chains with ``vref.write_csv`` (coordinates stored as float32, exactly
what a submitted trajectory.csv carries) and ask the Validator itself. The config is the
repo's own copy of the shared model config (tests/fixtures/model01, md5-pinned in
test_fixtures.py; DECISIONS.md C-05).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from waam_validator.config.loader import load_config

from gen import layer_z
from vref import SAMPLE_JOB, timelines_of, validator_verdict, write_csv
from waam import prevalidate as pv
from waam import timing as timing_mod
from waam.prevalidate import PrevalidateRules, quantize_f32
from waam.segment import Mode, check_chain
from waam.timing import Step, TimingParams, build_chain

MODEL01_FIXTURE = Path(__file__).parent / "fixtures" / "model01"


@pytest.fixture(scope="module")
def cfg():
    path = MODEL01_FIXTURE / "config.yaml"
    if not path.exists():
        pytest.fail(f"{path} is required (DECISIONS.md C-05) but missing")
    return load_config(path)


def test_sample_job_config_without_arc_time_is_refused():
    # sample_job's config carries no arc_on/arc_off: timing must refuse, not invent a value
    c = load_config(SAMPLE_JOB / "config.yaml")
    assert c.process.arc_on_time_s is None
    with pytest.raises(ValueError, match="arc"):
        TimingParams.from_config(c)


def _params(cfg) -> TimingParams:
    return TimingParams.from_config(cfg)


def _sector_pass(r: PrevalidateRules, rid: int, k: int, edges: list[float], frac: float = 0.3):
    """Polyline of ``len(edges)`` edges in robot ``rid``'s sector; z = layer ``k`` center."""
    g = r.geom
    base = g.base_xy[rid - 1] - g.ws_center_xy
    ang = math.atan2(base[1], base[0])
    c = g.ws_center_xy + frac * g.ws_radius_mm * np.array([math.cos(ang), math.sin(ang)])
    tang = np.array([-math.sin(ang), math.cos(ang)])
    z = layer_z(r, k)
    pts, cur = [(float(c[0]), float(c[1]), z)], c.copy()
    for e in edges:
        cur = cur + e * tang
        pts.append((float(cur[0]), float(cur[1]), z))
    return tuple(pts)


def _robot_steps(r, rid, k, edges):
    pts = _sector_pass(r, rid, k, edges)
    return pts[0], [Step("travel", (pts[0],)), Step("pass", pts), Step("wait", duration_s=0.7)]


def _start(r, rid):
    return _sector_pass(r, rid, rid, [], frac=0.6)[0]  # each robot starts in its own sector


def _closed(cfg, chains):
    rules = PrevalidateRules.from_config(cfg)
    tls = timelines_of(chains)
    for rid in (1, 2, 3):
        assert pv.close_timeline(rules, tls, rid).ok
    return tls


# ------------------------------------------------------------------ unit rules


def test_pass_layout_arc_on_before_arc_off_after(cfg):
    prm = _params(cfg)
    r = PrevalidateRules.from_config(cfg)
    _, steps = _robot_steps(r, 1, 0, [30.0, 20.0, 10.0])
    chain = build_chain(1, _start(r, 1), steps, prm)
    check_chain(chain)
    assert [s.mode for s in chain] == [Mode.T, Mode.W, Mode.D, Mode.D, Mode.D, Mode.W, Mode.W]
    assert chain[1].duration_s == pytest.approx(prm.arc_on_s, abs=1e-9)
    assert chain[5].duration_s == pytest.approx(prm.arc_off_s, abs=1e-9)
    assert chain[0].start_time_s == 0.0
    assert all(s.start_xyz_mm == s.end_xyz_mm for s in chain if s.mode is Mode.W)


def test_d_speed_on_quantized_coordinates(cfg):
    prm = _params(cfg)
    r = PrevalidateRules.from_config(cfg)
    _, steps = _robot_steps(r, 2, 3, [37.123456789, 1.5, 0.37, 11.0000001])
    n = 0
    for s in build_chain(2, _start(r, 2), steps, prm):
        if s.mode is Mode.D:
            n += 1
            v = math.dist(quantize_f32(s.start_xyz_mm), quantize_f32(s.end_xyz_mm)) / s.duration_s
            assert v == pytest.approx(prm.deposition_speed_mm_s, rel=1e-9)
    assert n == 4


def test_travel_at_configured_speed_and_zero_travel_skipped(cfg):
    prm = _params(cfg)
    chain = build_chain(1, (0.0, 0.0, 10.0),
                        [Step("travel", ((0.0, 0.0, 10.0),)),
                         Step("travel", ((300.0, 400.0, 10.0),))], prm)
    assert len(chain) == 1 and chain[0].mode is Mode.T
    assert chain[0].duration_s == pytest.approx(500.0 / prm.travel_speed_mm_s, rel=1e-12)


@pytest.mark.parametrize("bad,match", [
    ("empty", "at least one step"),
    ("pass_not_at_pos", "current position"),
    ("zero_edge", "zero-length"),
    ("short_pass", "two vertices"),
    ("wait_no_duration", "duration_s > 0"),
    ("wait_negative", "duration_s > 0"),
    ("all_zero_travel", "no segment"),
    ("travel_two_points", "exactly one"),
    ("unknown_kind", "unknown kind"),
])
def test_bad_steps_raise(cfg, bad, match):
    prm = _params(cfg)
    p0, p1 = (1.0, 2.0, 3.0), (5.0, 2.0, 3.0)
    cases = {
        "empty": [],
        "pass_not_at_pos": [Step("pass", (p1, p0))],
        "zero_edge": [Step("pass", (p0, p0))],
        "short_pass": [Step("pass", (p0,))],
        "wait_no_duration": [Step("wait")],
        "wait_negative": [Step("wait", duration_s=-1.0)],
        "all_zero_travel": [Step("travel", (p0,))],
        "travel_two_points": [Step("travel", (p0, p1))],
        "unknown_kind": [Step("hover")],
    }
    with pytest.raises(ValueError, match=match):
        build_chain(1, p0, cases[bad], prm)


def test_sub_float32_travel_then_pass_continues_from_chain_position(cfg):
    prm = _params(cfg)
    p0 = (100.0, 0.0, 1.0)
    near = (100.0 + 1e-10, 0.0, 1.0)  # the same point for the Validator (float32)
    chain = build_chain(1, p0, [Step("travel", (near,)),
                                Step("pass", (near, (110.0, 0.0, 1.0)))], prm)
    assert [s.mode for s in chain] == [Mode.W, Mode.D, Mode.W]
    assert chain[1].start_xyz_mm == p0  # the seam keeps the chain's own end value


@pytest.mark.parametrize("args", [(0.0, 150.0, 1.0, 1.0), (8.0, -1.0, 1.0, 1.0),
                                  (8.0, 150.0, -1.0, 1.0), (8.0, 150.0, 1.0, float("nan"))])
def test_timing_params_reject_bad_values(args):
    with pytest.raises(ValueError):
        TimingParams(*args)


@pytest.mark.parametrize("which", ["on", "off"])
def test_missing_arc_time_is_an_error(which):
    class P:  # duck-typed config with one arc time omitted
        class process:
            deposition_speed_mm_s = 8.0
            travel_speed_mm_s = 150.0
            arc_on_time_s = None if which == "on" else 1.0
            arc_off_time_s = None if which == "off" else 1.0

    with pytest.raises(ValueError, match="arc"):
        TimingParams.from_config(P)


# ------------------------------------------------------------------ golden: real Validator


def _three_robot_chains(cfg, edges_per_robot):
    prm = _params(cfg)
    r = PrevalidateRules.from_config(cfg)
    chains = {}
    for rid, edges in zip((1, 2, 3), edges_per_robot):
        _, steps = _robot_steps(r, rid, rid, edges)
        chains[rid] = build_chain(rid, _start(r, rid), steps, prm)
    return chains


@pytest.mark.parametrize("edges_per_robot", [
    ([30.0, 20.0, 10.0], [25.0, 25.0], [40.0]),
    ([37.123456789, 1.5, 0.37, 11.0000001], [2.0, 3.0], [0.8, 0.9, 1.1]),  # short edges
    ([12.3] * 12, [7.77] * 5, [55.5, 0.61]),
    ([0.0004, 30.0], [0.0007, 5.0], [10.0]),  # micro edges near the float32 spacing
])
def test_golden_validator_accepts_built_chains(cfg, tmp_path, edges_per_robot):
    chains = _three_robot_chains(cfg, edges_per_robot)
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert ok_v, reasons
    assert any(s.mode is Mode.D for ch in chains.values() for s in ch)
    # prevalidate agrees and the schedule passes the writer gate
    rules = PrevalidateRules.from_config(cfg)
    assert pv.require_submittable(rules, _closed(cfg, chains)).ok


# A one-ulp D edge at |x| >= 512 mm: float32 spacing there is 2**-14 mm. The raw edge is
# 1.1 ulp long but the Validator reads 0 -> 2 ulp (+82 % speed) unless timing uses the
# quantized length (C-11). Positions are inside robot 2's reach and the workspace.
_ULP = 2.0 ** -14


def _ulp_case_chains(cfg):
    prm = _params(cfg)
    r = PrevalidateRules.from_config(cfg)
    z = layer_z(r, 2)
    x0, x1 = 600.0 + 0.45 * _ULP, 600.0 + 1.55 * _ULP
    chains = {}
    for rid in (1, 3):
        _, steps = _robot_steps(r, rid, rid, [30.0, 20.0])
        chains[rid] = build_chain(rid, _start(r, rid), steps, prm)
    steps2 = [Step("travel", ((x0, 0.0, z),)), Step("pass", ((x0, 0.0, z), (x1, 0.0, z))),
              Step("wait", duration_s=0.7)]
    chains[2] = build_chain(2, _start(r, 2), steps2, prm)
    return chains


def test_golden_one_ulp_edge_passes_validator_with_quantized_timing(cfg, tmp_path):
    chains = _ulp_case_chains(cfg)
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert ok_v, reasons
    rules = PrevalidateRules.from_config(cfg)
    assert pv.require_submittable(rules, _closed(cfg, chains)).ok


def test_golden_negative_control_raw_length_timing_is_rejected(cfg, tmp_path, monkeypatch):
    # The same schedule timed with the raw (unquantized) length must fail in the Validator:
    # this proves the case above discriminates C-11.
    monkeypatch.setattr(timing_mod, "_qdist", lambda a, b: math.dist(a, b))
    chains = _ulp_case_chains(cfg)
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert not ok_v and "DEPOSITION_SPEED_VIOLATION" in reasons, reasons


def test_golden_long_chain_large_times_is_accepted(cfg, tmp_path):
    """Many passes and t > 5000 s: seams stay exact through the CSV (repr) round trip."""
    prm = _params(cfg)
    r = PrevalidateRules.from_config(cfg)
    chains = {}
    for rid in (1, 2, 3):
        pts = _sector_pass(r, rid, rid, [15.0, 10.0])
        steps = []
        for _ in range(120 if rid == 1 else 1):
            steps += [Step("travel", (pts[0],)), Step("pass", pts), Step("wait", duration_s=60.0)]
        chains[rid] = build_chain(rid, _start(r, rid), steps, prm)
    assert chains[1][-1].end_time_s > 5000.0
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert ok_v, reasons
