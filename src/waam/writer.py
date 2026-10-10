"""writer: segment chains -> trajectory.csv + a linter that reads the file back (stage 6).

Contract (CLAUDE.md "trajectory.csv 계약", DECISIONS.md C-03, C-04, C-13):

- ``write_trajectory`` is the only way a schedule reaches disk. It first passes
  ``prevalidate.require_submittable`` (every timeline closed + the full Validator-semantics
  check), checks that the timelines are the schedule being written, renders, lints the
  rendered file and only then moves it to its final name. A rejected schedule leaves no file.
- Numbers: times with ``repr(float)``; coordinates as the float32-rounded value printed with
  ``repr(float)``. Rounding by the Validator's loader is thereby a no-op and the file means
  exactly what ``prevalidate`` checked. Line endings ``\\n``, UTF-8 without BOM.
- Every row's mode governs "this row until the next row". Each robot gets a terminal row of
  mode W at its last end time and position.
- ``lint_csv`` trusts nothing in memory: it parses the file, checks the contract, rebuilds
  segments from the rows and runs ``prevalidate.check_all`` on them.

Issue codes use the Validator's names (``prevalidate.Code`` names where one exists);
``FORMAT_CONTRACT`` marks a cell that is not in the writer's exact format.
"""

from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

import numpy as np

from .prevalidate import (
    _MODE_CODE,
    PrevalidateRules,
    Timeline,
    check_all,
    quantize_f32,
    require_submittable,
)
from .segment import Mode, Segment, SegmentError, check_chain

HEADER = "robot_id,time_s,x_mm,y_mm,z_mm,mode"
ROBOT_IDS = (1, 2, 3)


class LintIssue(NamedTuple):
    code: str
    robot: int = 0
    row: int = 0  # 1-based line number in the file (header = 1); 0 = not row-specific
    detail: str = ""


# ------------------------------------------------------------------------------- render


def _num(v: float) -> str:
    return repr(float(quantize_f32(v)))


def _row(rid: int, t: float, xyz: Sequence[float], mode: Mode) -> str:
    return f"{rid},{t!r},{_num(xyz[0])},{_num(xyz[1])},{_num(xyz[2])},{mode.value}"


def render_rows(chains: Mapping[int, Sequence[Segment]]) -> list[str]:
    """Header + one row per segment start + a terminal W row per robot (no I/O)."""
    if set(chains) != set(ROBOT_IDS):
        raise ValueError(f"chains must hold exactly robots {ROBOT_IDS}, got {sorted(chains)}")
    rows = [HEADER]
    for rid in ROBOT_IDS:
        segs = list(chains[rid])
        try:
            check_chain(segs)
        except SegmentError as exc:
            raise ValueError(str(exc)) from exc
        if segs[0].robot_id != rid:
            raise ValueError(f"chain {rid} holds robot {segs[0].robot_id}'s segments")
        for s in segs:
            rows.append(_row(rid, s.start_time_s, s.start_xyz_mm, s.mode))
        last = segs[-1]
        rows.append(_row(rid, last.end_time_s, last.end_xyz_mm, Mode.W))
    return rows


# -------------------------------------------------------------------------------- lint


