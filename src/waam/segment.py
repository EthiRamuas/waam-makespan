"""Segment: the internal schedule representation (data contract only).

Field names follow docs/spec.md section 3 (Exporter intermediate form). A segment is one
CSV row: its ``mode`` governs [start_time_s, end_time_s) and the motion inside is a linear
interpolation start -> end. Only structural invariants live here; anything that needs the
config (speeds, workspace, layers, reach, collisions) belongs to ``prevalidate``.

Units: mm, s. A robot's schedule is a chain of segments (see ``check_chain``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

Xyz = tuple[float, float, float]


class Mode(str, Enum):
    T = "T"  # travel: free XYZ move, no deposition
    D = "D"  # deposition
    W = "W"  # wait: position unchanged


class SegmentError(ValueError):
    """A segment or a segment chain violates a structural invariant."""


def _xyz(name: str, value: object) -> Xyz:
    try:
        x, y, z = (float(c) for c in value)  # type: ignore[attr-defined]
    except (TypeError, ValueError) as exc:
        raise SegmentError(f"{name} must be 3 numbers (x, y, z), got {value!r}") from exc
    if not all(map(math.isfinite, (x, y, z))):
        raise SegmentError(f"{name} must be finite, got {(x, y, z)}")
    return (x, y, z)


@dataclass(frozen=True, slots=True)
class Segment:
    robot_id: int
    mode: Mode
    start_time_s: float
    end_time_s: float
    start_xyz_mm: Xyz
    end_xyz_mm: Xyz

    def __post_init__(self) -> None:
        if isinstance(self.robot_id, bool) or self.robot_id not in (1, 2, 3):
            raise SegmentError(f"robot_id must be 1, 2 or 3, got {self.robot_id!r}")
        try:
            object.__setattr__(self, "mode", Mode(self.mode))
        except ValueError as exc:
            raise SegmentError(f"mode must be one of T, D, W, got {self.mode!r}") from exc
        t0, t1 = float(self.start_time_s), float(self.end_time_s)
        if not (math.isfinite(t0) and math.isfinite(t1)):
            raise SegmentError(f"times must be finite, got {(t0, t1)}")
        if t0 < 0.0:
            raise SegmentError(f"start_time_s must be >= 0, got {t0}")
        if not t1 > t0:
            raise SegmentError(f"end_time_s must be > start_time_s, got {(t0, t1)}")
        object.__setattr__(self, "start_time_s", t0)
        object.__setattr__(self, "end_time_s", t1)
        object.__setattr__(self, "start_xyz_mm", _xyz("start_xyz_mm", self.start_xyz_mm))
        object.__setattr__(self, "end_xyz_mm", _xyz("end_xyz_mm", self.end_xyz_mm))

    @property
    def duration_s(self) -> float:
        return self.end_time_s - self.start_time_s

    @property
    def length_xy_mm(self) -> float:
        return math.hypot(
            self.end_xyz_mm[0] - self.start_xyz_mm[0], self.end_xyz_mm[1] - self.start_xyz_mm[1]
        )

    @property
    def length_mm(self) -> float:
        return math.dist(self.start_xyz_mm, self.end_xyz_mm)


def check_chain(segments: list[Segment]) -> None:
    """Structural invariants of ONE robot's schedule; raises ``SegmentError``.

    - non-empty, a single robot_id
    - first segment starts at exactly t = 0.0
    - consecutive segments touch exactly in time and position (no gaps: fill with W)
    - the last segment is a W (the CSV's final row has mode W)

    Exact float equality is intended: ``timing.py`` must build chains from the previous
    segment's end values rather than recomputing them.
    """
    if not segments:
        raise SegmentError("a robot schedule needs at least one segment")
    rid = segments[0].robot_id
    if segments[0].start_time_s != 0.0:
        raise SegmentError(f"robot {rid}: first segment must start at 0.0, got "
                           f"{segments[0].start_time_s}")
    for i, seg in enumerate(segments):
        if seg.robot_id != rid:
            raise SegmentError(f"mixed robot ids in one chain: {rid} and {seg.robot_id}")
        if i == 0:
            continue
        prev = segments[i - 1]
        if seg.start_time_s != prev.end_time_s:
            raise SegmentError(
                f"robot {rid}: time gap/overlap between segment {i - 1} and {i}: "
                f"{prev.end_time_s} -> {seg.start_time_s}")
        if seg.start_xyz_mm != prev.end_xyz_mm:
            raise SegmentError(
                f"robot {rid}: position jump between segment {i - 1} and {i}: "
                f"{prev.end_xyz_mm} -> {seg.start_xyz_mm}")
    if segments[-1].mode is not Mode.W:
        raise SegmentError(f"robot {rid}: last segment must be W, got {segments[-1].mode.value}")
