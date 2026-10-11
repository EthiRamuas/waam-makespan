"""Standby positions (B7) and end-of-work parking candidates (B9 (a)).

B7: robot i waits on the ray origin -> its base, at distance rho from the origin. For every other
robot j let K_j be the D vertices j reaches (all layers) and A_j = conv({base_j} U K_j): the union
of j's arm segments to any point of conv(K_j) (convexity). The standby segment [base_i, s(rho)]
must keep dist >= arm_i + arm_j + arm_clearance + float32_buffer_mm from every A_j. The TCP rule is
implied (arm-to-arm segment distance <= TCP-to-TCP distance and the arm requirement is not smaller).
rho is the smallest integer mm for which this holds (the condition is monotone in rho: a larger rho
shortens the segment).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
from shapely.geometry import LineString, MultiPoint

from . import geometry as geo
from .prevalidate import float32_buffer_mm
from .strategy import Cell

# probe_06 A2/D5 (hypothesis, not measured): park = home + lambda (base - home) in XY, z = home z.
PARK_LAMBDAS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _points(items: Iterable[Any]) -> np.ndarray:
    chunks = [np.asarray(q.vertices, dtype=np.float64).reshape(-1, 2) for q in items]
    if not chunks:
        return np.empty((0, 2))
    return np.unique(np.round(np.vstack(chunks), 3), axis=0)


def arm_hulls(cell: Cell, items: Iterable[Any]) -> list[Any]:
    """A_j = conv({base_j} U K_j) for every robot (config order); ``items`` have ``.vertices``."""
    pts = _points(items)
    g = cell.geometry
    hulls = []
    for j, rid in enumerate(cell.robot_ids):
        kj = pts[geo.in_reach(g, rid, pts)] if len(pts) else pts
        hulls.append(MultiPoint(np.vstack([kj, g.base_xy[j][None, :]])).convex_hull)
    return hulls


def standby_rho(cell: Cell, items: Iterable[Any], hulls: Sequence[Any] | None = None) -> dict[int, int | None]:
    """Smallest integer rho per robot id, or None if no rho in 0..floor(base distance) satisfies B7."""
    g = cell.geometry
    hulls = list(hulls) if hulls is not None else arm_hulls(cell, items)
    buf = float32_buffer_mm(g)
    out: dict[int, int | None] = {}
    for i, rid in enumerate(cell.robot_ids):
        rel = g.base_xy[i] - cell.origin_xy
        d = float(np.hypot(rel[0], rel[1]))
        if d <= 0.0:
            raise ValueError(f"robot {rid}: base at the origin has no direction")
        u = rel / d
        need = [float(g.arm_radius_mm[i] + g.arm_radius_mm[j] + g.arm_clearance_mm + buf)
                for j in range(cell.n_robots)]
        found: int | None = None
        for rho in range(int(math.floor(d)) + 1):
            seg = LineString([tuple(g.base_xy[i]), tuple(cell.origin_xy + rho * u)])
            if all(seg.distance(hulls[j]) >= need[j] for j in range(cell.n_robots) if j != i):
                found = rho
                break
        out[rid] = found
    return out


def standby_positions(cell: Cell, items: Iterable[Any]) -> dict[int, tuple[float, float]]:
    """B7: XY of the standby TCP per robot id; the base position if no rho qualifies."""
    g = cell.geometry
    rhos = standby_rho(cell, items)
    out: dict[int, tuple[float, float]] = {}
    for i, rid in enumerate(cell.robot_ids):
        rho = rhos[rid]
        if rho is None:
            out[rid] = (float(g.base_xy[i][0]), float(g.base_xy[i][1]))
        else:
            rel = g.base_xy[i] - cell.origin_xy
            u = rel / float(np.hypot(rel[0], rel[1]))
            p = cell.origin_xy + rho * u
            out[rid] = (float(p[0]), float(p[1]))
    return out


def park_candidates(cell: Cell, robot_id: int) -> list[tuple[float, float, float]]:
    """B9 (a): home + lambda (base - home) in XY, z = home z, in the order of ``PARK_LAMBDAS``."""
    i = cell.robot_ids.index(robot_id)
    hx, hy, hz = (float(c) for c in cell.home_xyz[i])
    bx, by = float(cell.base_xy[i][0]), float(cell.base_xy[i][1])
    return [(hx + lam * (bx - hx), hy + lam * (by - hy), hz) for lam in PARK_LAMBDAS]
