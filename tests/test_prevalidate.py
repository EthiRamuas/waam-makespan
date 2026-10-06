"""prevalidate vs the real Validator (golden tests run the Validator itself).

Soundness is the contract: prevalidate OK  =>  Validator passes everything but shape.
False rejects are allowed but only for collisions (the per-robot rules are exact), and
their rate is printed (``pytest -s``) so it is reported, not assumed.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from waam_validator.config.loader import load_config
from waam_validator.trajectory.loader import load_trajectory_csv

from gen import layer_z, random_chains
from vref import (COLLISION_CODES, MODEL01_DIR, SAMPLE_JOB, timelines_of, validator_verdict,
                  write_csv)
from waam import geometry as geo
from waam import prevalidate as pv
from waam.prevalidate import Code, PrevalidateRules, Timeline, check_all, try_append
from waam.segment import Segment

CONFIGS = {"sample_job": SAMPLE_JOB, "model01": MODEL01_DIR}


def _cfg(name):
    d = CONFIGS[name]
    if not (d / "config.yaml").exists():
        if os.environ.get("WAAM_REQUIRE_REF"):  # CI / full runs: a missing reference is an error
            pytest.fail(f"reference config {d} is required but missing")
        pytest.skip(f"{d} not available")
    return load_config(d / "config.yaml")


@pytest.fixture(params=sorted(CONFIGS))
def cfg(request):
    return _cfg(request.param)


@pytest.fixture
def rules(cfg):
    return PrevalidateRules.from_config(cfg)


def S(rid, mode, t0, t1, p0, p1):
    return Segment(rid, mode, t0, t1, p0, p1)


# ------------------------------------------------------------------ buffer / quantization


def test_buffer_policy(cfg):
    g = geo.CellGeometry.from_config(cfg)
    computed = pv.float32_buffer_mm(g, min_buffer_mm=0.0)
    assert computed > 0
    r = PrevalidateRules.from_config(cfg)
    assert r.buffer_mm == max(computed, 1e-3)  # beta = max(computed, 1e-3 mm)
    assert PrevalidateRules.from_config(cfg, min_buffer_mm=5.0).buffer_mm == 5.0
    big = geo.CellGeometry.from_config(cfg)
    big = type(big)(**{**{f: getattr(big, f) for f in big.__slots__}, "reach_mm": big.reach_mm * 100})
    assert pv.float32_buffer_mm(big, 0.0) > computed  # grows with the coordinate range


def test_quantize_matches_validator_loader(tmp_path):
    cfg = _cfg("sample_job")
    rng = np.random.default_rng(5)
    chains = {rid: [] for rid in (1, 2, 3)}
    for rid in chains:
        t, p = 0.0, tuple(rng.uniform(-2000, 2000, 3))
        for _ in range(6):
            q = tuple(rng.uniform(-2000, 2000, 3))
            chains[rid].append(S(rid, "T", t, t + float(rng.uniform(0.1, 9.9)), p, q))
            t, p = chains[rid][-1].end_time_s, q
    tls = timelines_of(chains)
    for raw in (False, True):  # text = float32-roundtrip repr, or plain float64 repr
        ts = load_trajectory_csv(write_csv(tmp_path / f"t{raw}.csv", chains, raw=raw), cfg)
        for tl, traj in zip(tls, ts.robots):
            np.testing.assert_array_equal(traj.xyz_mm.astype(np.float64), tl.xyz)
            np.testing.assert_array_equal(traj.time_s, tl.t)


# ------------------------------------------------------------------ the soundness contract


def _compare(rep, ok_v, reasons, i, stats):
    pre_codes = {v.code.name for v in rep.violations}
    pre_local = pre_codes - COLLISION_CODES
    val_local = reasons - COLLISION_CODES
    assert not (rep.ok and not ok_v), f"UNSOUND #{i}: prevalidate OK, Validator FAIL {reasons}"
    # per-robot rules are exact: same yes/no, and the Validator's code is among ours
    assert bool(pre_local) == bool(val_local), f"#{i}: local rules differ {pre_codes} vs {reasons}"
    assert val_local <= pre_local, f"#{i}: {val_local} not in {pre_local}"
    if rep.ok and ok_v:
        stats["both_ok"] += 1
    elif not rep.ok and not ok_v:
        stats["both_fail"] += 1
        if (pre_codes & COLLISION_CODES) and (reasons & COLLISION_CODES):
            stats["both_flag_collision"] += 1
    else:  # prevalidate rejects, Validator passes: allowed only for collisions
        assert not pre_local, f"#{i}: false reject on an exact rule {pre_codes}"
        stats["false_reject_collision"] += 1
    stats["pre_ok_val_fail"] += int(rep.ok and not ok_v)


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_soundness_random_schedules_vs_validator(name, tmp_path):
    cfg = _cfg(name)
    rules = PrevalidateRules.from_config(cfg)
    rng = np.random.default_rng(20240607)
    stats: Counter = Counter()
    n = 600
    for i in range(n):
        chains = random_chains(rng, rules, edgy=0.08, stray=0.15)
        rep = check_all(rules, timelines_of(chains))
        ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
        _compare(rep, ok_v, reasons, i, stats)
    print(f"\n[{name}] n={n} {dict(stats)} "
          f"false-reject rate among Validator-PASS="
          f"{stats['false_reject_collision'] / max(1, stats['false_reject_collision'] + stats['both_ok']):.3f}")
    assert stats["pre_ok_val_fail"] == 0  # the contract: zero false accepts
    # the test must not be vacuous: both outcomes and collision agreement are exercised
    # sample_job's 250 mm workspace squeezes all three arms into one 250 mm zone, so random
    # schedules there are (almost) never collision-free: the "both OK" floor applies to model01.
    assert stats["both_fail"] >= 15 and stats["both_flag_collision"] >= 3
    if name == "model01":
        assert stats["both_ok"] >= 15


def test_soundness_collision_dense_vs_validator(tmp_path):
    """Collision-heavy schedules (everyone mostly in the same region, all rules satisfied)."""
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    rng = np.random.default_rng(777)
    stats: Counter = Counter()
    for i in range(250):
        chains = random_chains(rng, rules, edgy=0.0, stray=0.7)
        rep = check_all(rules, timelines_of(chains))
        ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
        _compare(rep, ok_v, reasons, i, stats)
        stats["collision_seen"] += int(bool(reasons & COLLISION_CODES))
    print(f"\n[collision-dense] {dict(stats)}")
    assert stats["pre_ok_val_fail"] == 0
    assert stats["collision_seen"] >= 15


# ------------------------------------------------------------------ one reason code per rule


def _parked(cfg, t_end):
    """All robots parked at their config home XY, z=1.0 (collision-free)."""
    out = {}
    for rid in (1, 2, 3):
        h = next(r for r in cfg.robots if r.id == rid).home_xyz_mm
        out[rid] = [S(rid, "W", 0.0, t_end, (h[0], h[1], 1.0), (h[0], h[1], 1.0))]
    return out


def _replace_r1(cfg, segs, t_end=40.0):
    chains = _parked(cfg, t_end)
    chains[1] = segs
    return chains


def _reason_cases(r):
    z = layer_z(r, 0)
    home = (-1000.0, 0.0, 1.0)
    # R1 chain pieces: T from home to p at a comfortable speed, then the case-specific segment
    def go(p, t0=0.0, dur=12.0):
        return S(1, "T", t0, t0 + dur, home, p)
    cases = {}
    p = (-698.0, 0.0, z)
    cases["DEPOSITION_OUTSIDE_WORKSPACE"] = [go(p), S(1, "D", 12.0, 12.0 + 58 / 8, p, (-640.0, 0.0, z))]
    p = (0.0, 0.0, z)
    cases["DEPOSITION_ZERO_LENGTH"] = [go(p), S(1, "D", 12.0, 14.0, p, p)]
    cases["DEPOSITION_VERTICAL_MOVE"] = [go(p), S(1, "D", 12.0, 18.25, p, (50.0, 0.0, z + 1.0))]
    pb = (0.0, 0.0, -1.0)
    cases["DEPOSITION_BELOW_BUILD_PLANE"] = [go(pb), S(1, "D", 12.0, 18.25, pb, (50.0, 0.0, -1.0))]
    pl = (0.0, 0.0, z + 1.0)  # half a layer off the layer grid
    cases["DEPOSITION_LAYER_MISMATCH"] = [go(pl), S(1, "D", 12.0, 18.25, pl, (50.0, 0.0, z + 1.0))]
    cases["WAIT_POSITION_CHANGED"] = [go(p), S(1, "W", 12.0, 15.0, p, (1.0, 0.0, z))]
    cases["DEPOSITION_SPEED_VIOLATION"] = [go(p), S(1, "D", 12.0, 15.0, p, (50.0, 0.0, z))]
    cases["TRAVEL_SPEED_VIOLATION"] = [S(1, "T", 0.0, 5.0, home, (0.0, 0.0, z)),
                                       S(1, "T", 5.0, 10.0, (0.0, 0.0, z), (-1000.0, 0.0, 1.0))]
    cases["ROBOT_XY_REACH_VIOLATION"] = [S(1, "T", 0.0, 20.0, home, (101.0, 0.0, z))]
    return cases


@pytest.mark.parametrize("code", ["DEPOSITION_OUTSIDE_WORKSPACE", "DEPOSITION_ZERO_LENGTH",
                                  "DEPOSITION_VERTICAL_MOVE", "DEPOSITION_BELOW_BUILD_PLANE",
                                  "DEPOSITION_LAYER_MISMATCH", "WAIT_POSITION_CHANGED",
                                  "DEPOSITION_SPEED_VIOLATION", "TRAVEL_SPEED_VIOLATION",
                                  "ROBOT_XY_REACH_VIOLATION"])
def test_reason_codes_match_validator(code, tmp_path):
    cfg = _cfg("model01")  # fail_on_speed_violation = true there
    rules = PrevalidateRules.from_config(cfg)
    chains = _replace_r1(cfg, _reason_cases(rules)[code])
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    rep = check_all(rules, timelines_of(chains))
    assert not ok_v and code in reasons, reasons
    assert not rep.ok and code in {v.code.name for v in rep.violations}, rep
    assert rep.verdict.code.name == code or code == "ROBOT_XY_REACH_VIOLATION"


def test_speed_codes_are_warnings_when_validator_config_says_so(tmp_path):
    cfg = _cfg("sample_job")  # fail_on_speed_violation = false
    rules = PrevalidateRules.from_config(cfg)
    chains = _replace_r1(cfg, _reason_cases(rules)["TRAVEL_SPEED_VIOLATION"])
    # sample_job geometry differs; only the speed rule matters, R1 stays inside reach 2500
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    rep = check_all(rules, timelines_of(chains))
    assert rep.ok == ok_v
    assert Code.TRAVEL_SPEED_VIOLATION in {w.code for w in rep.warnings}


def test_fixture_sample_job_and_speed_flag_flip():
    cfg = load_config(SAMPLE_JOB / "config.yaml")
    rows = [r.split(",") for r in (SAMPLE_JOB / "trajectory.csv").read_text().splitlines()[1:]]
    chains = {rid: [] for rid in (1, 2, 3)}
    by = {rid: [(float(r[1]), (float(r[2]), float(r[3]), float(r[4])), r[5])
                for r in rows if int(r[0]) == rid] for rid in (1, 2, 3)}
    for rid, pts in by.items():
        for (t0, p0, m), (t1, p1, _) in zip(pts, pts[1:]):
            chains[rid].append(S(rid, m, t0, t1, p0, p1))
    rules = PrevalidateRules.from_config(cfg)
    rep = check_all(rules, timelines_of(chains))
    ok_v, reasons = validator_verdict(SAMPLE_JOB / "trajectory.csv", cfg)
    assert rep.ok and ok_v  # Validator summary.json: PASS (2 travel-speed warnings)
    assert [w.code for w in rep.warnings] == [Code.TRAVEL_SPEED_VIOLATION] * 2
    # flip the flag in memory (no file is touched): both must now fail on the travel speed
    strict = cfg.model_copy(update={
        "validation": cfg.validation.model_copy(update={"fail_on_speed_violation": True})})
    rep2 = check_all(PrevalidateRules.from_config(strict), timelines_of(chains))
    ok2, reasons2 = validator_verdict(SAMPLE_JOB / "trajectory.csv", strict)
    assert not rep2.ok and not ok2
    assert reasons2 == {"TRAVEL_SPEED_VIOLATION"}
    assert {v.code.name for v in rep2.violations} == {"TRAVEL_SPEED_VIOLATION"}


# ------------------------------------------------------------------ collision goldens


def test_golden_counterexample_rejected_like_validator(tmp_path):
    """The earlier sampled-only counterexample (n=5 says safe, Validator says FAIL)."""
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    g = rules.geom
    x, dt = -249.999, 0.23
    r1 = [S(1, "T", 0.0, dt, (x, -4.0, 1.0), (x, 8.0, 1.0))]
    r2 = [S(2, "W", 0.0, dt, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))]
    b3 = (float(g.base_xy[2][0]), float(g.base_xy[2][1]), 1.0)
    r3 = [S(3, "W", 0.0, dt, b3, b3)]
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", {1: r1, 2: r2, 3: r3}), cfg)
    assert not ok_v and "ARM_ENVELOPE" in reasons  # measured on the real Validator
    tls = pv.new_timelines()
    assert try_append(rules, tls, r2[0]).ok and try_append(rules, tls, r3[0]).ok
    v = try_append(rules, tls, r1[0])
    assert not v.ok and v.code is Code.ARM_ENVELOPE and (v.robot, v.other) == (1, 2)
    assert tls[0].n_segments == 0  # rolled back
    assert not check_all(rules, timelines_of({1: r1, 2: r2, 3: r3})).ok


def test_golden_parked_robot_is_still_an_obstacle(tmp_path):
    """R1 finishes at t=10 and parks; R2 arrives only after t=10 (hold must be checked)."""
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    g = rules.geom
    park = (-300.0, 0.0, 1.0)
    r1 = [S(1, "W", 0.0, 10.0, park, park)]
    r2 = [S(2, "T", 0.0, 20.0, (500.0, 866.0, 1.0), (-150.0, 0.0, 1.0)),
          S(2, "W", 20.0, 30.0, (-150.0, 0.0, 1.0), (-150.0, 0.0, 1.0))]
    b3 = (float(g.base_xy[2][0]), float(g.base_xy[2][1]), 1.0)
    r3 = [S(3, "W", 0.0, 30.0, b3, b3)]
    chains = {1: r1, 2: r2, 3: r3}
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert not ok_v and reasons & COLLISION_CODES  # R1's hold to the makespan is checked
    tls = pv.new_timelines()
    assert try_append(rules, tls, r1[0]).ok and try_append(rules, tls, r3[0]).ok
    assert pv.close_timeline(rules, tls, 1).ok and pv.close_timeline(rules, tls, 3).ok
    v = try_append(rules, tls, r2[0])  # collision only in the part after R1's last time
    assert not v.ok and v.code.name in reasons
    assert v.t >= 10.0  # found in R1's hold window, never while R1 was still moving
    # without close, the open R1 is only known until t=10, so the same append passes (by design)
    tls_open = pv.new_timelines()
    assert try_append(rules, tls_open, r1[0]).ok and try_append(rules, tls_open, r3[0]).ok
    assert try_append(rules, tls_open, r2[0]).ok
    # moving R2 elsewhere is fine, and check_hold agrees with the Validator on parking spots
    assert pv.check_hold(rules, tls, 2, (-150.0, 0.0), 10.0).ok is False
    assert pv.check_hold(rules, tls, 2, (500.0, 866.0), 10.0).ok is True


def test_check_hold_sound_vs_validator(tmp_path):
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    g = rules.geom
    b = [(float(g.base_xy[i][0]), float(g.base_xy[i][1]), 1.0) for i in range(3)]
    r1 = [S(1, "W", 0.0, 5.0, (-1000.0, 0.0, 1.0), (-1000.0, 0.0, 1.0)),
          S(1, "T", 5.0, 15.0, (-1000.0, 0.0, 1.0), (-300.0, 200.0, 1.0))]
    r3 = [S(3, "W", 0.0, 15.0, b[2], b[2])]
    tls = timelines_of({1: r1, 2: [S(2, "W", 0.0, 1.0, b[1], b[1])], 3: r3})
    rng = np.random.default_rng(3)
    n_ok = n_bad = 0
    for _ in range(60):
        xy = (float(rng.uniform(-300, 700)), float(rng.uniform(-100, 900)))
        if not geo.in_reach(rules.geom, 2, xy):
            continue
        v = pv.check_hold(rules, tls, 2, xy, 0.0)
        r2 = [S(2, "W", 0.0, 15.0, (xy[0], xy[1], 1.0), (xy[0], xy[1], 1.0))]
        ok_v, _ = validator_verdict(write_csv(tmp_path / "t.csv", {1: r1, 2: r2, 3: r3}), cfg)
        assert not (v.ok and not ok_v), f"check_hold unsound at {xy}"
        n_ok += int(v.ok)
        n_bad += int(not v.ok)
    assert n_ok >= 5 and n_bad >= 5


# ------------------------------------------------------------------ incremental == full


def _interleaved(chains):
    segs = [s for c in chains.values() for s in c]
    return sorted(segs, key=lambda s: (s.start_time_s, s.robot_id))


def test_incremental_equals_full_and_rolls_back(rules, cfg, tmp_path):
    rng = np.random.default_rng(99)
    stats: Counter = Counter()
    for i in range(200):
        chains = random_chains(rng, rules, edgy=0.1, stray=0.3)
        full = check_all(rules, timelines_of(chains))
        tls = pv.new_timelines()
        accepted = True
        remaining = {rid: len(c) for rid, c in chains.items()}
        for seg in _interleaved(chains):
            before = [(tl.n_segments, tl.t.copy(), tl.xyz.copy()) for tl in tls]
            v = try_append(rules, tls, seg)
            append_rejected = not v.ok
            remaining[seg.robot_id] -= 1
            if v.ok and remaining[seg.robot_id] == 0:  # robot done: it now holds forever
                v = pv.close_timeline(rules, tls, seg.robot_id)
                if not v.ok:
                    assert not tls[seg.robot_id - 1].closed  # a failed close leaves it open
            if not v.ok:
                accepted = False
                if append_rejected:
                    for tl, (n, t, xyz) in zip(tls, before):  # rejection leaves no trace
                        assert tl.n_segments == n
                        np.testing.assert_array_equal(tl.t, t)
                        np.testing.assert_array_equal(tl.xyz, xyz)
                break
        assert accepted == full.ok, f"#{i}: incremental {accepted} vs full {full.ok} {full.violations[:2]}"
        stats[accepted] += 1
        if accepted:  # and the final timelines judge the same way as a fresh build
            assert check_all(rules, tls).ok
    assert stats[False] >= 8
    if cfg.workspace.radius_mm > 500:  # sample_job's 250 mm workspace is never collision-free
        assert stats[True] >= 8


def test_chain_errors_are_reported_not_raised(rules):
    tls = pv.new_timelines()
    seg = S(1, "W", 1.0, 2.0, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
    assert try_append(rules, tls, seg).code is Code.CHAIN_TIME_MISMATCH  # must start at 0.0
    ok = S(1, "W", 0.0, 2.0, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
    assert try_append(rules, tls, ok).ok
    assert try_append(rules, tls, S(1, "W", 2.0, 3.0, (5.0, 0.0, 1.0), (5.0, 0.0, 1.0))
                      ).code is Code.CHAIN_POSITION_JUMP
    with pytest.raises(ValueError):
        tls[0].append(S(1, "W", 9.0, 10.0, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)))
    assert check_all(rules, tls).verdict.code is Code.MISSING_ROBOT
