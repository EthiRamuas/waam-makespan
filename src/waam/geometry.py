"""XY geometry: reach, Base-TCP capsule distance, workspace (Validator formulas).

Units: mm, s, float64. Z is unused except in ``dist3``. Robot ids are 1..3,
array index is ``id - 1``.

Shape contract (all point arguments): ``(2,)`` or ``(N,2)``. Anything else --
notably xyz ``(3,)`` / ``(N,3)`` -- raises ``ValueError``; slice ``[..., :2]``
at the call site. Arguments are broadcast against each other ((1,2) or (2,)
against (N,2)); mismatched batch lengths raise. The result is a scalar only if
*every* point argument was ``(2,)``, otherwise an ``(N,)`` array (``N`` may be
0, which gives an empty array).

Source of the formulas (read-only reference): WAAM_Validator
``collision/geometry2d.py``, ``trajectory/reach.py``, ``trajectory/validator.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, NamedTuple

import numpy as np

# Interval sampling spacing (policy knob, not correctness): the interval bound
# below is conservative for ANY spacing; a smaller spacing only tightens it.
INTERVAL_MAX_STEP_MM = 2.5


@dataclass(frozen=True, slots=True)
class CellGeometry:
    base_xy: np.ndarray  # (3, 2)
    reach_mm: np.ndarray  # (3,)
    tcp_radius_mm: np.ndarray  # (3,)
    arm_radius_mm: np.ndarray  # (3,)
    arm_clearance_mm: float
    touching_is_collision: bool
    check_arm_envelope: bool
    check_tcp_radius: bool
    eps_mm: float
    ws_center_xy: np.ndarray  # (2,)
    ws_radius_mm: float
    bead_width_mm: float

    @classmethod
    def from_config(cls, cfg: Any) -> CellGeometry:
        """Build from a ``waam_validator`` Config (duck-typed: only attributes are read)."""
        robots = sorted(cfg.robots, key=lambda r: r.id)
        return cls(
            base_xy=np.array([r.base_xyz_mm[:2] for r in robots], dtype=np.float64),
            reach_mm=np.array([r.xy_reach_radius_mm for r in robots], dtype=np.float64),
            tcp_radius_mm=np.array([r.tcp_radius_mm for r in robots], dtype=np.float64),
            arm_radius_mm=np.array([r.arm_envelope_radius_mm for r in robots], dtype=np.float64),
            arm_clearance_mm=float(cfg.collision.arm_clearance_mm),
            touching_is_collision=bool(cfg.collision.touching_is_collision),
            check_arm_envelope=bool(cfg.collision.check_arm_envelope),
            check_tcp_radius=bool(cfg.collision.check_tcp_radius),
            eps_mm=float(cfg.collision.geometry_epsilon_mm),
            ws_center_xy=np.asarray(cfg.workspace.center_xy_mm, dtype=np.float64),
            ws_radius_mm=float(cfg.workspace.radius_mm),
            bead_width_mm=float(cfg.process.bead_width_mm),
        )


# ---------------------------------------------------------------- shape handling


def _xy(a: Any) -> np.ndarray:
    arr = np.asarray(a, dtype=np.float64)
    if arr.ndim not in (1, 2) or arr.shape[-1] != 2:
        raise ValueError(f"expected XY points of shape (2,) or (N,2), got {arr.shape}")
    return arr


def _prep(*points: Any) -> tuple[list[np.ndarray], bool]:
    """Validate, broadcast to a common (N,2), and report if all inputs were single points."""
    arrs = [_xy(p) for p in points]
    single = all(a.ndim == 1 for a in arrs)
    return list(np.broadcast_arrays(*[a.reshape(-1, 2) for a in arrs])), single


def _out(arr: np.ndarray, single: bool) -> Any:
    return arr[0] if single else arr


# ---------------------------------------------------------------- reach


def _xy_dist(g: CellGeometry, robot_id: int, xy: Any) -> tuple[np.ndarray, bool]:
    (p,), single = _prep(xy)
    return np.hypot(*(p - g.base_xy[robot_id - 1]).T), single


def reach_margin(g: CellGeometry, robot_id: int, xy: Any) -> Any:
    """``R - dist`` (positive = inside reach)."""
    d, single = _xy_dist(g, robot_id, xy)
    return _out(g.reach_mm[robot_id - 1] - d, single)


def in_reach(g: CellGeometry, robot_id: int, xy: Any) -> Any:
    """Validator rule: violation iff ``dist > R + eps``."""
    d, single = _xy_dist(g, robot_id, xy)
    return _out(d <= g.reach_mm[robot_id - 1] + g.eps_mm, single)


def reachable_mask(g: CellGeometry, xy: Any) -> np.ndarray:
    """Which robots reach each point: ``(3,)`` for one point, ``(N,3)`` for a batch."""
    (p,), single = _prep(xy)
    mask = np.stack([in_reach(g, rid, p) for rid in (1, 2, 3)], axis=1)
    return mask[0] if single else mask


# ---------------------------------------------------------------- collision


def _project(points: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    d = ends - starts
    den = np.einsum("ij,ij->i", d, d)
    num = np.einsum("ij,ij->i", points - starts, d)
    t = np.divide(num, den, out=np.zeros_like(num), where=den > 0.0)
    return starts + np.clip(t, 0.0, 1.0)[:, None] * d


def _cross(l: np.ndarray, r: np.ndarray) -> np.ndarray:
    return l[:, 0] * r[:, 1] - l[:, 1] * r[:, 0]


def _seg_seg(A0: np.ndarray, A1: np.ndarray, B0: np.ndarray, B1: np.ndarray) -> np.ndarray:
    """Core of ``seg_seg_dist`` on already-broadcast (N,2) arrays."""
    n = len(A0)
    ca = np.stack((A0, A1, _project(B0, A0, A1), _project(B1, A0, A1)), axis=1)
    cb = np.stack((_project(A0, B0, B1), _project(A1, B0, B1), B0, B1), axis=1)
    dist = np.sqrt(np.min(np.sum((ca - cb) ** 2, axis=2), axis=1)) if n else np.empty(0)

    da, db, off = A1 - A0, B1 - B0, B0 - A0
    den = _cross(da, db)
    tol = (
        np.finfo(np.float64).eps
        * np.maximum(np.linalg.norm(da, axis=1) * np.linalg.norm(db, axis=1), 1.0)
        * 16.0
    )
    ok = np.abs(den) > tol
    ta = np.divide(_cross(off, db), den, out=np.zeros(n), where=ok)
    tb = np.divide(_cross(off, da), den, out=np.zeros(n), where=ok)
    cross = ok & (ta >= 0) & (ta <= 1) & (tb >= 0) & (tb <= 1)
    return np.where(cross, 0.0, dist)


def seg_seg_dist(a0: Any, a1: Any, b0: Any, b1: Any) -> Any:
    """Shortest distance between 2D segments a0-a1 and b0-b1 (0 if they cross).

    Same candidate scheme as the Validator: four endpoint-to-segment
    projections, plus an exact zero when the segments properly intersect.
    Degenerate (zero-length) segments are handled by the projection step.
    """
    (A0, A1, B0, B1), single = _prep(a0, a1, b0, b1)
    return _out(_seg_seg(A0, A1, B0, B1), single)


def _arm_required(g: CellGeometry, ra: int, rb: int) -> float:
    return float(g.arm_radius_mm[ra - 1] + g.arm_radius_mm[rb - 1] + g.arm_clearance_mm)


def _tcp_required(g: CellGeometry, ra: int, rb: int) -> float:
    return float(g.tcp_radius_mm[ra - 1] + g.tcp_radius_mm[rb - 1])


def _arm_margin_n(g: CellGeometry, ra: int, ta: np.ndarray, rb: int, tb: np.ndarray) -> np.ndarray:
    n = len(ta)
    ba = np.broadcast_to(g.base_xy[ra - 1], (n, 2))
    bb = np.broadcast_to(g.base_xy[rb - 1], (n, 2))
    return _seg_seg(ba, ta, bb, tb) - _arm_required(g, ra, rb)


def _tcp_margin_n(g: CellGeometry, ra: int, ta: np.ndarray, rb: int, tb: np.ndarray) -> np.ndarray:
    return np.hypot(*(ta - tb).T) - _tcp_required(g, ra, rb)


def _arm_hit(g: CellGeometry, margin: np.ndarray) -> np.ndarray:
    return margin <= g.eps_mm if g.touching_is_collision else margin < -g.eps_mm


def _tcp_hit(g: CellGeometry, margin: np.ndarray) -> np.ndarray:
    # Validator: d <= r_a + r_b (touching) or d < r_a + r_b. No epsilon.
    return margin <= 0.0 if g.touching_is_collision else margin < 0.0


def arm_margin(g: CellGeometry, ra: int, tcp_a: Any, rb: int, tcp_b: Any) -> Any:
    """Capsule centerline distance minus ``r_a + r_b + clearance``."""
    (ta, tb), single = _prep(tcp_a, tcp_b)
    return _out(_arm_margin_n(g, ra, ta, rb, tb), single)


def arm_collides(g: CellGeometry, ra: int, tcp_a: Any, rb: int, tcp_b: Any) -> Any:
    """Validator rule: ``margin <= eps`` if touching counts, else ``margin < -eps``."""
    (ta, tb), single = _prep(tcp_a, tcp_b)
    return _out(_arm_hit(g, _arm_margin_n(g, ra, ta, rb, tb)), single)


def tcp_collides(g: CellGeometry, ra: int, tcp_a: Any, rb: int, tcp_b: Any) -> Any:
    """TCP circles: ``d <= r_a + r_b`` (touching) or ``<``. No epsilon (as in Validator)."""
    (ta, tb), single = _prep(tcp_a, tcp_b)
    return _out(_tcp_hit(g, _tcp_margin_n(g, ra, ta, rb, tb)), single)


def pair_collides(g: CellGeometry, ra: int, tcp_a: Any, rb: int, tcp_b: Any) -> Any:
    """Arm OR TCP collision, honoring the config's check flags."""
    (ta, tb), single = _prep(tcp_a, tcp_b)
    hit = np.zeros(len(ta), dtype=bool)
    if g.check_arm_envelope:
        hit |= _arm_hit(g, _arm_margin_n(g, ra, ta, rb, tb))
    if g.check_tcp_radius:
        hit |= _tcp_hit(g, _tcp_margin_n(g, ra, ta, rb, tb))
    return _out(hit, single)


