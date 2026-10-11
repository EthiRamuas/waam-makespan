"""Sectors by base direction (docs/specs/baseline.md B16, C-43). Pure functions.

The origin is the workspace centre. A robot's sector is bounded by the bisectors between its
base direction and the angularly adjacent base directions (the public config gives 120 deg
sectors as a special case; nothing here assumes a number of robots or an angle). ``delta`` rotates
all boundaries by the same angle. A point belongs to the half-open sector [lo, hi).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .strategy import Cell

TWO_PI = 2.0 * math.pi


@dataclass(frozen=True, slots=True)
class SectorSpec:
    robot_ids: tuple[int, ...]  # config order; label i <-> robot_ids[i]
    origin_xy: np.ndarray  # (2,)
    order: np.ndarray  # (n,) config indices sorted by base angle
    base_angle: np.ndarray  # (n,) atan2 of (base - origin), config order
    beta: np.ndarray  # (n,) boundary after the k-th robot in ``order`` (before rotation by delta)
    half_lo: np.ndarray  # (n,) half gap to the previous neighbour, config order [rad]
    half_hi: np.ndarray  # (n,) half gap to the next neighbour, config order [rad]
    delta: float  # rotation of every boundary [rad]

    @property
    def n(self) -> int:
        return len(self.robot_ids)

    def boundary_angles(self) -> np.ndarray:
        """Boundary ray angles (rotated by delta); empty for one robot."""
        return self.beta + self.delta if self.n > 1 else np.empty(0)


def sector_bounds(cell: Cell, delta_rad: float = 0.0) -> SectorSpec:
    n = cell.n_robots
    rel = cell.base_xy - cell.origin_xy
    if np.any(np.hypot(rel[:, 0], rel[:, 1]) <= 0.0):
        raise ValueError("a base at the origin has no direction")
    th = np.arctan2(rel[:, 1], rel[:, 0])
    order = np.argsort(th, kind="stable")
    ths = th[order]
    gaps = np.diff(np.concatenate([ths, [ths[0] + TWO_PI]]))  # gap after the k-th sorted robot
    beta = ths + gaps / 2.0
    half_hi = np.empty(n)
    half_lo = np.empty(n)
    for k in range(n):
        half_hi[order[k]] = gaps[k] / 2.0
        half_lo[order[k]] = gaps[k - 1] / 2.0
    return SectorSpec(cell.robot_ids, cell.origin_xy.copy(), order, th, beta, half_lo, half_hi,
                      float(delta_rad))


def owner_index(spec: SectorSpec, xy: np.ndarray) -> np.ndarray:
    """Config index of the robot whose sector holds each point of ``xy`` (N,2)."""
    xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    if spec.n == 1:
        return np.zeros(len(xy), dtype=int)
    ang = np.arctan2(xy[:, 1] - spec.origin_xy[1], xy[:, 0] - spec.origin_xy[0]) - spec.delta
    b0 = spec.beta[0]
    c = np.mod(spec.beta - b0, TWO_PI)  # increasing, c[0] == 0
    u = np.mod(ang - b0, TWO_PI)
    idx = np.searchsorted(c, u, side="right") - 1
    return spec.order[(idx + 1) % spec.n]


def owner_robot(spec: SectorSpec, xy: np.ndarray) -> np.ndarray:
    """Robot id owning each point."""
    ids = np.asarray(spec.robot_ids)
    return ids[owner_index(spec, xy)]


def phi_max(cell: Cell, r_max_mm: float) -> np.ndarray:
    """C-43: largest angle off the base direction at which every point of radius <= r_max
    (about the origin) is still within reach: acos((d^2 + r^2 - R^2) / (2 d r)).

    pi if every direction is reachable, 0 if even the base direction is not.
    """
    d = np.hypot(*(cell.base_xy - cell.origin_xy).T)
    R = cell.geometry.reach_mm
    out = np.empty(cell.n_robots)
    for i in range(cell.n_robots):
        if r_max_mm <= 0.0:
            out[i] = math.pi if d[i] <= R[i] else 0.0
            continue
        c = (d[i] ** 2 + r_max_mm**2 - R[i] ** 2) / (2.0 * d[i] * r_max_mm)
        out[i] = math.pi if c <= -1.0 else (0.0 if c > 1.0 else math.acos(c))
    return out


def delta_max(cell: Cell, spec: SectorSpec, r_max_mm: float) -> float:
    """C-43: min over robots of (phi_max - sector half width), using the larger side."""
    phi = phi_max(cell, r_max_mm)
    return float(min(min(phi[i] - spec.half_hi[i], phi[i] - spec.half_lo[i])
                     for i in range(spec.n)))


def sector_arc(spec: SectorSpec, index: int) -> tuple[float, float]:
    """(lo, hi) of robot ``index``'s sector, boundaries rotated by delta; the sector is [lo, hi) going
    counter-clockwise from lo (width = (hi - lo) mod 2 pi). Needs n > 1."""
    k = int(np.flatnonzero(spec.order == index)[0])
    return float(spec.beta[k - 1] + spec.delta), float(spec.beta[k] + spec.delta)


def angular_distance_to_sector(spec: SectorSpec, index: int, angle_rad: float) -> float:
    """Circular distance from ``angle_rad`` to robot ``index``'s sector: 0 inside [lo, hi)."""
    if spec.n == 1:
        return 0.0
    lo, hi = sector_arc(spec, index)
    width = (hi - lo) % TWO_PI
    rel = (angle_rad - lo) % TWO_PI
    if rel < width:
        return 0.0
    return float(min(rel - width, TWO_PI - rel))
