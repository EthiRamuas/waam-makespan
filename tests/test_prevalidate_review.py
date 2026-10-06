"""Review-driven prevalidate tests: closed-timeline pop, margin-boundary sweep against the real
Validator, meaningful sample_job soundness, config variants, commit-order independence."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import numpy as np
import pytest

from gen import random_chain
from test_prevalidate import S, _cfg, _compare
from vref import COLLISION_CODES, timelines_of, validator_verdict, write_csv
from waam import prevalidate as pv
from waam.prevalidate import Code, PrevalidateRules, Timeline, check_all, try_append


def _b3(rules):
    b = rules.geom.base_xy[2]
    return (float(b[0]), float(b[1]), 1.0)


# ------------------------------------------------------------------ closed timeline + pop


def test_pop_last_reopens_closed_timeline_and_hold_is_rechecked(tmp_path):
    """Reviewer's counterexample: pop on a closed timeline used to leave a stale hold check."""
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    home2 = (500.0, 866.025404, 1.0)
    r1 = [S(1, "W", 0.0, 10.0, (-300.0, 0.0, 1.0), (-300.0, 0.0, 1.0)),
          S(1, "T", 10.0, 15.0, (-300.0, 0.0, 1.0), (-1000.0, 0.0, 1.0))]
    r2 = [S(2, "W", 0.0, 16.0, home2, home2),
          S(2, "T", 16.0, 26.0, home2, (-150.0, 0.0, 1.0)),
          S(2, "T", 26.0, 36.0, (-150.0, 0.0, 1.0), home2),
          S(2, "W", 36.0, 40.0, home2, home2)]
    r3 = [S(3, "W", 0.0, 40.0, _b3(rules), _b3(rules))]
    tls = pv.new_timelines()
    for seg in r1:
        assert try_append(rules, tls, seg).ok
    assert pv.close_timeline(rules, tls, 1).ok  # R1 ends parked at (-1000, 0): all fine
    for seg in r3 + r2:
        assert try_append(rules, tls, seg).ok
    assert check_all(rules, tls).ok

    tls[0].pop_last()  # R1 now ends at t=10 parked at (-300, 0): R2 reaches (-150, 0) at t=26
    assert not tls[0].closed  # popping reopens the timeline
    v = pv.close_timeline(rules, tls, 1)
    assert not v.ok and v.code is Code.ARM_ENVELOPE  # the new hold is re-checked, not trusted
    assert not tls[0].closed
    assert not check_all(rules, tls).ok
    chains = {1: r1[:1], 2: r2, 3: r3}
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert not ok_v and reasons & COLLISION_CODES  # measured on the real Validator


def test_close_is_idempotent_and_closed_timeline_rejects_appends():
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    tls = pv.new_timelines()
    park = (-1000.0, 0.0, 1.0)
    assert try_append(rules, tls, S(1, "W", 0.0, 5.0, park, park)).ok
    assert pv.close_timeline(rules, tls, 1).ok and pv.close_timeline(rules, tls, 1).ok
    assert tls[0].closed
    assert try_append(rules, tls, S(1, "W", 5.0, 6.0, park, park)).code is Code.TIMELINE_CLOSED
    with pytest.raises(ValueError):
        tls[0].append(S(1, "W", 5.0, 6.0, park, park))
    assert pv.close_timeline(rules, tls, 2).code is Code.MISSING_ROBOT  # empty timeline


def test_require_submittable_gate():
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    chains = {rid: [S(rid, "W", 0.0, 5.0, (h := next(r for r in cfg.robots if r.id == rid
                                                      ).home_xyz_mm)[:2] + (1.0,),
                      h[:2] + (1.0,))] for rid in (1, 2, 3)}
    tls = timelines_of(chains)
    with pytest.raises(ValueError, match="not closed"):
        pv.require_submittable(rules, tls)
    for rid in (1, 2, 3):
        assert pv.close_timeline(rules, tls, rid).ok
    assert pv.require_submittable(rules, tls).ok
    # a colliding schedule built WITHOUT checks cannot pass the gate even if everything is closed
    x = -249.999
    bad = timelines_of({1: [S(1, "T", 0.0, 0.23, (x, -4.0, 1.0), (x, 8.0, 1.0))],
                        2: [S(2, "W", 0.0, 0.23, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))],
                        3: [S(3, "W", 0.0, 0.23, _b3(rules), _b3(rules))]})
    for tl in bad:
        tl.closed = True
    with pytest.raises(ValueError, match="not valid"):
        pv.require_submittable(rules, bad)


