"""Pieces: toolpath passes cut at reach boundaries (B3) and at sector boundaries (B17, B18).

A piece is a ``strategy.Task``. All functions are pure and deterministic; the number of robots,
the bases and the reach come from the ``Cell`` (B1, B12).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from . import geometry as geo
from .prevalidate import float32_buffer_mm
from .sector import SectorSpec, angular_distance_to_sector, owner_index
from .strategy import Cell, Task

_U_TOL = 1e-9  # tolerance in the polyline parameter u = segment index + t


class PieceError(ValueError):
    """A pass has a point no robot reaches (the toolpath checks the workspace, so this is a defect)."""


def _reach_ids(cell: Cell, pts: np.ndarray) -> frozenset[int]:
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    return frozenset(
        rid for rid in cell.robot_ids if bool(np.all(geo.in_reach(cell.geometry, rid, pts)))
    )


def _length(v: np.ndarray) -> float:
    return float(np.hypot(*np.diff(v, axis=0).T).sum()) if len(v) > 1 else 0.0


def _tuple(v: np.ndarray) -> tuple[tuple[float, float], ...]:
    return tuple((float(x), float(y)) for x, y in v)


def passes_to_tasks(passes: Sequence[Any], cell: Cell) -> list[Task]:
    """One task per pass, unchanged (``Pass.reachable_robots`` is kept)."""
    del cell
    return [
        Task(layer=q.layer, z=q.z, kind=q.kind, vertices=tuple(q.vertices), length=q.length,
             pass_index=i, piece_index=0, reachable=frozenset(q.reachable_robots))
        for i, q in enumerate(passes)
    ]


# ------------------------------------------------------------------ B3: reach boundaries


def _robot_intervals(v: np.ndarray, cell: Cell, idx: int) -> list[tuple[float, float]]:
    """Maximal intervals of u in [0, nseg] where robot ``idx`` reaches the polyline (d <= R - float32_buffer_mm)."""
    g = cell.geometry
    # C-47 (hypothesis): cut on R - float32_buffer_mm, inside the Validator limit R + eps even after
    # the float32 quantisation of the Validator's loader
    r_eff = float(g.reach_mm[idx] - float32_buffer_mm(g))
    base = g.base_xy[idx]
    out: list[tuple[float, float]] = []
    for k in range(len(v) - 1):
        a, b = v[k], v[k + 1]
        d = b - a
        f = a - base
        qa = float(d @ d)
        qc = float(f @ f) - r_eff**2
        if qa == 0.0:
            lo, hi = (0.0, 1.0) if qc <= 0.0 else (1.0, 0.0)
        else:
            qb = 2.0 * float(f @ d)
            disc = qb * qb - 4.0 * qa * qc
            if disc < 0.0:
                continue
            sq = math.sqrt(disc)
            lo = max((-qb - sq) / (2.0 * qa), 0.0)
            hi = min((-qb + sq) / (2.0 * qa), 1.0)
        if lo > hi:
            continue
        s, e = k + lo, k + hi
        if out and s <= out[-1][1] + _U_TOL:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _point_at(v: np.ndarray, u: float) -> np.ndarray:
    nseg = len(v) - 1
    k = min(int(math.floor(u)), nseg - 1)
    t = u - k
    if t <= _U_TOL:
        return v[k].copy()
    if t >= 1.0 - _U_TOL:
        return v[k + 1].copy()
    return v[k] + t * (v[k + 1] - v[k])


def _sub_polyline(v: np.ndarray, x0: float, x1: float) -> np.ndarray:
    pts = [_point_at(v, x0)]
    for j in range(int(math.floor(x0)) + 1, int(math.ceil(x1))):
        if x0 + _U_TOL < j < x1 - _U_TOL:
            pts.append(v[j].copy())
    pts.append(_point_at(v, x1))
    return np.array(pts)


def split_at_reach(passes: Sequence[Any], cell: Cell) -> list[Task]:
    """B3. A pass some robot reaches entirely is kept whole. A pass nobody reaches entirely is cut
    greedily: from the current position take the robot whose reach interval (d <= R + eps, the
    ``geometry.in_reach`` rule, shrunk by ``float32_buffer_mm`` per C-47) extends farthest, cut at
    the exact circle/segment intersection, repeat. Raises ``PieceError`` if some point is reached by nobody."""
    tasks: list[Task] = []
    for pi, q in enumerate(passes):
        if q.reachable_robots:
            tasks.append(Task(q.layer, q.z, q.kind, tuple(q.vertices), q.length, pi, 0,
                              frozenset(q.reachable_robots)))
            continue
        v = np.array(q.vertices, dtype=np.float64)
        nseg = len(v) - 1
        if nseg < 1:
            raise PieceError(f"pass {pi}: fewer than two vertices and unreachable")
        intervals = [_robot_intervals(v, cell, i) for i in range(cell.n_robots)]
        cuts = [0.0]
        x = 0.0
        while x < nseg - _U_TOL:
            best = -1.0
            for iv in intervals:
                for s, e in iv:
                    if s <= x + _U_TOL and e > x + _U_TOL and e > best:
                        best = e
            if best < 0.0:
                p = _point_at(v, x)
                raise PieceError(f"pass {pi} layer {q.layer}: nobody reaches ({p[0]:.6f}, {p[1]:.6f})")
            x = min(best, float(nseg))
            cuts.append(x)
        for ci in range(len(cuts) - 1):
            pv = _sub_polyline(v, cuts[ci], cuts[ci + 1])
            reach = _reach_ids(cell, pv)
            if not reach:
                raise PieceError(f"pass {pi} layer {q.layer}: piece {ci} has no common robot")
            tasks.append(Task(q.layer, q.z, q.kind, _tuple(pv), _length(pv), pi, ci, reach))
    return tasks


# ------------------------------------------------------------------ B17, B18: sector boundaries


@dataclass(frozen=True, slots=True)
class SectorSplit:
    tasks: list[Task]  # every piece; owner = sector owner, or the robot chosen by the fallback (B18)
    unresolved: tuple[int, ...]  # indices into ``tasks`` nobody reaches (fallback step 3): P must fail
    cut_tasks: int  # input tasks cut into more than one piece by sector boundaries
    extra_pieces: int  # output pieces - input tasks (includes fallback B3 splits)
    triggered: int = 0  # sector pieces whose owner could not reach every vertex (fallback fired)

    @property
    def fallback_pieces(self) -> int:
        return self.triggered

    @property
    def fallback_length_mm(self) -> float:
        return float(sum(self.tasks[i].length for i in self.unresolved))


@dataclass(frozen=True, slots=True)
class _PassLike:
    layer: int
    z: float
    kind: str
    vertices: tuple
    length: float
    reachable_robots: frozenset


def _mid_angle(pv: np.ndarray, spec: SectorSpec) -> float:
    """Angle (about the origin) of the point at half the arc length of the polyline."""
    seg = np.hypot(*np.diff(pv, axis=0).T) if len(pv) > 1 else np.zeros(0)
    total = float(seg.sum())
    if total <= 0.0:
        p = pv[0]
    else:
        half = total / 2.0
        k = int(np.searchsorted(np.cumsum(seg), half, side="left"))
        k = min(k, len(seg) - 1)
        before = float(seg[:k].sum())
        t = (half - before) / float(seg[k]) if seg[k] > 0.0 else 0.0
        p = pv[k] + t * (pv[k + 1] - pv[k])
    return math.atan2(p[1] - spec.origin_xy[1], p[0] - spec.origin_xy[0])


def _best_owner(candidates: frozenset[int], pv: np.ndarray, cell: Cell, spec: SectorSpec) -> int:
    """B18 step 1: the candidate whose sector is angularly nearest to the piece midpoint (ties: smaller id)."""
    ang = _mid_angle(pv, spec)
    return min(candidates, key=lambda rid: (
        angular_distance_to_sector(spec, cell.robot_ids.index(rid), ang), rid))


def _fallback(task: Task, pv: np.ndarray, sector_owner: int, cell: Cell,
              spec: SectorSpec) -> list[tuple[np.ndarray, int, frozenset[int], bool]]:
    """B18 (C-47): (1) hand the piece to the nearest-sector robot that reaches all of it; (2) if none,
    cut it with B3 and apply (1) to each part; (3) a part nobody reaches stays with the sector owner,
    flagged unresolved. Returns (vertices, owner, reachable, resolved) per part."""
    reach = _reach_ids(cell, pv)
    if reach:
        return [(pv, _best_owner(reach, pv, cell, spec), reach, True)]
    like = _PassLike(task.layer, task.z, task.kind, _tuple(pv), _length(pv), frozenset())
    try:
        parts = split_at_reach([like], cell)
    except PieceError:
        return [(pv, sector_owner, reach, False)]
    return [(np.array(t.vertices), _best_owner(t.reachable, np.array(t.vertices), cell, spec),
             t.reachable, True) for t in parts]


def _runs(v: np.ndarray, spec: SectorSpec) -> list[tuple[int, np.ndarray]]:
    """Cut the polyline at the sector boundary rays; consecutive sub-intervals of one sector form a
    run. A closed ring whose first and last runs lie in one sector is merged (U-10)."""
    A, B = v[:-1], v[1:]
    D = B - A
    L = np.hypot(D[:, 0], D[:, 1])
    nb = spec.n if spec.n > 1 else 0
    ts = np.full((len(A), max(nb, 1)), 1.0)
    ang = spec.boundary_angles()
    ox, oy = spec.origin_xy
    for k in range(nb):
        dx, dy = math.cos(ang[k]), math.sin(ang[k])
        ca = dx * (A[:, 1] - oy) - dy * (A[:, 0] - ox)
        cd = dx * D[:, 1] - dy * D[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = -ca / cd
        t = np.where(cd != 0.0, t, 0.0)
        pt = A + D * t[:, None]
        ok = (cd != 0.0) & (t > 0.0) & (t < 1.0) & (
            ((pt[:, 0] - ox) * dx + (pt[:, 1] - oy) * dy) > 0.0)
        ts[:, k] = np.where(ok, t, 1.0)
    ts.sort(axis=1)
    bp = np.concatenate([np.zeros((len(A), 1)), ts, np.ones((len(A), 1))], axis=1)
    p_lo = np.where((bp[:, :-1] == 0.0)[..., None], A[:, None, :],
                    A[:, None, :] + D[:, None, :] * bp[:, :-1, None])
    p_hi = np.where((bp[:, 1:] == 1.0)[..., None], B[:, None, :],
                    A[:, None, :] + D[:, None, :] * bp[:, 1:, None])
    sl = L[:, None] * (bp[:, 1:] - bp[:, :-1])
    keep = sl > 0.0
    sa, sb = p_lo[keep], p_hi[keep]
    if len(sa) == 0:
        return []
    lab = owner_index(spec, (sa + sb) / 2.0)
    starts = np.flatnonzero(np.concatenate([[True], lab[1:] != lab[:-1]]))
    ends = np.concatenate([starts[1:], [len(lab)]])
    runs = [(int(lab[s]), np.vstack([sa[s:e][:1], sb[s:e]])) for s, e in zip(starts, ends)]
    closed = len(v) >= 2 and bool(np.allclose(v[0], v[-1]))
    if closed and len(runs) > 1 and runs[0][0] == runs[-1][0]:
        first, last = runs[0], runs[-1]
        runs = runs[1:-1] + [(last[0], np.vstack([last[1], first[1][1:]]))]
    return runs


def split_at_sectors(tasks: Sequence[Task], cell: Cell, spec: SectorSpec) -> SectorSplit:
    """B17: cut every task at the sector boundary rays (half-open sectors [lo, hi), zero-length
    parts dropped, closed rings merged). B18 (C-47): a piece whose sector owner cannot reach every
    vertex is reassigned (see ``_fallback``); pieces nobody reaches are listed in ``unresolved``."""
    out: list[Task] = []
    unresolved: list[int] = []
    cut = 0
    triggered = 0
    seq: dict[int, int] = {}
    for task in tasks:
        v = np.array(task.vertices, dtype=np.float64)
        runs = _runs(v, spec) if len(v) >= 2 else []
        if len(runs) <= 1:
            lab = runs[0][0] if runs else int(owner_index(spec, v[:1])[0])
            runs = [(lab, v)]
        else:
            cut += 1
        for lab, pv in runs:
            sector_owner = cell.robot_ids[lab]
            reach = _reach_ids(cell, pv)
            if sector_owner in reach:
                parts = [(pv, sector_owner, reach, True)]
            else:
                triggered += 1
                parts = _fallback(task, pv, sector_owner, cell, spec)
            for part_v, owner, part_reach, ok in parts:
                k = seq.get(task.pass_index, 0)
                seq[task.pass_index] = k + 1
                if not ok:
                    unresolved.append(len(out))
                out.append(Task(task.layer, task.z, task.kind, _tuple(part_v), _length(part_v),
                                task.pass_index, k, part_reach, owner))
    return SectorSplit(out, tuple(unresolved), cut, len(out) - len(tasks), triggered)
