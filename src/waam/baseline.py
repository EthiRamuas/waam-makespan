"""Baseline portfolio (docs/specs/baseline.md B23-B25, C-42): strategy S and strategy P both run,
the one with the smaller prevalidated makespan is chosen, ties go to S. The choice depends on the
two makespans only (no timing, no model number); every model gets the same rule.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import toolpath as tp
from .assign import AssignmentError, HandoverAssigner, SectorAssigner
from .pieces import PieceError, passes_to_tasks, split_at_reach
from .prevalidate import PrevalidateRules
from .schedule import EventScheduler, ScheduleError, ScheduleResult, SerialHandoverScheduler
from .segment import Segment
from .standby import standby_positions
from .strategy import Cell
from .writer import write_trajectory


class BaselineError(Exception):
    """Neither strategy produced a prevalidated schedule: no result is made up (B23)."""

    def __init__(self, reasons: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in reasons.items()))
        self.reasons = reasons


@dataclass(slots=True)
class Candidate:
    name: str
    ok: bool
    makespan_s: float | None
    reason: str
    notes: dict
    compute_s: float  # assignment + scheduling (+ pieces) of this strategy
    result: ScheduleResult | None = None


@dataclass(slots=True)
class BaselineResult:
    strategy: str
    chains: dict[int, list[Segment]]
    timelines: tuple
    makespan_s: float
    candidates: list[Candidate]
    rules: PrevalidateRules
    toolpath_s: float
    compute_s: float  # toolpath.generate (no cache) through selection (and the write, if requested)
    write_s: float | None = None
    notes: dict = field(default_factory=dict)


def _run_strategy(name, make_tasks, assigner, scheduler_cls, cell, rules, standby) -> Candidate:
    t0 = time.perf_counter()
    try:
        assignment = assigner.assign(make_tasks(), cell)
        res = scheduler_cls(rules, standby).schedule(assignment, cell)
    except ScheduleError as exc:
        return Candidate(name, False, None, str(exc), dict(exc.notes), time.perf_counter() - t0)
    except (AssignmentError, PieceError) as exc:
        return Candidate(name, False, None, f"{type(exc).__name__}: {exc}", {}, time.perf_counter() - t0)
    return Candidate(name, True, res.makespan_s, "", dict(res.notes), time.perf_counter() - t0, res)


def choose(cands: list[Candidate]) -> Candidate:
    """B23: the candidate with the smaller makespan; ties go to S; no candidate -> BaselineError."""
    ok = [c for c in cands if c.ok]
    if not ok:
        raise BaselineError({c.name: c.reason for c in cands})
    return min(ok, key=lambda c: (c.makespan_s, c.name != "S"))


def run_baseline(stack: Any, cfg: Any, *, params: tp.ToolpathParams | None = None,
                 delta: float | str = 0.0, out_path: str | Path | None = None) -> BaselineResult:
    """S and P, prevalidate, portfolio choice (ties: S). ``out_path`` writes the chosen schedule
    with ``write_trajectory`` (which re-checks ``require_submittable``) and counts it in compute_s."""
    t_all = time.perf_counter()
    cell = Cell.from_config(cfg, params)
    rules = PrevalidateRules.from_config(cfg)
    t0 = time.perf_counter()
    toolpath = tp.generate(stack, cfg, params, use_cache=False)
    toolpath_s = time.perf_counter() - t0
    standby = standby_positions(cell, toolpath.passes)
    cands = [
        _run_strategy("S", lambda: split_at_reach(toolpath.passes, cell), HandoverAssigner(),
                      SerialHandoverScheduler, cell, rules, standby),
        _run_strategy("P", lambda: passes_to_tasks(toolpath.passes, cell), SectorAssigner(delta),
                      EventScheduler, cell, rules, standby),
    ]
    best = choose(cands)
    res = best.result
    write_s = None
    if out_path is not None:
        t1 = time.perf_counter()
        write_trajectory(Path(out_path), res.chains, rules, res.timelines)
        write_s = time.perf_counter() - t1
    return BaselineResult(best.name, res.chains, res.timelines, res.makespan_s, cands, rules,
                          toolpath_s, time.perf_counter() - t_all, write_s,
                          {"standby": standby, **res.notes})
