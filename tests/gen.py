"""Seeded random schedules for soundness tests (config-driven, no model-specific numbers).

Each robot gets a chain of T/D/W segments. Most points sit in the robot's own sector of the
workspace so a healthy share of schedules is valid; a configurable share is deliberately
pushed to rule boundaries (speed exactly at +-tolerance, Z at the layer tolerance, W moves
near the wait tolerance) or into other robots' sectors / the whole disc to provoke
reach violations and collisions.
"""

from __future__ import annotations

import math

import numpy as np

from waam.prevalidate import PrevalidateRules
from waam.segment import Segment


def layer_z(r: PrevalidateRules, k: int) -> float:
    return r.build_plane_z_mm + ((k + 0.5) if r.tcp_z_center else (k + 1)) * r.layer_height_mm


def sector_point(rng, r: PrevalidateRules, sector: int, wide: bool) -> tuple[float, float]:
    g = r.geom
    base = g.base_xy[sector - 1] - g.ws_center_xy
    ang = math.atan2(base[1], base[0]) + rng.uniform(-0.45, 0.45)
    if wide:
        ang = rng.uniform(0.0, 2.0 * math.pi)
    rad = g.ws_radius_mm * rng.uniform(0.05, 0.88 if not wide else 1.02)
    return (float(g.ws_center_xy[0] + rad * math.cos(ang)),
            float(g.ws_center_xy[1] + rad * math.sin(ang)))


def _dur_for_speed(length: float, speed: float, floor: float = 0.5) -> float:
    return max(length / speed, floor) if length > 0 else floor


def random_chain(rng, r: PrevalidateRules, rid: int, *, edgy: float = 0.15,
                 stray: float = 0.25) -> list[Segment]:
    """One robot's chain. ``edgy`` = share of rule-boundary values, ``stray`` = share of
    points drawn from another robot's sector or the whole disc."""
    n = int(rng.integers(1, 5))
    modes = [str(m) for m in rng.choice(["T", "D", "W"], size=n, p=[0.3, 0.45, 0.25])]
    wide = rng.random() < stray
    sector = rid if rng.random() > stray else int(rng.integers(1, 4))
    zl = layer_z(r, int(rng.integers(0, 4)))

    # waypoints joined by W segments are one location (a "group")
    group = [0]
    for m in modes:
        group.append(group[-1] if m == "W" else group[-1] + 1)
    n_groups = group[-1] + 1
    has_d = [False] * n_groups
    for i, m in enumerate(modes):
        if m == "D":
            has_d[group[i]] = has_d[group[i + 1]] = True
    gxy = [sector_point(rng, r, sector, wide) for _ in range(n_groups)]
    gz = [zl if has_d[k] else float(rng.uniform(0.0, 200.0)) for k in range(n_groups)]

    segs: list[Segment] = []
    t = 0.0
    p_prev = (gxy[0][0], gxy[0][1], gz[0])
    for i, m in enumerate(modes):
        p0 = p_prev
        tgt = (gxy[group[i + 1]][0], gxy[group[i + 1]][1], gz[group[i + 1]])
        if m == "W":
            p1 = p0
            if rng.random() < edgy:
                p1 = (p0[0] + float(rng.choice([0.0004, 0.0009, 0.0011, 0.002])), p0[1], p0[2])
        elif m == "D":
            dz = float(rng.choice([0.1, 0.2499, 0.2501, 0.4, -0.3])) if rng.random() < edgy else 0.0
            p1 = (tgt[0], tgt[1], tgt[2] + dz)
        else:
            p1 = tgt
        length = math.dist(p0, p1)
        if m == "W":
            dur = float(rng.uniform(0.5, 6.0))
        elif m == "D":
            vd, tol = r.deposition_speed_mm_s, r.speed_relative_tolerance
            v = (float(rng.choice([vd * (1 + tol), vd * (1 - tol), vd * 1.0999, vd * 0.9001,
                                   vd * 1.12, vd * 0.85]))
                 if rng.random() < edgy else vd)
            dur = _dur_for_speed(length, v)
        else:
            vt, tol = r.travel_speed_mm_s, r.speed_relative_tolerance
            v = (float(rng.choice([vt * (1 + tol), vt * 1.0999, vt * 1.12, vt * 0.5]))
                 if rng.random() < edgy else vt * float(rng.uniform(0.3, 0.9)))
            dur = _dur_for_speed(length, v)
        segs.append(Segment(rid, m, t, t + dur, p0, p1))
        t, p_prev = t + dur, p1
    return segs


def random_chains(rng, r: PrevalidateRules, **kw) -> dict[int, list[Segment]]:
    return {rid: random_chain(rng, r, rid, **kw) for rid in (1, 2, 3)}
