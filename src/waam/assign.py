"""Assignment strategies of the baseline (docs/specs/baseline.md B13, B16-B19).

``HandoverAssigner`` (strategy S) hands a layer's pieces from robot to robot with as few handovers as
possible; ``SectorAssigner`` (strategy P) gives every piece to the owner of its sector. Both read the
robots, bases and reach from the ``Cell`` (B12) and are deterministic (B11).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .pieces import split_at_sectors
from .sector import delta_max, sector_bounds
from .strategy import Cell, Task


class AssignmentError(ValueError):
    """The assignment cannot be made (a piece nobody reaches): the strategy fails."""


@dataclass(frozen=True, slots=True)
class Run:
    """Consecutive pieces one robot processes in one layer (S)."""

    robot: int
    layer: int
    tasks: tuple[Task, ...]


class Assignment(dict):
    """``{robot_id: [Task, ...]}`` (the protocol type) plus strategy extras."""

    def __init__(self, data=(), *, runs: Sequence[Run] = (), part_center=(0.0, 0.0), delta_rad=0.0,
                 extra_pieces=0) -> None:
        super().__init__(data)
        self.runs: list[Run] = list(runs)
        self.part_center = tuple(part_center)
        self.delta_rad = float(delta_rad)
        self.extra_pieces = int(extra_pieces)


def _key(t: Task) -> tuple[int, int, int]:
    return (t.layer, t.pass_index, t.piece_index)


def part_center(tasks: Sequence[Task]) -> tuple[float, float]:
    """U-12: centre of the bounding box of all D vertices (all layers)."""
    pts = np.array([p for t in tasks for p in t.vertices], dtype=np.float64)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    return float((lo[0] + hi[0]) / 2.0), float((lo[1] + hi[1]) / 2.0)


def mid_point(t: Task) -> tuple[float, float]:
    """Point at half the arc length of the piece."""
    v = np.array(t.vertices, dtype=np.float64)
    seg = np.hypot(*np.diff(v, axis=0).T)
    total = float(seg.sum())
    if total <= 0.0:
        return float(v[0][0]), float(v[0][1])
    k = min(int(np.searchsorted(np.cumsum(seg), total / 2.0, side="left")), len(seg) - 1)
    s = (total / 2.0 - float(seg[:k].sum())) / float(seg[k]) if seg[k] > 0.0 else 0.0
    p = v[k] + s * (v[k + 1] - v[k])
    return float(p[0]), float(p[1])


# ---------------------------------------------------------------------------- S


class HandoverAssigner:
    """B13. Per layer, in the toolpath's canonical order: the current robot first processes every
    piece it reaches; the remaining pieces go to the robot reaching the most remaining length
    (ties: smaller id), repeated. Between layers the last robot continues."""

    name = "S"

    def assign(self, tasks: Sequence[Task], cell: Cell) -> Assignment:
        by_layer: dict[int, list[Task]] = {}
        for t in sorted(tasks, key=_key):
            if not t.reachable:
                raise AssignmentError(f"piece (layer {t.layer}, pass {t.pass_index}) has no robot")
            by_layer.setdefault(t.layer, []).append(t)
        runs: list[Run] = []
        cur: int | None = None
        for layer in sorted(by_layer):
            todo = list(by_layer[layer])
            while todo:
                if cur is None or not any(cur in t.reachable for t in todo):
                    length = {rid: sum(t.length for t in todo if rid in t.reachable)
                              for rid in cell.robot_ids}
                    cur = min(cell.robot_ids, key=lambda rid: (-length[rid], rid))
                mine = tuple(t for t in todo if cur in t.reachable)
                runs.append(Run(cur, layer, mine))
                todo = [t for t in todo if cur not in t.reachable]
        data = {rid: [t for r in runs if r.robot == rid for t in r.tasks] for rid in cell.robot_ids}
        return Assignment(data, runs=runs)


# ---------------------------------------------------------------------------- P


class SectorAssigner:
    """B16-B19 (C-43, C-44, C-47). ``delta``: rotation of the sector boundaries in radians, or
    ``"auto"`` (C-43: the 2 degree grid point within +-delta_max that minimises the largest sector
    load D time + arc time, ties: smaller |delta|). Default 0 until measured (U-16)."""

    name = "P"

    def __init__(self, delta: float | str = 0.0) -> None:
        self.delta = delta

    def _split(self, tasks, cell, delta):
        return split_at_sectors(tasks, cell, sector_bounds(cell, delta))

    def auto_delta(self, tasks: Sequence[Task], cell: Cell) -> float:
        pts = np.array([p for t in tasks for p in t.vertices], dtype=np.float64)
        r_max = float(np.max(np.hypot(*(pts - cell.origin_xy).T)))
        dmax = delta_max(cell, sector_bounds(cell), r_max)
        k = max(int(math.floor(math.degrees(dmax) / 2.0 + 1e-9)), 0)
        arc = cell.timing.arc_on_s + cell.timing.arc_off_s
        best = None
        for j in sorted(range(-k, k + 1), key=lambda j: (abs(j), j)):
            delta = math.radians(2.0 * j)
            out = self._split(tasks, cell, delta)
            load = dict.fromkeys(cell.robot_ids, 0.0)
            for t in out.tasks:
                load[t.owner] += t.length / cell.timing.deposition_speed_mm_s + arc
            peak = max(load.values())
            if best is None or peak < best[0] - 1e-12:
                best = (peak, delta)
        return best[1]

    def assign(self, tasks: Sequence[Task], cell: Cell) -> Assignment:
        delta = self.auto_delta(tasks, cell) if self.delta == "auto" else float(self.delta)
        out = self._split(tasks, cell, delta)
        if out.unresolved:
            raise AssignmentError(f"{len(out.unresolved)} pieces nobody reaches (B18 step 3)")
        center = part_center(tasks)
        c = np.array(center)

        def order(t: Task):  # B19: farthest from the part centre first, then canonical
            m = np.array(mid_point(t))
            return (t.layer, -float(np.hypot(*(m - c))), t.pass_index, t.piece_index)

        data = {rid: sorted((t for t in out.tasks if t.owner == rid), key=order)
                for rid in cell.robot_ids}
        return Assignment(data, part_center=center, delta_rad=delta, extra_pieces=out.extra_pieces)