class IntervalResult(NamedTuple):
    """Conservative lower bounds over a whole interval (continuous time).

    ``arm_margin`` / ``tcp_margin`` are lower bounds of the true minimum over
    the interval; ``t`` is the time of the worst *sample* (diagnostic only).
    ``collides`` is True if the bounds could be in collision under the
    Validator's rules and the config's check flags, i.e. it never reports
    safe for an interval that actually collides (it may report a collision
    for a near miss within ~``max_step_mm``).
    """

    collides: bool
    arm_margin: float
    tcp_margin: float
    t: float


def min_arm_margin_over_interval(
    g: CellGeometry,
    ra: int,
    p0a: Any,
    p1a: Any,
    rb: int,
    p0b: Any,
    p1b: Any,
    t0: float,
    t1: float,
    *,
    max_step_mm: float = INTERVAL_MAX_STEP_MM,
) -> IntervalResult:
    """Collision bound for both TCPs moving linearly p0 -> p1 over [t0, t1].

    Both the Base-TCP segment distance and the TCP-TCP distance are 1-Lipschitz
    in each TCP position (a point on the Base-TCP segment moves at most as far
    as the TCP). Sampling at ``n+1`` equally spaced parameters, any instant is
    within half a spacing of a sample, so::

        true_min >= min_over_samples - (La + Lb) / (2 n)

    where ``La``, ``Lb`` are the XY path lengths. This holds for any ``n``, so
    the result does not depend on how the Validator samples. Time does not
    enter the bound (positions are linear in time); ``n`` depends on distance
    only, so stationary intervals cost one sample.
    """
    for p in (p0a, p1a, p0b, p1b):
        if np.shape(p) != (2,):
            raise ValueError(f"interval endpoints must have shape (2,), got {np.shape(p)}")
    if t1 < t0:
        raise ValueError(f"t1 ({t1}) must be >= t0 ({t0})")
    p0a, p1a, p0b, p1b = (np.asarray(x, dtype=np.float64) for x in (p0a, p1a, p0b, p1b))
    la = float(np.linalg.norm(p1a - p0a))
    lb = float(np.linalg.norm(p1b - p0b))
    n = max(1, math.ceil(max(la, lb) / max_step_mm))
    u = np.linspace(0.0, 1.0, n + 1)[:, None]
    ta = p0a + u * (p1a - p0a)
    tb = p0b + u * (p1b - p0b)
    slack = (la + lb) / (2.0 * n)
    arm = _arm_margin_n(g, ra, ta, rb, tb)
    tcp = _tcp_margin_n(g, ra, ta, rb, tb)
    arm_lb = float(arm.min()) - slack
    tcp_lb = float(tcp.min()) - slack
    hit = (g.check_arm_envelope and bool(_arm_hit(g, np.array(arm_lb)))) or (
        g.check_tcp_radius and bool(_tcp_hit(g, np.array(tcp_lb)))
    )
    worst = int(np.argmin(arm)) if g.check_arm_envelope or not g.check_tcp_radius else int(np.argmin(tcp))
    return IntervalResult(bool(hit), arm_lb, tcp_lb, float(t0 + (t1 - t0) * u[worst, 0]))


