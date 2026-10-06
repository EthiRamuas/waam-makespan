"""Benchmark prevalidate (development measurement, no targets assumed).

    python -m experiments.bench_prevalidate [--reps 300] [--out experiments/bench_prevalidate.csv]

Scenarios (model-01 cell config read from the Validator checkout, read-only):
  local        check_segment_local on one D segment
  append(M)    try_append (accepted) onto robots that already hold M segments each
  overlap(L)   try_append of one long segment that overlaps L committed segments of another robot
  reject       try_append that collides (rolled back)
  hold(L)      check_hold against L overlapping committed segments
  check_all(M) full check of three robots with M segments each
  validator(M) the real Validator (loader + rules + schedule + collision, no shape) on the same
This is a dev-machine measurement; official compute time must be taken on the fixed machine.
"""

from __future__ import annotations

import argparse
import csv
import math
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from waam_validator.config.loader import load_config  # noqa: E402

from waam import geometry as geo  # noqa: E402
from waam import prevalidate as pv  # noqa: E402
from waam.segment import Segment  # noqa: E402

CONFIG = Path("C:/Github/WAAM_Validator/tests/01/config.yaml")
SEED = 20241006


def _sector_point(rng, rules, rid):
    g = rules.geom
    base = g.base_xy[rid - 1] - g.ws_center_xy
    ang = math.atan2(base[1], base[0]) + rng.uniform(-0.25, 0.25)
    rad = rng.uniform(350.0, 600.0)
    return (float(rad * math.cos(ang)), float(rad * math.sin(ang)), 1.0)


def context_chain(rng, rules, rid, m, t_start=0.0, p_start=None):
    """m valid segments (D/T/W cycle) at z=1 inside the robot's own sector."""
    p = p_start or _sector_point(rng, rules, rid)
    t = t_start
    out = []
    for i in range(m):
        kind = "DTW"[i % 3]
        if kind == "W":
            q, dur = p, 1.0
        else:
            q = _sector_point(rng, rules, rid)
            length = math.dist(p, q)
            speed = rules.deposition_speed_mm_s if kind == "D" else 75.0
            dur = max(length / speed, 0.5)
        out.append(Segment(rid, kind, t, t + dur, p, q))
        t, p = t + dur, q
    return out


def build_context(rng, rules, m):
    tls = pv.new_timelines()
    for rid in (1, 2, 3):
        for seg in context_chain(rng, rules, rid, m):
            v = pv.try_append(rules, tls, seg)
            if not v.ok:  # keep the context valid: rebuild this robot's chain from scratch
                raise RuntimeError(f"context rejected: {v}")
    return tls