def lint_csv(path: Path, rules: PrevalidateRules) -> list[LintIssue]:
    """All contract violations of the file at ``path`` (empty list = clean)."""
    raw = Path(path).read_bytes()
    issues: list[LintIssue] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(LintIssue("INVALID_CSV_HEADER", 0, 1, "UTF-8 BOM"))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return [*issues, LintIssue("INVALID_CSV_HEADER", 0, 0, f"not UTF-8: {exc}")]
    if "\r" in text:
        issues.append(LintIssue("INVALID_CSV_HEADER", 0, 0, "carriage return in file"))
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    else:
        issues.append(LintIssue("INVALID_CSV_HEADER", 0, len(lines), "missing final newline"))
    lines = [ln.rstrip("\r") for ln in lines]
    if not lines or lines[0] != HEADER:
        return [*issues, LintIssue("INVALID_CSV_HEADER", 0, 1, f"header must be {HEADER!r}")]

    parsed: list[tuple[int, int, float, np.ndarray, str]] = []  # line, rid, t, xyz64, mode
    for no, ln in enumerate(lines[1:], start=2):
        cells = ln.split(",")
        if len(cells) != 6:
            issues.append(LintIssue("INVALID_CSV_HEADER", 0, no, "row must have six cells"))
            continue
        if "" in cells:
            issues.append(LintIssue("NONFINITE_VALUE", 0, no, "empty cell"))
            continue
        if cells[0] not in ("1", "2", "3"):
            issues.append(LintIssue("INVALID_ROBOT_ID", 0, no, f"robot_id {cells[0]!r}"))
            continue
        if cells[5] not in ("T", "D", "W"):
            issues.append(LintIssue("INVALID_CSV_HEADER", int(cells[0]), no,
                                    f"mode {cells[5]!r} must be T, D or W"))
            continue
        try:
            vals = [float(c) for c in cells[1:5]]
        except ValueError:
            issues.append(LintIssue("NONFINITE_VALUE", int(cells[0]), no, "not a number"))
            continue
        xyz32 = np.asarray(vals[1:], dtype=np.float64)
        with np.errstate(over="ignore"):
            finite = np.isfinite(vals).all() and np.isfinite(xyz32.astype(np.float32)).all()
        if not finite:
            issues.append(LintIssue("NONFINITE_VALUE", int(cells[0]), no, "NaN/inf/overflow"))
            continue
        # exact writer format: Python float() also takes '_', spaces and non-ASCII digits that
        # the Validator's loader refuses, and float64 coordinates would not be float32 values
        want = [repr(vals[0])] + [repr(float(quantize_f32(v))) for v in vals[1:]]
        if cells[1:5] != want:
            bad = next(c for c, w in zip(cells[1:5], want) if c != w)
            issues.append(LintIssue("FORMAT_CONTRACT", int(cells[0]), no,
                                    f"cell {bad!r} is not the writer format (C-13)"))
            continue
        parsed.append((no, int(cells[0]), vals[0], xyz32, cells[5]))
    if issues:  # structural problems: semantic checks would only add noise
        return issues

    by_robot: dict[int, list[tuple[int, float, np.ndarray, str]]] = {r: [] for r in ROBOT_IDS}
    prev: tuple[int, float] | None = None
    for no, rid, t, xyz, mode in parsed:
        if prev is not None:
            if rid < prev[0]:
                issues.append(LintIssue("UNSORTED_TRAJECTORY", rid, no, "robot_id not ascending"))
            elif rid == prev[0] and t == prev[1]:
                issues.append(LintIssue("DUPLICATE_TIMESTAMP", rid, no, f"t={t!r}"))
            elif rid == prev[0] and t < prev[1]:
                issues.append(LintIssue("UNSORTED_TRAJECTORY", rid, no, "time not increasing"))
        prev = (rid, t)
        by_robot[rid].append((no, t, xyz, mode))
    for rid in ROBOT_IDS:
        rows = by_robot[rid]
        if len(rows) < 2:
            issues.append(LintIssue("MISSING_ROBOT", rid, 0, f"{len(rows)} row(s), need >= 2"))
            continue
        if rows[0][1] != 0.0:
            issues.append(LintIssue("FIRST_TIME_NOT_ZERO", rid, rows[0][0], f"t={rows[0][1]!r}"))
        if rows[-1][3] != "W":
            issues.append(LintIssue("FINAL_MODE_NOT_W", rid, rows[-1][0], rows[-1][3]))
    if issues:
        return issues

    segs_by_robot: dict[int, list[Segment]] = {r: [] for r in ROBOT_IDS}
    for rid in ROBOT_IDS:
        rows = by_robot[rid]
        durations = {"T": 0.0, "D": 0.0, "W": 0.0}
        for (no, t0, p0, mode), (_, t1, p1, _m) in zip(rows[:-1], rows[1:]):
            durations[mode] += t1 - t0
            q0, q1 = quantize_f32(p0), quantize_f32(p1)
            if mode == "W" and math.dist(q0, q1) > rules.wait_position_tolerance_mm:
                issues.append(LintIssue("WAIT_POSITION_CHANGED", rid, no,
                                        f"moves {math.dist(q0, q1)!r} mm"))
            if mode == "D":
                if not math.hypot(q1[0] - q0[0], q1[1] - q0[1]) > 0.0:
                    issues.append(LintIssue("DEPOSITION_ZERO_LENGTH", rid, no))
                if abs(q1[2] - q0[2]) > rules.layer_z_tolerance_mm:
                    issues.append(LintIssue("DEPOSITION_VERTICAL_MOVE", rid, no,
                                            f"dz={q1[2] - q0[2]!r}"))
            segs_by_robot[rid].append(Segment(rid, Mode(mode), t0, t1, tuple(p0), tuple(p1)))
        if not math.isclose(sum(durations.values()), rows[-1][1], rel_tol=1e-12, abs_tol=1e-9):
            issues.append(LintIssue("MODE_TIME_SUM_MISMATCH", rid, rows[-1][0]))
    if issues:
        return issues

    # the file as a schedule: everything the Validator decides except shape
    timelines = tuple(Timeline.from_segments(r, segs_by_robot[r]) for r in ROBOT_IDS)
    report = check_all(rules, timelines)  # type: ignore[arg-type]
    return [LintIssue(v.code.name, v.robot, 0, f"t={v.t!r} other={v.other}")
            for v in report.violations]


