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
from .sector import SectorSpec, owner_index
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
    """Maximal intervals of u in [0, nseg] where robot ``idx`` reaches the polyline (d <= R + eps/2)."""
    g = cell.geometry
    r_eff = float(g.reach_mm[idx] + 0.5 * g.eps_mm)  # cut points stay inside R + eps despite rounding
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
    ``geometry.in_reach`` rule) extends farthest, cut at the exact circle/segment intersection,
    repeat. Raises ``PieceError`` if some point is reached by nobody."""
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
    tasks: list[Task]  # every piece, owner = sector owner (robot id)
    unresolved: tuple[int, ...]  # indices into ``tasks`` whose owner cannot reach every vertex (B18)
    cut_tasks: int  # input tasks cut into more than one piece
    extra_pieces: int  # output pieces - input tasks

    @property
    def fallback_pieces(self) -> int:
        return len(self.unresolved)

    @property
    def fallback_length_mm(self) -> float:
        return float(sum(self.tasks[i].length for i in self.unresolved))


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
    parts dropped, closed rings merged). B18: report the pieces whose owner cannot reach every
    vertex; the reassignment to a neighbour is **not** implemented (the spec leaves the neighbour
    choice and the following B3 split open), so these pieces keep the sector owner."""
    out: list[Task] = []
    unresolved: list[int] = []
    cut = 0
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
            owner = cell.robot_ids[lab]
            k = seq.get(task.pass_index, 0)
            seq[task.pass_index] = k + 1
            reach = _reach_ids(cell, pv)
            piece = Task(task.layer, task.z, task.kind, _tuple(pv), _length(pv), task.pass_index,
                         k, reach, owner)
            if owner not in reach:
                unresolved.append(len(out))
            out.append(piece)
    return SectorSplit(out, tuple(unresolved), cut, len(out) - len(tasks))
