"""prevalidate: millisecond-scale pre-check that stands in for the Validator in search loops.

What it decides (everything the Validator decides except the shape metrics):
  reach, D-segment rules (workspace, length, Z/layer), W position, speeds, collisions
  (arm capsule + TCP circle) and the CSV-level contract (first time 0,
  mode durations sum to completion; the terminal W row belongs to the writer).

Soundness contract: if prevalidate says OK, the Validator must not FAIL for any of the
above. It may reject more (conservative). Shape metrics are NOT covered: toolpath
guarantees them and the Validator confirms submission candidates.

float32 policy (decision "C", hybrid):
  * Waypoints are quantized exactly like the Validator's loader (``float32``), so reach,
    workspace, speed and W-position checks see the same numbers: no buffer needed.
  * Collision samples inside an interval are rounded to float32 by the Validator at
    times we cannot know, so collision bounds subtract ``buffer_mm``:
    ``beta = max(2 * sqrt(2) / 2 * spacing_f32(Rmax), min_buffer_mm)``.
  * Continuous-time collision bounds come from ``geometry`` (Lipschitz), never from
    sampling density.

Timelines: one ``Timeline`` per robot (struct of arrays, amortised O(1) append, O(1)
rollback). ``try_append`` checks the new segment against the other robots' *committed*
spans only: a robot that is still being scheduled is not assumed to stand still. When a
robot's schedule is complete, ``close_timeline`` declares that it holds its last position
for good (the Validator does the same until the makespan) and checks that hold against what
the others have committed; later appends by the others are checked against the hold.
Every overlapping pair is thereby checked once, when the later of the two is committed.
``check_all`` applies the Validator's semantics to the final timelines: everyone holds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Any, NamedTuple

import numpy as np

from . import geometry as geo
from .segment import Mode, Segment

DEFAULT_MIN_BUFFER_MM = 1e-3

_MODE_T, _MODE_D, _MODE_W = 0, 1, 2
_MODE_CODE = {Mode.T: _MODE_T, Mode.D: _MODE_D, Mode.W: _MODE_W}


class Code(IntEnum):
    """Reason codes. Names equal the Validator's issue / error / collision-type codes."""

    OK = 0
    # --- Validator trajectory/validator.py issues and errors ---------------------------
    ROBOT_XY_REACH_VIOLATION = 1
    DEPOSITION_OUTSIDE_WORKSPACE = 2
    DEPOSITION_ZERO_LENGTH = 3
    DEPOSITION_VERTICAL_MOVE = 4
    DEPOSITION_BELOW_BUILD_PLANE = 5
    DEPOSITION_LAYER_MISMATCH = 6
    WAIT_POSITION_CHANGED = 7
    DEPOSITION_SPEED_VIOLATION = 8
    TRAVEL_SPEED_VIOLATION = 9
    STATIONARY_TRAVEL_WARNING = 10  # warning only
    # --- Validator collision types (collision/simulator.py) ----------------------------
    ARM_ENVELOPE = 20
    TCP_RADIUS = 21
    # --- Validator loader / schedule contract ------------------------------------------
    FIRST_TIME_NOT_ZERO = 30
    FINAL_MODE_NOT_W = 31  # about the CSV terminal row: checked by the writer, not here
    MISSING_ROBOT = 32
    NONFINITE_VALUE = 33
    MODE_TIME_SUM_MISMATCH = 34  # the Validator's ArithmeticError
    # --- ours (no Validator counterpart: the CSV cannot express these) -----------------
    CHAIN_TIME_MISMATCH = 100
    CHAIN_POSITION_JUMP = 101
    TIMELINE_CLOSED = 102


class Verdict(NamedTuple):
    ok: bool
    code: Code
    t: float = math.nan  # time of the first violation (diagnostic)
    robot: int = 0
    other: int = 0  # second robot for collisions


OK = Verdict(True, Code.OK)