# ------------------------------------------------------------------------------- write


def _same_schedule(chains: Mapping[int, Sequence[Segment]],
                   timelines: Sequence[Timeline]) -> str | None:
    """Why ``timelines`` is not the schedule in ``chains`` (None = identical)."""
    if sorted(tl.robot_id for tl in timelines) != list(ROBOT_IDS):
        return f"timelines hold robots {[tl.robot_id for tl in timelines]}, need {ROBOT_IDS}"
    for tl in timelines:
        segs = chains[tl.robot_id]
        if tl.n_segments != len(segs):
            return f"robot {tl.robot_id}: {tl.n_segments} timeline segments, {len(segs)} in chain"
        t = np.array([s.start_time_s for s in segs] + [segs[-1].end_time_s])
        xyz = quantize_f32([s.start_xyz_mm for s in segs] + [segs[-1].end_xyz_mm])
        mode = np.array([_MODE_CODE[sg.mode] for sg in segs], dtype=np.uint8)
        for what, a, b in (("times", tl.t, t), ("positions", tl.xyz, xyz), ("modes", tl.mode, mode)):
            if not np.array_equal(a, b):
                return f"robot {tl.robot_id}: timeline {what} differ from the chain"
    return None


def write_trajectory(path: Path, chains: Mapping[int, Sequence[Segment]],
                     rules: PrevalidateRules,
                     timelines: tuple[Timeline, Timeline, Timeline]) -> Path:
    """Gate, render, lint, publish ``path``. Raises ``ValueError``; no file on rejection."""
    path = Path(path)
    rows = render_rows(chains)  # also validates chain structure
    require_submittable(rules, timelines)
    if (why := _same_schedule(chains, timelines)) is not None:
        raise ValueError(f"timelines are not the schedule being written: {why}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(("\n".join(rows) + "\n").encode("utf-8"))
        issues = lint_csv(tmp, rules)
        if issues:
            raise ValueError("written file failed lint: " + "; ".join(
                f"{i.code}(robot {i.robot}, row {i.row}) {i.detail}".strip() for i in issues[:5]))
        try:
            os.replace(tmp, path)
        except OSError as exc:  # e.g. the target is open elsewhere (Windows)
            raise ValueError(f"cannot replace {path}: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)  # also on any unexpected error; no half-written leftovers
    return path