def timeit(fn, reps, setup=None, teardown=None):
    ts = []
    for _ in range(reps):
        if setup:
            setup()
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1e6)
        if teardown:
            teardown()
    ts.sort()
    return {"n": reps, "median_us": statistics.median(ts), "p95_us": ts[int(0.95 * (reps - 1))],
            "mean_us": statistics.fmean(ts), "min_us": ts[0]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--out", default=str(Path(__file__).with_name("bench_prevalidate.csv")))
    args = ap.parse_args()
    cfg = load_config(CONFIG)
    rules = pv.PrevalidateRules.from_config(cfg)
    rows = []

    def record(name, params, res):
        rows.append({"scenario": name, "params": params, **res})
        print(f"{name:<24}{params:<24}median {res['median_us']:>10.1f} us   p95 {res['p95_us']:>10.1f} us"
              f"   mean {res['mean_us']:>10.1f} us", flush=True)

    orig = geo.intervals_collide

    def with_prefilter(on):
        geo.intervals_collide = (lambda *a, **k: orig(*a, **{**k, "prefilter": on}))

    # ---- local
    rng = np.random.default_rng(SEED)
    seg = Segment(1, "D", 0.0, 5.0, (-400.0, 0.0, 1.0), (-360.0, 0.0, 1.0))
    record("local", "D segment", timeit(lambda: pv.check_segment_local(rules, seg), args.reps))

    for prefilter in (True, False):
        with_prefilter(prefilter)
        tag = "" if prefilter else " [no AABB]"
        # ---- append onto M committed segments
        for m in (10, 100, 1000):
            rng = np.random.default_rng(SEED)
            tls = build_context(rng, rules, m)
            last = tls[0]
            p0 = tuple(last.xyz[-1])
            cand = Segment(1, "D", last.end_time, last.end_time + 5.0, p0,
                           (p0[0] + 40.0, p0[1], 1.0))
            ok = pv.try_append(rules, tls, cand)
            if not ok.ok:  # pick a reachable, collision-free candidate: stay put
                cand = Segment(1, "W", last.end_time, last.end_time + 1.0, p0, p0)
                assert pv.try_append(rules, tls, cand).ok
            tls[0].pop_last()
            res = timeit(lambda: pv.try_append(rules, tls, cand), args.reps, teardown=tls[0].pop_last)
            record("append" + tag, f"M={m}", res)

        # ---- one long segment overlapping L committed segments of another robot
        for L in (1, 10, 100, 1000):
            rng = np.random.default_rng(SEED)
            tls = pv.new_timelines()
            total = 25.0
            home2 = _sector_point(rng, rules, 2)
            for i in range(L):
                t0, t1 = total * i / L, total * (i + 1) / L
                assert pv.try_append(rules, tls, Segment(2, "W", t0, t1, home2, home2)).ok
            p1 = _sector_point(rng, rules, 1)
            p2 = (p1[0] + 200.0, p1[1], 1.0)
            cand = Segment(1, "D", 0.0, 25.0, p1, p2)
            assert pv.try_append(rules, tls, cand).ok, "overlap scenario must be collision-free"
            tls[0].pop_last()
            res = timeit(lambda: pv.try_append(rules, tls, cand), args.reps, teardown=tls[0].pop_last)
            record("overlap" + tag, f"L={L}", res)

        # ---- full check
        for m in (100, 1000):
            rng = np.random.default_rng(SEED)
            tls = build_context(rng, rules, m)
            reps = max(5, args.reps // (20 if m >= 1000 else 5))
            res = timeit(lambda: pv.check_all(rules, tls), reps)
            record("check_all" + tag, f"M={m}", res)

    geo.intervals_collide = orig

    # ---- rejection (collision with a parked robot)
    rng = np.random.default_rng(SEED)
    tls = pv.new_timelines()
    park = (-150.0, 0.0, 1.0)
    assert pv.try_append(rules, tls, Segment(2, "W", 0.0, 60.0, park, park)).ok
    assert pv.close_timeline(rules, tls, 2).ok
    bad = Segment(1, "D", 0.0, 43.75, (-700.0, 0.0, 1.0), (-350.0, 0.0, 1.0))
    assert not pv.try_append(rules, tls, bad).ok
    record("reject", "vs parked R2", timeit(lambda: pv.try_append(rules, tls, bad), args.reps))

    # ---- check_hold
    for L in (1, 100):
        rng = np.random.default_rng(SEED)
        tls = pv.new_timelines()
        total = 25.0
        home2 = _sector_point(rng, rules, 2)
        for i in range(L):
            assert pv.try_append(rules, tls, Segment(2, "W", total * i / L, total * (i + 1) / L,
                                                     home2, home2)).ok
        xy = _sector_point(rng, rules, 1)[:2]
        record("hold", f"L={L}", timeit(lambda: pv.check_hold(rules, tls, 1, xy, 0.0), args.reps))

    # ---- the real Validator on the same schedule (reference, M=100)
    from vref import timelines_of, validator_verdict, write_csv  # noqa: E402

    rng = np.random.default_rng(SEED)
    chains = {rid: context_chain(rng, rules, rid, 100) for rid in (1, 2, 3)}
    with tempfile.TemporaryDirectory() as d:
        path = write_csv(Path(d) / "t.csv", chains)
        ok_v, reasons = validator_verdict(path, cfg)
        assert ok_v, reasons
        record("validator", "M=100", timeit(lambda: validator_verdict(path, cfg), 5))
    record("check_all", "M=100 (same)", timeit(lambda: pv.check_all(rules, timelines_of(chains)), 20))

    meta = f"python {platform.python_version()}, numpy {np.__version__}, {platform.processor()}"
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "params", "n", "median_us", "p95_us",
                                          "mean_us", "min_us"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n{meta}\nbuffer_mm={rules.buffer_mm}  saved: {args.out}")


if __name__ == "__main__":
    main()