class Report(NamedTuple):
    ok: bool
    violations: list[Verdict]
    warnings: list[Verdict]

    @property
    def verdict(self) -> Verdict:
        return self.violations[0] if self.violations else OK


# ------------------------------------------------------------------------- rules


def float32_buffer_mm(g: geo.CellGeometry, min_buffer_mm: float = DEFAULT_MIN_BUFFER_MM) -> float:
    """Collision buffer: ``max(computed float32 rounding bound, min_buffer_mm)``.

    A sample coordinate of magnitude <= Rmax is rounded by at most half a float32 spacing
    per axis, so a sampled TCP moves by at most ``sqrt(2)/2 * spacing`` and the margin of a
    pair by at most twice that. Rmax is bounded by the largest |base coordinate| + reach.
    """
    rmax = float(np.max(np.abs(g.base_xy).max(axis=1) + g.reach_mm))
    spacing = float(np.spacing(np.float32(rmax)))
    return max(2.0 * math.sqrt(2.0) / 2.0 * spacing, float(min_buffer_mm))


@dataclass(frozen=True, slots=True)
class PrevalidateRules:
    geom: geo.CellGeometry
    deposition_speed_mm_s: float
    travel_speed_mm_s: float
    speed_relative_tolerance: float
    fail_on_speed_violation: bool
    layer_height_mm: float
    build_plane_z_mm: float
    tcp_z_center: bool
    layer_z_tolerance_mm: float
    wait_position_tolerance_mm: float
    buffer_mm: float
    max_step_mm: float
    geom_arm_only: geo.CellGeometry
    geom_tcp_only: geo.CellGeometry

    @classmethod
    def from_config(
        cls,
        cfg: Any,
        *,
        min_buffer_mm: float = DEFAULT_MIN_BUFFER_MM,
        max_step_mm: float = geo.INTERVAL_MAX_STEP_MM,
    ) -> PrevalidateRules:
        g = geo.CellGeometry.from_config(cfg)
        p, v = cfg.process, cfg.validation
        return cls(
            geom=g,
            deposition_speed_mm_s=float(p.deposition_speed_mm_s),
            travel_speed_mm_s=float(p.travel_speed_mm_s),
            speed_relative_tolerance=float(v.speed_relative_tolerance),
            fail_on_speed_violation=bool(v.fail_on_speed_violation),
            layer_height_mm=float(p.layer_height_mm),
            build_plane_z_mm=float(p.build_plane_z_mm),
            tcp_z_center=(p.tcp_z_reference == "center"),
            layer_z_tolerance_mm=float(v.layer_z_tolerance_mm),
            wait_position_tolerance_mm=float(v.wait_position_tolerance_mm),
            buffer_mm=float32_buffer_mm(g, min_buffer_mm),
            max_step_mm=float(max_step_mm),
            geom_arm_only=replace(g, check_tcp_radius=False),
            geom_tcp_only=replace(g, check_arm_envelope=False),
        )


def quantize_f32(xyz: Any) -> np.ndarray:
    """Coordinates exactly as the Validator's loader sees them (float32, back to float64)."""
    with np.errstate(over="ignore"):
        return np.asarray(xyz, dtype=np.float64).astype(np.float32).astype(np.float64)


# ------------------------------------------------------------------------- timeline


