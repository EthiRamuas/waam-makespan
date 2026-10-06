"""Reference helpers: run the Validator itself (everything except shape) on our schedules.

``validator_verdict`` composes the same stages the Validator's pipeline runs before the
shape step: loader, ``validate_trajectory_set``, schedule metrics, collision analysis.
Nothing here modifies the Validator; it is only imported and called.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from waam_validator.collision.simulator import run_collision_analysis
from waam_validator.errors import WaamValidatorError
from waam_validator.schedule.metrics import compute_schedule_metrics
from waam_validator.trajectory.loader import load_trajectory_csv
from waam_validator.trajectory.validator import validate_trajectory_set

from waam.prevalidate import Timeline
from waam.segment import Segment

COLLISION_CODES = {"ARM_ENVELOPE", "TCP_RADIUS"}

SAMPLE_JOB = Path(__file__).parent / "fixtures" / "sample_job"
MODEL01_DIR = Path("C:/Github/WAAM_Validator/tests/01")


def _num(v: float, raw: bool) -> str:
    return repr(float(v)) if raw else repr(float(np.float32(v)))


def write_csv(path: Path, chains: dict[int, list[Segment]], *, raw: bool = False) -> Path:
    """Segments -> trajectory.csv: one row per segment start + a terminal W row per robot."""
    lines = ["robot_id,time_s,x_mm,y_mm,z_mm,mode"]
    for rid in (1, 2, 3):
        segs = chains[rid]
        for s in segs:
            x, y, z = (_num(c, raw) for c in s.start_xyz_mm)
            lines.append(f"{rid},{s.start_time_s!r},{x},{y},{z},{s.mode.value}")
        last = segs[-1]
        x, y, z = (_num(c, raw) for c in last.end_xyz_mm)
        lines.append(f"{rid},{last.end_time_s!r},{x},{y},{z},W")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def timelines_of(chains: dict[int, list[Segment]]) -> tuple[Timeline, Timeline, Timeline]:
    return tuple(Timeline.from_segments(rid, chains[rid]) for rid in (1, 2, 3))  # type: ignore[return-value]


def validator_verdict(csv_path: Path, cfg) -> tuple[bool, set[str]]:
    """(passes everything but shape, set of failing reason codes) from the real Validator."""
    try:
        ts = load_trajectory_csv(csv_path, cfg)
        messages = validate_trajectory_set(ts, cfg)
    except WaamValidatorError as exc:
        return False, {exc.code}
    reasons = {v.code for v in messages.violations}
    try:
        compute_schedule_metrics(ts)
    except ArithmeticError:
        reasons.add("MODE_TIME_SUM_MISMATCH")
    result = run_collision_analysis(ts, cfg)
    reasons |= {e.collision_type for e in result.events}
    return not reasons, reasons