def test_check_hold_includes_reach():
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    tls = pv.new_timelines()
    assert pv.check_hold(rules, tls, 1, (500.0, 0.0), 0.0).code is Code.ROBOT_XY_REACH_VIOLATION
    assert pv.check_hold(rules, tls, 1, (-1000.0, 0.0), 0.0).ok


def test_timeline_capacity_growth_and_pop_push_mix():
    tl = Timeline(1, capacity=1)
    rng = np.random.default_rng(8)
    segs, t, p = [], 0.0, (0.0, 0.0, 1.0)
    for i in range(300):
        q = tuple(float(v) for v in rng.uniform(-100, 100, 3))
        segs.append(S(1, "TDW"[i % 3], t, t + 1.0 + i * 0.001, p, q))
        t, p = segs[-1].end_time_s, q
    for i, seg in enumerate(segs):
        tl.append(seg)
        if i % 7 == 3:  # pop and push again around the growth boundaries
            tl.pop_last()
            tl.append(seg)
    ref = Timeline.from_segments(1, segs)
    assert tl.n_segments == ref.n_segments == 300
    np.testing.assert_array_equal(tl.t, ref.t)
    np.testing.assert_array_equal(tl.xyz, ref.xyz)
    np.testing.assert_array_equal(tl.mode, ref.mode)
    np.testing.assert_array_equal(tl.t[:-1], [s.start_time_s for s in segs])
    assert Timeline(2).t.shape == (0,) and Timeline(2).xyz.shape == (0, 3)


# ------------------------------------------------------------------ margin boundary sweep


@pytest.mark.parametrize("delta", [-2e-3, -1e-3, -3e-4, 0.0, 3e-4, 1e-3, 3e-3, 8e-3, 3e-2, 1.0])
@pytest.mark.parametrize("fine", [False, True])
def test_margin_boundary_sweep_vs_validator(delta, fine, tmp_path):
    """R1 sweeps vertically past parked R2; the true minimum arm margin is exactly ``delta``
    (R1's TCP reaches (xc, 0), R2's TCP is (-150, 0): margin = (-150 - xc) - 250)."""
    cfg = _cfg("model01")
    rules = PrevalidateRules.from_config(cfg)
    if fine:  # Lipschitz slack 0.01 mm: only the float32 buffer remains between us and the truth
        rules = replace(rules, max_step_mm=0.02)
    xc = -400.0 - delta
    chains = {
        1: [S(1, "T", 0.0, 4.0, (xc, -200.0, 1.0), (xc, 200.0, 1.0))],
        2: [S(2, "W", 0.0, 4.0, (-150.0, 0.0, 1.0), (-150.0, 0.0, 1.0))],
        3: [S(3, "W", 0.0, 4.0, _b3(rules), _b3(rules))],
    }
    rep = check_all(rules, timelines_of(chains))
    ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
    assert not (rep.ok and not ok_v), f"UNSOUND at margin {delta}: {reasons}"
    if delta <= -1e-3:
        assert not rep.ok and not ok_v  # real collision: both see it
    if fine and delta >= 3e-2:
        assert rep.ok and ok_v  # tight enough to accept a clear 3e-2 mm margin
    if not fine and delta >= 3e-4:
        assert ok_v  # the Validator passes these; our default slack (~1.25 mm) rejects them


# ------------------------------------------------------------------ soundness, more regimes


def test_soundness_sample_job_with_parked_others(tmp_path):
    """sample_job's 250 mm workspace makes random 3-robot schedules collide almost always.
    Parking R2/R3 at their bases leaves R1's rules (top reference!) meaningfully exercised."""
    cfg = _cfg("sample_job")
    rules = PrevalidateRules.from_config(cfg)
    rng = np.random.default_rng(31)
    stats: Counter = Counter()
    for i in range(400):
        c1 = random_chain(rng, rules, 1, edgy=0.15, stray=0.1)
        t_end = c1[-1].end_time_s
        chains = {1: c1}
        for rid in (2, 3):
            b = rules.geom.base_xy[rid - 1]
            chains[rid] = [S(rid, "W", 0.0, t_end, (float(b[0]), float(b[1]), 1.0),
                             (float(b[0]), float(b[1]), 1.0))]
        rep = check_all(rules, timelines_of(chains))
        ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
        _compare(rep, ok_v, reasons, i, stats)
    print(f"\n[sample_job parked] {dict(stats)}")
    assert stats["pre_ok_val_fail"] == 0
    assert stats["both_ok"] >= 30 and stats["both_fail"] >= 30