class Timeline:
    """One robot's committed schedule: breakpoints ``t`` (n+1), quantized ``xyz`` (n+1,3)."""

    __slots__ = ("robot_id", "_t", "_xyz", "_mode", "_n", "closed")

    def __init__(self, robot_id: int, capacity: int = 64) -> None:
        self.robot_id = robot_id
        self._t = np.empty(capacity + 1)
        self._xyz = np.empty((capacity + 1, 3))
        self._mode = np.empty(capacity, dtype=np.uint8)
        self._n = 0
        self.closed = False  # True: complete, holds its last position forever

    @property
    def n_segments(self) -> int:
        return self._n

    @property
    def t(self) -> np.ndarray:
        return self._t[: self._n + 1] if self._n else self._t[:0]

    @property
    def xyz(self) -> np.ndarray:
        return self._xyz[: self._n + 1] if self._n else self._xyz[:0]

    @property
    def mode(self) -> np.ndarray:
        return self._mode[: self._n]

    @property
    def end_time(self) -> float:
        return float(self._t[self._n]) if self._n else 0.0

    def chain_code(self, t0: float, p0q: np.ndarray) -> Code:
        if t0 != self.end_time:
            return Code.CHAIN_TIME_MISMATCH
        if self._n and not np.array_equal(p0q, self._xyz[self._n]):
            return Code.CHAIN_POSITION_JUMP
        return Code.OK

    def push(self, t0: float, t1: float, p0q: np.ndarray, p1q: np.ndarray, mode: int) -> None:
        if self.closed:
            raise ValueError(f"robot {self.robot_id}: timeline is closed")
        code = self.chain_code(t0, p0q)
        if code != Code.OK:
            raise ValueError(f"robot {self.robot_id}: {code.name} at t={t0}")
        if self._n + 1 >= len(self._mode):
            cap = max(2 * len(self._mode), 8)
            self._t = np.resize(self._t, cap + 1)
            self._xyz = np.resize(self._xyz, (cap + 1, 3))
            self._mode = np.resize(self._mode, cap)
        if self._n == 0:
            self._t[0] = t0
            self._xyz[0] = p0q
        self._t[self._n + 1] = t1
        self._xyz[self._n + 1] = p1q
        self._mode[self._n] = mode
        self._n += 1

    def append(self, seg: Segment) -> None:
        """Commit a segment WITHOUT checking it (use ``try_append`` in a search)."""
        self.push(seg.start_time_s, seg.end_time_s, quantize_f32(seg.start_xyz_mm),
                  quantize_f32(seg.end_xyz_mm), _MODE_CODE[seg.mode])

    def pop_last(self) -> None:
        if self._n == 0:
            raise IndexError("timeline is empty")
        self._n -= 1

    @classmethod
    def from_segments(cls, robot_id: int, segments: list[Segment]) -> Timeline:
        tl = cls(robot_id, max(len(segments), 8))
        for seg in segments:
            tl.append(seg)
        return tl

    def position_at(self, t: float) -> np.ndarray:
        """Quantized XYZ at time ``t`` (holds the last position after the last time)."""
        return np.array([np.interp(t, self.t, self.xyz[:, i]) for i in range(3)])


def new_timelines() -> tuple[Timeline, Timeline, Timeline]:
    return (Timeline(1), Timeline(2), Timeline(3))


# ------------------------------------------------------------------------- local rules


