"""timing: ordered steps -> a gap-free Segment chain with times filled in (stage 5).

The scheduler decides who does what in which order (``Step``); this module only fills in
the clock. Rules (DECISIONS.md C-08..C-11):

- ``pass``: a continuous deposition polyline. ``arc_on`` W at its first vertex, one D per
  polyline edge at the deposition speed, ``arc_off`` W at its last vertex.
- ``travel``: one T segment to the target at the travel speed.
- ``wait``: one W segment of the given duration.

Durations use the float32-quantized endpoints, i.e. the coordinates the Validator's loader
sees, so the speed check holds after the CSV round trip. Each segment starts from the
previous one's exact end values (``segment.check_chain`` demands exact equality).

Geometry rules (workspace, reach, vertical D, Z layer, collisions) are ``prevalidate``'s job;
here a D edge is only refused when its quantized 3D length is zero (no duration exists).
The chain's times must be written with ``repr`` (the seams are exact only in float64).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from waam.prevalidate import quantize_f32
from waam.segment import Mode, Segment, Xyz, check_chain


@dataclass(frozen=True, slots=True)
class TimingParams:
    deposition_speed_mm_s: float
    travel_speed_mm_s: float
    arc_on_s: float
    arc_off_s: float

    def __post_init__(self) -> None:
        for name in ("deposition_speed_mm_s", "travel_speed_mm_s"):
            v = getattr(self, name)
            if not (math.isfinite(v) and v > 0.0):
                raise ValueError(f"{name} must be finite and > 0, got {v!r}")
        for name in ("arc_on_s", "arc_off_s"):
            v = getattr(self, name)
            if not (math.isfinite(v) and v >= 0.0):  # 0 only if the config says so
                raise ValueError(f"{name} must be finite and >= 0, got {v!r}")

    @classmethod
    def from_config(cls, cfg: Any) -> TimingParams:
        p = cfg.process
        if p.arc_on_time_s is None or p.arc_off_time_s is None:
            raise ValueError("config has no arc_on/arc_off time; arc time is never omitted")
        return cls(
            deposition_speed_mm_s=float(p.deposition_speed_mm_s),
            travel_speed_mm_s=float(p.travel_speed_mm_s),
            arc_on_s=float(p.arc_on_time_s),
            arc_off_s=float(p.arc_off_time_s),
        )


@dataclass(frozen=True, slots=True)
class Step:
    kind: Literal["pass", "travel", "wait"]
    points: tuple[Xyz, ...] = ()  # pass: >= 2 vertices; travel: (target,); wait: ()
    duration_s: float | None = None  # wait only


def _qdist(a: Xyz, b: Xyz) -> float:
    return float(math.dist(quantize_f32(a), quantize_f32(b)))


def build_chain(rid: int, start_xyz: Xyz, steps: Sequence[Step],
                params: TimingParams) -> list[Segment]:
    """Segment chain for robot ``rid`` starting at t = 0.0 at ``start_xyz``."""
    if not steps:
        raise ValueError("a robot needs at least one step (park it with a wait step)")
    segs: list[Segment] = []
    t = 0.0
    pos: Xyz = tuple(float(c) for c in start_xyz)  # type: ignore[assignment]

    def add(mode: Mode, dur: float, end: Xyz) -> None:
        nonlocal t, pos
        seg = Segment(rid, mode, t, t + dur, pos, end)
        segs.append(seg)
        t, pos = seg.end_time_s, seg.end_xyz_mm

    for i, st in enumerate(steps):
        if st.kind == "wait":
            if st.duration_s is None or not st.duration_s > 0.0:
                raise ValueError(f"step {i}: wait needs duration_s > 0")
            add(Mode.W, st.duration_s, pos)
        elif st.kind == "travel":
            if len(st.points) != 1:
                raise ValueError(f"step {i}: travel needs exactly one target point")
            target = tuple(float(c) for c in st.points[0])
            d = _qdist(pos, target)  # type: ignore[arg-type]
            if d > 0.0:
                add(Mode.T, d / params.travel_speed_mm_s, target)  # type: ignore[arg-type]
        elif st.kind == "pass":
            if len(st.points) < 2:
                raise ValueError(f"step {i}: pass needs at least two vertices")
            # same point as far as the Validator can tell (float32): continue from `pos`
            if not np.array_equal(quantize_f32(st.points[0]), quantize_f32(pos)):
                raise ValueError(f"step {i}: pass must start at the robot's current position "
                                 f"{pos}, got {st.points[0]} (insert a travel step)")
            if params.arc_on_s > 0.0:
                add(Mode.W, params.arc_on_s, pos)
            for b in st.points[1:]:
                b = tuple(float(c) for c in b)
                d = _qdist(pos, b)  # type: ignore[arg-type]
                if not d > 0.0:
                    raise ValueError(f"step {i}: zero-length deposition edge {pos} -> {b}")
                add(Mode.D, d / params.deposition_speed_mm_s, b)  # type: ignore[arg-type]
            if params.arc_off_s > 0.0:
                add(Mode.W, params.arc_off_s, pos)
        else:
            raise ValueError(f"step {i}: unknown kind {st.kind!r}")
    if not segs:
        raise ValueError("steps produced no segment (all travels had zero length)")
    check_chain(segs)
    return segs
