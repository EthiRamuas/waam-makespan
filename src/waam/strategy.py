"""Value objects shared by the baseline strategies (docs/specs/baseline.md section 5-1).

``Task`` is a piece of a toolpath pass (B2); ``Cell`` bundles what the strategies read from the
config (B1, B12): robot count, bases, reach, homes, origin, timing, lift. Nothing here is specific
to a number of robots or to a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .geometry import CellGeometry
from .timing import TimingParams
from .toolpath import ToolpathParams


@dataclass(frozen=True, slots=True)
class Task:
    """A piece: a pass or part of a pass (B2). Vertices are XY; a closed ring repeats its first point."""

    layer: int
    z: float
    kind: str
    vertices: tuple[tuple[float, float], ...]
    length: float
    pass_index: int
    piece_index: int
    reachable: frozenset[int]  # robot ids that reach every vertex
    owner: int | None = None  # robot id from the sector split (B17); None before assignment


@dataclass(frozen=True, slots=True)
class Cell:
    robot_ids: tuple[int, ...]  # sorted ids; array index i <-> robot_ids[i]
    geometry: CellGeometry
    home_xyz: np.ndarray  # (n, 3)
    origin_xy: np.ndarray  # (2,) workspace centre
    timing: TimingParams
    lift_dz_mm: float

    @property
    def n_robots(self) -> int:
        return len(self.robot_ids)

    @property
    def base_xy(self) -> np.ndarray:
        return self.geometry.base_xy

    @classmethod
    def from_config(cls, cfg: Any, params: ToolpathParams | None = None) -> Cell:
        """Duck-typed on a Validator ``Config``: only attributes are read."""
        robots = sorted(cfg.robots, key=lambda r: r.id)
        if not robots:
            raise ValueError("config has no robots")
        p = params if params is not None else ToolpathParams.from_config(cfg)
        return cls(
            robot_ids=tuple(int(r.id) for r in robots),
            geometry=CellGeometry.from_config(cfg),
            home_xyz=np.array([[float(c) for c in r.home_xyz_mm] for r in robots], dtype=np.float64),
            origin_xy=np.asarray(cfg.workspace.center_xy_mm, dtype=np.float64),
            timing=TimingParams.from_config(cfg),
            lift_dz_mm=float(p.lift_dz_mm),
        )