def _local(
    rules: PrevalidateRules,
    rid: int,
    t0: np.ndarray,
    t1: np.ndarray,
    P0: np.ndarray,
    P1: np.ndarray,
    modes: np.ndarray,
) -> tuple[list[tuple[Code, np.ndarray]], list[tuple[Code, np.ndarray]]]:
    """Per-rule (code, per-segment mask) lists for violations and warnings (validator.py)."""
    r, g = rules, rules.geom
    d = P1 - P0
    length = np.linalg.norm(d, axis=1)
    xy_len = np.linalg.norm(d[:, :2], axis=1)
    speed = length / (t1 - t0)
    is_d, is_t, is_w = modes == _MODE_D, modes == _MODE_T, modes == _MODE_W

    reach_bad = ~(np.asarray(geo.in_reach(g, rid, P0[:, :2]))
                  & np.asarray(geo.in_reach(g, rid, P1[:, :2])))
    ws_bad = is_d & ~np.asarray(geo.deposition_in_workspace(g, P0[:, :2], P1[:, :2]))
    zero_len = is_d & (xy_len <= g.eps_mm)
    vertical = is_d & (np.abs(d[:, 2]) > r.layer_z_tolerance_mm)
    rep_z = (P0[:, 2] + P1[:, 2]) / 2.0
    below_plane = is_d & (rep_z < r.build_plane_z_mm - r.layer_z_tolerance_mm)
    if r.tcp_z_center:
        rounded = np.rint((rep_z - r.build_plane_z_mm - r.layer_height_mm / 2.0) / r.layer_height_mm)
        layer_below0 = rounded < 0.0
        expected_z = r.build_plane_z_mm + (rounded + 0.5) * r.layer_height_mm
    else:
        rounded = np.rint((rep_z - r.build_plane_z_mm) / r.layer_height_mm)
        layer_below0 = rounded < 1.0
        expected_z = r.build_plane_z_mm + rounded * r.layer_height_mm
    layer_bad = is_d & (layer_below0 | (np.abs(rep_z - expected_z) > r.layer_z_tolerance_mm))

    wait_moved = is_w & (length > r.wait_position_tolerance_mm)
    dep_speed_bad = is_d & (
        np.abs(speed - r.deposition_speed_mm_s) / r.deposition_speed_mm_s
        > r.speed_relative_tolerance
    )
    travel_bad = is_t & (speed > r.travel_speed_mm_s * (1.0 + r.speed_relative_tolerance))
    stationary_t = is_t & (length <= g.eps_mm)
    fail = r.fail_on_speed_violation

    # (code, mask) in priority order; a segment can carry several codes (the Validator
    # records each of them), callers needing a single verdict take the first.
    viol = [
        (Code.DEPOSITION_OUTSIDE_WORKSPACE, ws_bad),
        (Code.DEPOSITION_ZERO_LENGTH, zero_len),
        (Code.DEPOSITION_VERTICAL_MOVE, vertical),
        (Code.DEPOSITION_BELOW_BUILD_PLANE, below_plane),
        (Code.DEPOSITION_LAYER_MISMATCH, layer_bad),
        (Code.ROBOT_XY_REACH_VIOLATION, reach_bad),
        (Code.WAIT_POSITION_CHANGED, wait_moved),
        (Code.DEPOSITION_SPEED_VIOLATION, dep_speed_bad & fail),
        (Code.TRAVEL_SPEED_VIOLATION, travel_bad & fail),
    ]
    warn = [
        (Code.DEPOSITION_SPEED_VIOLATION, dep_speed_bad & (not fail)),
        (Code.TRAVEL_SPEED_VIOLATION, travel_bad & (not fail)),
        (Code.STATIONARY_TRAVEL_WARNING, stationary_t),
    ]
    return viol, warn


def _first_code(masks: list[tuple[Code, np.ndarray]], i: int = 0) -> Code:
    for code, mask in masks:
        if mask[i]:
            return code
    return Code.OK


def check_segment_local(rules: PrevalidateRules, seg: Segment) -> Verdict:
    """Per-robot rules for one segment (no other robots, no chain)."""
    p0, p1 = quantize_f32(seg.start_xyz_mm), quantize_f32(seg.end_xyz_mm)
    if not (np.isfinite(p0).all() and np.isfinite(p1).all()):
        return Verdict(False, Code.NONFINITE_VALUE, seg.start_time_s, seg.robot_id)
    viol, _ = _local(rules, seg.robot_id, np.array([seg.start_time_s]), np.array([seg.end_time_s]),
                     p0[None], p1[None], np.array([_MODE_CODE[seg.mode]]))
    code = _first_code(viol)
    return OK if code == Code.OK else Verdict(False, code, seg.start_time_s, seg.robot_id)


# ------------------------------------------------------------------------- collisions


def _positions(tl: Timeline, bps: np.ndarray) -> np.ndarray:
    return np.stack([np.interp(bps, tl.t, tl.xyz[:, 0]), np.interp(bps, tl.t, tl.xyz[:, 1])], axis=1)