def _variant(cfg, name):
    if name == "touching_false":
        return cfg.model_copy(update={"collision": cfg.collision.model_copy(
            update={"touching_is_collision": False})})
    if name == "arm_check_off":
        return cfg.model_copy(update={"collision": cfg.collision.model_copy(
            update={"check_arm_envelope": False})})
    if name == "tcp_check_off":
        return cfg.model_copy(update={"collision": cfg.collision.model_copy(
            update={"check_tcp_radius": False})})
    if name == "workspace_offset":
        return cfg.model_copy(update={"workspace": cfg.workspace.model_copy(
            update={"center_xy_mm": (50.0, -30.0)})})
    if name == "speed_warns_only":
        return cfg.model_copy(update={"validation": cfg.validation.model_copy(
            update={"fail_on_speed_violation": False})})
    raise KeyError(name)


@pytest.mark.parametrize("variant", ["touching_false", "arm_check_off", "tcp_check_off",
                                     "workspace_offset", "speed_warns_only"])
def test_soundness_config_variants(variant, tmp_path):
    cfg = _variant(_cfg("model01"), variant)  # in-memory copies; no file is modified
    rules = PrevalidateRules.from_config(cfg)
    rng = np.random.default_rng(sum(map(ord, variant)))
    stats: Counter = Counter()
    for i in range(220):
        chains = {rid: random_chain(rng, rules, rid, edgy=0.08, stray=0.15) for rid in (1, 2, 3)}
        rep = check_all(rules, timelines_of(chains))
        ok_v, reasons = validator_verdict(write_csv(tmp_path / "t.csv", chains), cfg)
        _compare(rep, ok_v, reasons, i, stats)
    print(f"\n[{variant}] {dict(stats)}")
    assert stats["pre_ok_val_fail"] == 0
    assert stats["both_ok"] >= 5


# ------------------------------------------------------------------ commit-order independence


def _order(chains, kind, rng):
    if kind == "by_time":
        return sorted([s for c in chains.values() for s in c], key=lambda s: (s.start_time_s, s.robot_id))
    if kind == "robot_sequential":
        return [s for rid in (1, 2, 3) for s in chains[rid]]
    queues = {rid: list(c) for rid, c in chains.items()}
    out = []
    while any(queues.values()):  # random interleave, per-robot order preserved
        rid = int(rng.choice([r for r, q in queues.items() if q]))
        out.append(queues[rid].pop(0))
    return out


@pytest.mark.parametrize("kind", ["by_time", "robot_sequential", "random_interleave"])
@pytest.mark.parametrize("name", ["model01", "sample_job"])
def test_incremental_verdict_is_independent_of_commit_order(kind, name):
    cfg = _cfg(name)
    rules = PrevalidateRules.from_config(cfg)
    rng = np.random.default_rng(1234)
    stats: Counter = Counter()
    for i in range(150):
        chains = {rid: random_chain(rng, rules, rid, edgy=0.08, stray=0.2) for rid in (1, 2, 3)}
        full = check_all(rules, timelines_of(chains))
        tls = pv.new_timelines()
        remaining = {rid: len(c) for rid, c in chains.items()}
        accepted = True
        for seg in _order(chains, kind, rng):
            v = try_append(rules, tls, seg)
            remaining[seg.robot_id] -= 1
            if v.ok and remaining[seg.robot_id] == 0:
                v = pv.close_timeline(rules, tls, seg.robot_id)
            if not v.ok:
                accepted = False
                break
        assert accepted == full.ok, f"{kind} #{i}: incremental {accepted} vs full {full.ok}"
        stats[accepted] += 1
    assert stats[False] >= 20
    if name == "model01":
        assert stats[True] >= 5