# Upper bound on samples materialised at once by the batch interval functions.
_CHUNK_SAMPLES = 1 << 19


def _interval_arrays(*pts: Any) -> list[np.ndarray]:
    arrs, _ = _prep(*pts)
    return arrs


def interval_margins_batch(
    g: CellGeometry,
    ra: int,
    p0a: Any,
    p1a: Any,
    rb: int,
    p0b: Any,
    p1b: Any,
    *,
    max_step_mm: float = INTERVAL_MAX_STEP_MM,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised ``min_arm_margin_over_interval`` bounds for K intervals.

    Endpoints are ``(2,)`` or ``(K,2)`` and broadcast against each other. Returns
    ``(arm_lb, tcp_lb)``, both ``(K,)``: lower bounds of the continuous minimum
    margins, identical in construction to the scalar function (same ``n`` per
    interval, same ``(La+Lb)/(2n)`` slack).
    """
    P0a, P1a, P0b, P1b = _interval_arrays(p0a, p1a, p0b, p1b)
    K = len(P0a)
    arm_lb = np.empty(K)
    tcp_lb = np.empty(K)
    if K == 0:
        return arm_lb, tcp_lb
    la = np.hypot(*(P1a - P0a).T)
    lb = np.hypot(*(P1b - P0b).T)
    n = np.maximum(1, np.ceil(np.maximum(la, lb) / max_step_mm)).astype(np.int64)
    cnt = n + 1
    cum = np.cumsum(cnt)
    start = 0
    while start < K:
        before = cum[start - 1] if start else 0
        end = max(int(np.searchsorted(cum, before + _CHUNK_SAMPLES, side="right")), start + 1)
        end = min(end, K)
        c = cnt[start:end]
        local = np.cumsum(c) - c
        idx = np.repeat(np.arange(start, end), c)
        k = np.arange(int(c.sum())) - np.repeat(local, c)
        u = (k / n[idx])[:, None]
        ta = P0a[idx] + u * (P1a[idx] - P0a[idx])
        tb = P0b[idx] + u * (P1b[idx] - P0b[idx])
        slack = (la[start:end] + lb[start:end]) / (2.0 * n[start:end])
        arm_lb[start:end] = np.minimum.reduceat(_arm_margin_n(g, ra, ta, rb, tb), local) - slack
        tcp_lb[start:end] = np.minimum.reduceat(_tcp_margin_n(g, ra, ta, rb, tb), local) - slack
        start = end
    return arm_lb, tcp_lb


def _hull_aabb(base: np.ndarray, p0: np.ndarray, p1: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return np.minimum(np.minimum(base, p0), p1), np.maximum(np.maximum(base, p0), p1)


def interval_aabb_gap(
    g: CellGeometry, ra: int, p0a: Any, p1a: Any, rb: int, p0b: Any, p1b: Any
) -> np.ndarray:
    """Euclidean gap between the AABBs of ``hull{base, p0, p1}`` of both robots, ``(K,)``.

    For a TCP moving linearly p0 -> p1, the Base-TCP segment and the TCP itself both stay in
    the hull of {base, p0, p1}, so the gap is a lower bound on the centerline distance AND on
    the TCP-TCP distance over the whole interval (0 if the boxes overlap).
    """
    P0a, P1a, P0b, P1b = _interval_arrays(p0a, p1a, p0b, p1b)
    lo_a, hi_a = _hull_aabb(g.base_xy[ra - 1], P0a, P1a)
    lo_b, hi_b = _hull_aabb(g.base_xy[rb - 1], P0b, P1b)
    d = np.maximum(0.0, np.maximum(lo_b - hi_a, lo_a - hi_b))
    return np.hypot(d[:, 0], d[:, 1])


def interval_clear_mask(
    g: CellGeometry,
    ra: int,
    p0a: Any,
    p1a: Any,
    rb: int,
    p0b: Any,
    p1b: Any,
    *,
    buffer_mm: float = 0.0,
) -> np.ndarray:
    """``(K,)`` bool: AABB gap proves the interval is clear (no sampling needed).

    Uses the same hit rules as the exact check, applied to the gap bound minus ``buffer_mm``.
    A True entry is sound; False only means "not proven by the boxes".
    """
    gap = interval_aabb_gap(g, ra, p0a, p1a, rb, p0b, p1b)
    clear = np.ones(len(gap), dtype=bool)
    if g.check_arm_envelope:
        clear &= ~_arm_hit(g, gap - _arm_required(g, ra, rb) - buffer_mm)
    if g.check_tcp_radius:
        clear &= ~_tcp_hit(g, gap - _tcp_required(g, ra, rb) - buffer_mm)
    return clear


def intervals_collide(
    g: CellGeometry,
    ra: int,
    p0a: Any,
    p1a: Any,
    rb: int,
    p0b: Any,
    p1b: Any,
    *,
    buffer_mm: float = 0.0,
    max_step_mm: float = INTERVAL_MAX_STEP_MM,
    prefilter: bool = True,
) -> np.ndarray:
    """``(K,)`` bool: interval may collide (conservative), Validator rules on the bounds.

    ``buffer_mm`` is subtracted from the margin lower bounds before applying the
    Validator's hit rules (use it for float32 rounding slack). With ``prefilter`` the AABB
    gap clears far-apart intervals first; only the rest are sampled. Always returns an array
    (``K`` = 1 for single-interval input).
    """
    P0a, P1a, P0b, P1b = _interval_arrays(p0a, p1a, p0b, p1b)
    K = len(P0a)
    hit = np.zeros(K, dtype=bool)
    todo = (
        ~interval_clear_mask(g, ra, P0a, P1a, rb, P0b, P1b, buffer_mm=buffer_mm)
        if prefilter
        else np.ones(K, dtype=bool)
    )
    sel = np.flatnonzero(todo)
    if sel.size:
        arm, tcp = interval_margins_batch(
            g, ra, P0a[sel], P1a[sel], rb, P0b[sel], P1b[sel], max_step_mm=max_step_mm
        )
        h = np.zeros(sel.size, dtype=bool)
        if g.check_arm_envelope:
            h |= _arm_hit(g, arm - buffer_mm)
        if g.check_tcp_radius:
            h |= _tcp_hit(g, tcp - buffer_mm)
        hit[sel] = h
    return hit


# ---------------------------------------------------------------- workspace


def deposition_in_workspace(g: CellGeometry, p0_xy: Any, p1_xy: Any) -> Any:
    """D segment rule: ``max(r0, r1) + bead/2 <= R_ws + eps`` (T/W are exempt)."""
    (p0, p1), single = _prep(p0_xy, p1_xy)
    r = np.maximum(np.hypot(*(p0 - g.ws_center_xy).T), np.hypot(*(p1 - g.ws_center_xy).T))
    return _out(r + g.bead_width_mm / 2.0 <= g.ws_radius_mm + g.eps_mm, single)


# ---------------------------------------------------------------- helpers


def dist3(p0_xyz: Any, p1_xyz: Any) -> float:
    """3D Euclidean distance (speed checks use 3D distance / time)."""
    return float(np.linalg.norm(np.asarray(p1_xyz, float) - np.asarray(p0_xyz, float)))