def _collide_over(
    rules: PrevalidateRules, ra: int, bps: np.ndarray, A: np.ndarray, rb: int, B: np.ndarray
) -> Verdict:
    """Collision check over consecutive intervals bps[i]..bps[i+1] (A, B: (K+1, 2) positions)."""
    hit = geo.intervals_collide(rules.geom, ra, A[:-1], A[1:], rb, B[:-1], B[1:],
                                buffer_mm=rules.buffer_mm, max_step_mm=rules.max_step_mm)
    idx = np.flatnonzero(hit)
    if idx.size == 0:
        return OK
    i = int(idx[0])
    sub = (A[i : i + 1], A[i + 1 : i + 2], B[i : i + 1], B[i + 1 : i + 2])
    arm = bool(geo.intervals_collide(rules.geom_arm_only, ra, sub[0], sub[1], rb, sub[2], sub[3],
                                     buffer_mm=rules.buffer_mm, max_step_mm=rules.max_step_mm)[0])
    return Verdict(False, Code.ARM_ENVELOPE if arm else Code.TCP_RADIUS, float(bps[i]), ra, rb)


def _window_bps(times: list[np.ndarray], t_from: float, t_to: float) -> np.ndarray:
    hi = min(t_to, max(float(t[-1]) for t in times))
    if hi <= t_from:
        return np.array([t_from, t_from])
    inner = [t[(t > t_from) & (t < hi)] for t in times]
    return np.unique(np.concatenate([[t_from, hi], *inner]))


def _known_until(tl: Timeline, hold_open: bool) -> float:
    """Until when a timeline's position is known: forever if it holds, else its committed end."""
    return math.inf if (tl.closed or hold_open) else tl.end_time


def check_pair(rules: PrevalidateRules, tla: Timeline, tlb: Timeline,
               t_from: float = 0.0, t_to: float = math.inf, *, hold_open: bool = False) -> Verdict:
    """Collision check of two timelines over ``[t_from, t_to]``.

    An open timeline is only known over its committed span; a closed one (or any, with
    ``hold_open``) holds its last position afterwards.
    """
    if tla.n_segments == 0 or tlb.n_segments == 0:
        return OK
    t_to = min(t_to, _known_until(tla, hold_open), _known_until(tlb, hold_open))
    if t_to < t_from:
        return OK
    bps = _window_bps([tla.t, tlb.t], t_from, t_to)
    return _collide_over(rules, tla.robot_id, bps, _positions(tla, bps),
                         tlb.robot_id, _positions(tlb, bps))


def check_hold(rules: PrevalidateRules, timelines: tuple[Timeline, Timeline, Timeline],
               robot_id: int, xy: Any, t_from: float) -> Verdict:
    """Is parking ``robot_id`` at ``xy`` from ``t_from`` on (forever) safe vs what the others
    have committed (closed timelines count as holding forever)?"""
    xy = np.asarray(xy, dtype=np.float64)
    if xy.shape != (2,):
        raise ValueError(f"xy must have shape (2,), got {xy.shape}")
    q = quantize_f32(np.array([xy[0], xy[1], 0.0]))[:2]
    for other in (1, 2, 3):
        tl = timelines[other - 1]
        if other == robot_id or tl.n_segments == 0:
            continue
        until = _known_until(tl, False)
        if until < t_from:
            continue
        bps = _window_bps([tl.t], t_from, until)
        v = _collide_over(rules, robot_id, bps, np.tile(q, (len(bps), 1)), other,
                          _positions(tl, bps))
        if not v.ok:
            return v
    return OK


