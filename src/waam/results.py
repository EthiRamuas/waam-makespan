"""results: the append-only experiment log ``experiments/results.csv`` (DECISIONS.md C-17).

One row per run. The first six columns are a promise to the ``waam-status`` / ``waam-decide``
skills (docs/operations.md section 2-4): they read ``model, algo, makespan_s, ratio, compute_s,
passed`` by name.

Column meanings
---------------
``compute_s``
    Our algorithm's run time in seconds (wall clock): assignment, scheduling, timing and
    writing. The Validator's run time is NOT included. Measure on the one fixed machine
    (docs/playbook.md), otherwise numbers of different runs are not comparable.
``makespan_s``
    The last waypoint time over the robots. For a run the Validator checked it is the value
    in that run's ``summary.json``, taken as is.
``lower_bound_s`` / ``ratio``
    ``lower_bound_s`` is in SECONDS (docs/spec.md prints the bounds in hours: convert).
    ``ratio = makespan_s / lower_bound_s``. Without a lower bound ``ratio`` stays empty
    (not measured): nothing is estimated.
``passed``
    True only if the Validator ran and its ``summary.json`` says ``status == "PASS"``; False
    if it ran and said FAIL; EMPTY if the Validator was not run. A prevalidate verdict
    never becomes ``passed``: "not run" must not read as "run and passed".
``validator_status`` / ``validator_version``
    ``status`` / ``validator_version`` copied from ``summary.json``; empty if not run.

Rules
-----
- Rows are only ever appended, never edited or removed (older strategies are the comparison
  group). A file whose header differs from ``COLUMNS`` (including CRLF or a BOM) is refused.
- ONE WRITER AT A TIME. ``append_result`` is not safe against concurrent appends (measured:
  rows are lost and headers duplicated). A parallel sweep must give every worker its own file
  and merge afterwards; nothing here locks.
- ``make_row`` binds a Validator verdict to the trajectory it judged (DECISIONS.md C-19): the
  summary must be named ``summary.json``, sit next to the Validator's ``validation_inputs.json``,
  and that file's sha256 of ``trajectory.csv`` must equal the sha256 of ``trajectory_path``.
  Not checked yet: that the Validator ran with the official ``config.yaml`` / ``target.stl``
  (DECISIONS.md C-21, to be decided when ``run_all`` is designed).
- The invariants live in ``ResultRow.__post_init__``, so no construction path can produce a
  row that claims a Validator verdict without one.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path

COLUMNS: tuple[str, ...] = (
    "model", "algo", "makespan_s", "ratio", "compute_s", "passed",
    "run_at", "commit", "seed", "lower_bound_s", "validator_status", "validator_version",
    "notes",
)


def _is_real(v: object) -> bool:
    return type(v) is float and math.isfinite(v)  # not numpy floats, not bool, not int


def _clean_text(name: str, v: object) -> str:
    if not isinstance(v, str) or any(ord(ch) < 32 and ch != "\t" for ch in v):
        raise ValueError(f"{name} must be a string without line breaks or control characters")
    return v


@dataclass(frozen=True, slots=True)
class ResultRow:
    model: str
    algo: str
    makespan_s: float
    ratio: float | None
    compute_s: float
    passed: bool | None
    run_at: str
    commit: str
    seed: int | None
    lower_bound_s: float | None
    validator_status: str
    validator_version: str
    notes: str

    def __post_init__(self) -> None:
        for name in ("model", "algo", "run_at", "commit", "validator_status",
                     "validator_version", "notes"):
            _clean_text(name, getattr(self, name))
        if not self.model or not self.algo:
            raise ValueError("model and algo must be non-empty")
        if not (_is_real(self.makespan_s) and self.makespan_s > 0.0):
            raise ValueError(f"makespan_s must be a finite float > 0, got {self.makespan_s!r}")
        if not (_is_real(self.compute_s) and self.compute_s >= 0.0):
            raise ValueError(f"compute_s must be a finite float >= 0, got {self.compute_s!r}")
        if self.lower_bound_s is not None and not (
                _is_real(self.lower_bound_s) and self.lower_bound_s > 0.0):
            raise ValueError(f"lower_bound_s must be a finite float > 0, got "
                             f"{self.lower_bound_s!r}")
        if (self.ratio is None) != (self.lower_bound_s is None):
            raise ValueError("ratio and lower_bound_s are both set or both empty")
        if self.ratio is not None and not (
                _is_real(self.ratio)
                and math.isclose(self.ratio, self.makespan_s / self.lower_bound_s, rel_tol=1e-12)):
            raise ValueError("ratio must equal makespan_s / lower_bound_s")
        if self.seed is not None and type(self.seed) is not int:
            raise ValueError(f"seed must be an int or empty, got {self.seed!r}")
        if self.validator_status not in ("", "PASS", "FAIL"):
            raise ValueError(f"validator_status {self.validator_status!r}: only PASS/FAIL "
                             "come from summary.json (C-19)")
        ran = self.validator_status != ""
        if (self.passed is None) == ran or (
                ran and self.passed != (self.validator_status == "PASS")):
            raise ValueError("passed must be empty if the Validator was not run, otherwise "
                             "exactly (validator_status == 'PASS')")
        if ran != (self.validator_version != ""):
            raise ValueError("validator_version is set exactly when the Validator was run")


if tuple(f.name for f in fields(ResultRow)) != COLUMNS:
    raise RuntimeError("ResultRow fields and COLUMNS are out of sync")


def _read_summary(path: Path) -> tuple[str, str, float]:
    summary = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError(f"{path}: summary.json must be an object")
    status, version = summary.get("status"), summary.get("validator_version")
    if status not in ("PASS", "FAIL"):
        raise ValueError(f"{path}: status {status!r} is not PASS/FAIL (an error.json or another "
                         "file is not a validation result; policy: DECISIONS.md C-19)")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{path}: validator_version missing")
    schedule = summary.get("schedule")
    makespan = schedule.get("makespan_s") if isinstance(schedule, dict) else None
    if isinstance(makespan, bool) or not isinstance(makespan, (int, float)):
        raise ValueError(f"{path}: schedule.makespan_s missing or not a number")
    return status, version, float(makespan)


def _verify_binding(summary_path: Path, trajectory_path: Path) -> None:
    """The summary must be the Validator's verdict on exactly this trajectory.csv (C-19)."""
    summary_path = Path(summary_path)
    if summary_path.name != "summary.json":
        raise ValueError(f"{summary_path}: the file must be named summary.json")
    inputs = summary_path.with_name("validation_inputs.json")
    if not inputs.is_file():
        raise ValueError(f"{inputs} is missing: cannot tell which trajectory this verdict is for")
    try:
        want = json.loads(inputs.read_text(encoding="utf-8"))["inputs"]["trajectory.csv"]["sha256"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{inputs}: no inputs['trajectory.csv']['sha256'] ({exc!r})") from exc
    got = hashlib.sha256(Path(trajectory_path).read_bytes()).hexdigest()
    if not isinstance(want, str) or got != want.lower():
        raise ValueError(f"{summary_path} was not produced for {trajectory_path}: trajectory "
                         f"sha256 {got} != recorded {want!r}")


def make_row(model: str, algo: str, *, compute_s: float, seed: int | None, commit: str,
             trajectory_path: Path, lower_bound_s: float | None = None,
             summary_path: Path | None = None, makespan_s: float | None = None,
             notes: str = "", run_at: str | None = None) -> ResultRow:
    """Build a row. Validator-derived fields come only from ``summary_path``'s summary.json.

    ``trajectory_path`` is the trajectory.csv this run produced (it must exist). If a
    ``summary_path`` is given, that summary must belong to exactly this file (sha256).
    """
    if not Path(trajectory_path).is_file():
        raise ValueError(f"trajectory_path {trajectory_path} is not a file")
    status, version, value = "", "", None
    if summary_path is not None:
        _verify_binding(summary_path, trajectory_path)
        status, version, value = _read_summary(summary_path)
        if makespan_s is not None and not math.isclose(value, float(makespan_s), rel_tol=1e-9):
            raise ValueError(f"makespan_s {makespan_s!r} differs from summary.json's {value!r}")
    elif makespan_s is not None:
        value = float(makespan_s)
    if value is None:
        raise ValueError("no makespan: pass makespan_s or a summary.json that records one")
    lb = None if lower_bound_s is None else float(lower_bound_s)
    return ResultRow(
        model=model, algo=algo, makespan_s=float(value),
        ratio=None if lb is None or not lb > 0.0 else float(value) / lb,
        compute_s=float(compute_s),
        passed=(status == "PASS") if summary_path is not None else None,
        run_at=run_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        commit=commit, seed=seed, lower_bound_s=lb, validator_status=status,
        validator_version=version, notes=notes,
    )


def _cell(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _line(cells: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(cells)
    return buf.getvalue()


HEADER_LINE = _line(list(COLUMNS))


def append_result(path: Path, row: ResultRow) -> None:
    """Append one row (header first if the file is new or empty). Never rewrites old rows."""
    path = Path(path)
    line = _line([_cell(getattr(row, c)) for c in COLUMNS])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as fh:
            head = fh.readline().decode("utf-8")
            fh.seek(-1, 2)
            last = fh.read(1)
        if head != HEADER_LINE:
            why = (" (CRLF or BOM detected: keep the file LF, UTF-8 without BOM)"
                   if head.startswith("﻿") or head.endswith("\r\n") else "")
            raise ValueError(f"{path}: header differs from the results schema{why}; "
                             "refusing to append")
        if last != b"\n":
            raise ValueError(f"{path}: last row is incomplete (no final newline); "
                             "refusing to append")
        payload = line
    else:
        payload = HEADER_LINE + line
    with path.open("ab") as fh:  # one write call, binary: no newline translation on Windows
        fh.write(payload.encode("utf-8"))


def _bool(cell: str) -> bool:
    if cell not in ("True", "False"):
        raise ValueError(f"passed cell {cell!r} is not True/False/empty")
    return cell == "True"


def _opt(cell: str, conv):
    return None if cell == "" else conv(cell)


def read_results(path: Path) -> list[ResultRow]:
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None or tuple(header) != COLUMNS:
            raise ValueError(f"{path}: header differs from the results schema")
        rows = []
        for no, c in enumerate(reader, start=2):
            if len(c) != len(COLUMNS):
                raise ValueError(f"{path}: line {no} has {len(c)} cells, need {len(COLUMNS)}")
            rows.append(ResultRow(
                model=c[0], algo=c[1], makespan_s=float(c[2]), ratio=_opt(c[3], float),
                compute_s=float(c[4]), passed=_opt(c[5], _bool),
                run_at=c[6], commit=c[7], seed=_opt(c[8], int), lower_bound_s=_opt(c[9], float),
                validator_status=c[10], validator_version=c[11], notes=c[12]))
        return rows