def try_append(rules: PrevalidateRules, timelines: tuple[Timeline, Timeline, Timeline],
               seg: Segment) -> Verdict:
    """Check ``seg`` against its own robot's rules/chain and the other robots' committed
    timelines over its time span; commit it only if everything passes."""
    rid = seg.robot_id
    tl = timelines[rid - 1]
    if tl.closed:
        return Verdict(False, Code.TIMELINE_CLOSED, seg.start_time_s, rid)
    p0, p1 = quantize_f32(seg.start_xyz_mm), quantize_f32(seg.end_xyz_mm)
    if not (np.isfinite(p0).all() and np.isfinite(p1).all()):
        return Verdict(False, Code.NONFINITE_VALUE, seg.start_time_s, rid)
    chain = tl.chain_code(seg.start_time_s, p0)
    if chain != Code.OK:
        return Verdict(False, chain, seg.start_time_s, rid)
    viol, _ = _local(rules, rid, np.array([seg.start_time_s]), np.array([seg.end_time_s]),
                     p0[None], p1[None], np.array([_MODE_CODE[seg.mode]]))
    code = _first_code(viol)
    if code != Code.OK:
        return Verdict(False, code, seg.start_time_s, rid)
    tl.push(seg.start_time_s, seg.end_time_s, p0, p1, _MODE_CODE[seg.mode])
    for other in (1, 2, 3):
        if other == rid:
            continue
        v = check_pair(rules, tl, timelines[other - 1], seg.start_time_s, seg.end_time_s)
        if not v.ok:
            tl.pop_last()
            return v
    return OK


def close_timeline(rules: PrevalidateRules, timelines: tuple[Timeline, Timeline, Timeline],
                   robot_id: int) -> Verdict:
    """Declare ``robot_id``'s schedule complete: it holds its last position forever.

    Checks that hold against the other robots' committed spans; on a collision the timeline
    stays open. Afterwards the others' appends are checked against the hold.
    """
    tl = timelines[robot_id - 1]
    if tl.n_segments == 0:
        return Verdict(False, Code.MISSING_ROBOT, 0.0, robot_id)
    tl.closed = True
    for other in (1, 2, 3):
        if other == robot_id:
            continue
        v = check_pair(rules, tl, timelines[other - 1], tl.end_time)
        if not v.ok:
            tl.closed = False
            return v
    return OK


# ------------------------------------------------------------------------- full check


def check_all(rules: PrevalidateRules, timelines: tuple[Timeline, Timeline, Timeline]) -> Report:
    """Everything: contract, per-robot rules on every segment, all pairs to the makespan.

    The CSV's terminal W row is the writer's job (``FINAL_MODE_NOT_W`` is a writer-lint code):
    a timeline's last segment may have any mode.
    """
    violations: list[Verdict] = []
    warnings: list[Verdict] = []
    for tl in timelines:
        rid = tl.robot_id
        if tl.n_segments == 0:
            violations.append(Verdict(False, Code.MISSING_ROBOT, 0.0, rid))
            continue
        t, xyz, m = tl.t, tl.xyz, tl.mode
        if t[0] != 0.0:
            violations.append(Verdict(False, Code.FIRST_TIME_NOT_ZERO, float(t[0]), rid))
        if not np.isfinite(xyz).all():
            violations.append(Verdict(False, Code.NONFINITE_VALUE, 0.0, rid))
            continue
        dur = np.diff(t)
        total = float(dur[m == _MODE_D].sum() + dur[m == _MODE_T].sum() + dur[m == _MODE_W].sum())
        if not math.isclose(total, float(t[-1]), rel_tol=1e-12, abs_tol=1e-9):
            violations.append(Verdict(False, Code.MODE_TIME_SUM_MISMATCH, float(t[-1]), rid))
        viol, warn = _local(rules, rid, t[:-1], t[1:], xyz[:-1], xyz[1:], m)
        for code, mask in viol:
            violations.extend(Verdict(False, code, float(t[i]), rid) for i in np.flatnonzero(mask))
        for code, mask in warn:
            warnings.extend(Verdict(True, code, float(t[i]), rid) for i in np.flatnonzero(mask))
    for a, b in ((1, 2), (1, 3), (2, 3)):
        v = check_pair(rules, timelines[a - 1], timelines[b - 1], hold_open=True)
        if not v.ok:
            violations.append(v)
    return Report(not violations, violations, warnings)
