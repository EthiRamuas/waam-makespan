"""Schedulers of the baseline (docs/specs/baseline.md B4-B9, B14, B15, B20-B22, section 5-4).

``SerialHandoverScheduler`` runs strategy S (one robot at a time on the part), ``EventScheduler``
runs strategy P (sector robots in parallel, event based). Both fill the clock with
``timing.build_chain``, commit every segment through ``append_checked`` (prevalidate's
``try_append`` plus a check that robots whose timeline ended earlier hold their last position),
keep the layer synchronisation (C-23) and close every timeline before the result is returned.
Nothing here depends on a model or on a number of robots except that prevalidate and ``Segment``
accept robot ids 1..3 (checked up front).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from .assign import Assignment
from .prevalidate import (Code, PrevalidateRules, Timeline, Verdict, check_all, check_hold,
                          check_pair, close_timeline, new_timelines, quantize_f32, try_append)
from .segment import Mode, Segment
from .strategy import Cell, Task
from .timing import Step, build_chain

Xyz = tuple[float, float, float]
_COLLISION = (Code.ARM_ENVELOPE, Code.TCP_RADIUS)
_SUPPORTED_IDS = tuple(tl.robot_id for tl in new_timelines())  # what prevalidate/Segment accept


class ScheduleError(Exception):
    """A strategy could not produce a prevalidated schedule (it is marked failed, B15, B22)."""

    def __init__(self, strategy: str, reason: str, verdict: Verdict | None = None,
                 notes: dict | None = None) -> None:
        super().__init__(f"strategy {strategy}: {reason}" + (f" ({verdict.code.name} at t={verdict.t})"
                                                               if verdict is not None else ""))
        self.strategy = strategy
        self.reason = reason
        self.verdict = verdict
        self.notes = notes or {}


@dataclass(slots=True)
class ScheduleResult:
    chains: dict[int, list[Segment]]
    timelines: tuple[Timeline, Timeline, Timeline]
    makespan_s: float
    notes: dict = field(default_factory=dict)


def append_checked(rules: PrevalidateRules, timelines: tuple[Timeline, Timeline, Timeline],
                   seg: Segment) -> Verdict:
    """``try_append`` plus the hold check of section 5-4: ``try_append`` calls ``check_pair`` without
    ``hold_open``, so a robot whose open timeline ended before ``seg`` is not checked at its last
    position. Here every such robot is checked as holding that position over ``seg``'s span; a
    failure removes ``seg`` again (``Timeline.pop_last``)."""
    v = try_append(rules, timelines, seg)
    if not v.ok:
        return v
    tl = timelines[seg.robot_id - 1]
    for other in timelines:
        if other.robot_id == seg.robot_id or other.closed or other.n_segments == 0:
            continue
        if other.end_time < seg.end_time_s:
            h = check_pair(rules, tl, other, seg.start_time_s, seg.end_time_s, hold_open=True)
            if not h.ok:
                tl.pop_last()
                return h
    return v


def _shift(segs: Sequence[Segment], t0: float) -> list[Segment]:
    """Move a chain built from t = 0 to start at ``t0`` (neighbouring segments keep sharing values)."""
    return [Segment(s.robot_id, s.mode, t0 + s.start_time_s, t0 + s.end_time_s,
                    s.start_xyz_mm, s.end_xyz_mm) for s in segs]


def _same_f32(a, b) -> bool:
    return bool(np.array_equal(quantize_f32(a), quantize_f32(b)))


class _Run:
    """Mutable state shared by both schedulers: chains, timelines, positions, clocks, counters."""

    def __init__(self, strategy: str, cell: Cell, rules: PrevalidateRules,
                 standby: dict[int, tuple[float, float]]) -> None:
        if tuple(cell.robot_ids) != _SUPPORTED_IDS:
            raise ScheduleError(strategy, f"chains need robot ids {_SUPPORTED_IDS}, got {cell.robot_ids}")
        self.strategy = strategy
        self.cell = cell
        self.rules = rules
        self.standby = standby
        self.tl = new_timelines()
        self.chains: dict[int, list[Segment]] = {rid: [] for rid in cell.robot_ids}
        self.pos: dict[int, Xyz] = {rid: tuple(float(c) for c in cell.home_xyz[i])
                                    for i, rid in enumerate(cell.robot_ids)}
        self.end: dict[int, float] = dict.fromkeys(cell.robot_ids, 0.0)
        self.notes: Counter = Counter()
        self.dz = cell.lift_dz_mm

    # -- committing -----------------------------------------------------------------------
    def _commit(self, rid: int, segs: Sequence[Segment]) -> Verdict:
        done = 0
        for s in segs:
            v = append_checked(self.rules, self.tl, s)
            if not v.ok:
                for _ in range(done):
                    self.tl[rid - 1].pop_last()
                return v
            done += 1
        for s in segs:
            self.chains[rid].append(s)
        self.pos[rid] = segs[-1].end_xyz_mm
        self.end[rid] = segs[-1].end_time_s
        return Verdict(True, Code.OK)

    def steps(self, rid: int, steps: Sequence[Step]) -> Verdict:
        steps = [s for s in steps]
        if not steps:
            return Verdict(True, Code.OK)
        try:
            segs = build_chain(rid, self.pos[rid], steps, self.cell.timing)
        except ValueError:  # every travel had zero (float32) length: nothing to do
            if all(s.kind == "travel" for s in steps):
                return Verdict(True, Code.OK)
            raise
        return self._commit(rid, _shift(segs, self.end[rid]))

    def wait_until(self, rid: int, t: float) -> Verdict:
        if not t > self.end[rid]:
            return Verdict(True, Code.OK)
        seg = Segment(rid, Mode.W, self.end[rid], t, self.pos[rid], self.pos[rid])
        return self._commit(rid, [seg])

    # -- motion rules ---------------------------------------------------------------------
    def transit(self, rid: int, target: Xyz) -> list[Step]:
        """B4 / probe P6: lift, horizontal, descend; nothing if the target is the current point.
        The very first move of a robot that has not moved yet is the probe D6 diagonal."""
        x, y, z = self.pos[rid]
        x0, y0, z0 = target
        if _same_f32((x, y, z), target):
            return []
        if not self.chains[rid]:
            return [Step("travel", ((x0, y0, z0 + self.dz),)), Step("travel", ((x0, y0, z0),))]
        zl = max(z, z0) + self.dz
        return [Step("travel", ((x, y, zl),)), Step("travel", ((x0, y0, zl),)),
                Step("travel", ((x0, y0, z0),))]

    def at_standby(self, rid: int) -> bool:
        sx, sy = self.standby[rid]
        return _same_f32((self.pos[rid][0], self.pos[rid][1], 0.0), (sx, sy, 0.0))

    def retreat_steps(self, rid: int, z_ref: float) -> list[Step]:
        sx, sy = self.standby[rid]
        x, y, z = self.pos[rid]
        if self.at_standby(rid):
            return []
        if not self.chains[rid]:  # still at home: one diagonal move
            return [Step("travel", ((sx, sy, z_ref + self.dz),))]
        return [Step("travel", ((x, y, z + self.dz),)), Step("travel", ((sx, sy, z + self.dz),))]

    def retreat(self, rid: int, z_ref: float) -> Verdict:
        self.notes["retreats"] += 1
        return self.steps(rid, self.retreat_steps(rid, z_ref))

    def hold_ok(self, rid: int) -> bool:
        x, y, _ = self.pos[rid]
        return check_hold(self.rules, self.tl, rid, (x, y), self.end[rid]).ok

    def piece_steps(self, rid: int, task: Task) -> list[Step]:
        v = [(float(x), float(y)) for x, y in task.vertices]
        if v[0] != v[-1]:  # U-19: an open piece starts at the end nearer to the robot
            px, py, _ = self.pos[rid]
            if math.hypot(v[-1][0] - px, v[-1][1] - py) < math.hypot(v[0][0] - px, v[0][1] - py):
                v = v[::-1]
        pts = tuple((x, y, task.z) for x, y in v)
        return self.transit(rid, pts[0]) + [Step("pass", pts)]

    def piece(self, rid: int, task: Task) -> Verdict:
        return self.steps(rid, self.piece_steps(rid, task))

    # -- finishing ------------------------------------------------------------------------
    def finish(self, worked: Sequence[int], t_end: float, park) -> ScheduleResult:
        """Pad the working robots to ``t_end``; park the robots that never worked (B9 (a));
        close every timeline; the whole schedule must pass ``check_all``."""
        for rid in worked:
            v = self.wait_until(rid, t_end)
            if not v.ok:
                raise ScheduleError(self.strategy, "padding wait collides", v, dict(self.notes))
        for rid in self.cell.robot_ids:
            if rid in worked:
                continue
            for cand in park(rid):
                seg = Segment(rid, Mode.W, 0.0, t_end, cand, cand)
                v = append_checked(self.rules, self.tl, seg)
                if v.ok:
                    self.chains[rid].append(seg)
                    self.pos[rid], self.end[rid] = cand, t_end
                    break
            else:
                raise ScheduleError(self.strategy, f"robot {rid}: no safe parking candidate",
                                    None, dict(self.notes))
        for rid in self.cell.robot_ids:
            v = close_timeline(self.rules, self.tl, rid)
            if not v.ok:
                raise ScheduleError(self.strategy, f"robot {rid}: close_timeline failed", v,
                                    dict(self.notes))
        rep = check_all(self.rules, self.tl)
        if not rep.ok:
            raise ScheduleError(self.strategy, "check_all failed", rep.verdict, dict(self.notes))
        makespan = max(self.end.values())
        notes = {"strategy": self.strategy, **{k: int(v) for k, v in self.notes.items()}}
        return ScheduleResult(self.chains, self.tl, makespan, notes)


def _park_fn(cell: Cell):
    from .standby import park_candidates

    return lambda rid: park_candidates(cell, rid)


# ---------------------------------------------------------------------------- S


class SerialHandoverScheduler:
    """Strategy S (B13-B15): one robot at a time on the part."""

    name = "S"

    def __init__(self, rules: PrevalidateRules, standby: dict[int, tuple[float, float]]) -> None:
        self.rules = rules
        self.standby = standby

    def schedule(self, assignment: Assignment, cell: Cell) -> ScheduleResult:
        runs = assignment.runs
        if not runs:
            raise ScheduleError(self.name, "nothing to schedule")
        st = _Run(self.name, cell, self.rules, self.standby)
        worked = sorted({r.robot for r in runs})
        first, z0 = runs[0].robot, runs[0].tasks[0].z
        for rid in worked:  # B5: everybody who will work later waits at the standby position
            if rid != first:
                v = st.steps(rid, [Step("travel", ((*st.standby[rid], z0 + st.dz),))])
                if not v.ok:
                    raise ScheduleError(self.name, f"robot {rid}: move to standby collides", v,
                                        dict(st.notes))
        prev: int | None = None
        for run in runs:
            rid = run.robot
            if prev is not None and prev != rid:  # B14: the next robot enters after the last one is at standby
                v = st.retreat(prev, run.tasks[0].z)
                if not v.ok:
                    raise ScheduleError(self.name, "retreat collides", v, dict(st.notes))
                st.notes["handovers"] += 1
                v = st.wait_until(rid, st.end[prev])
                if not v.ok:
                    raise ScheduleError(self.name, "waiting for the handover collides", v, dict(st.notes))
            for task in run.tasks:
                v = st.piece(rid, task)
                if not v.ok:
                    raise ScheduleError(self.name, "piece rejected by prevalidate", v, dict(st.notes))
            prev = rid
        t_end = max(st.end.values())
        return st.finish(worked, t_end, _park_fn(cell))


# ---------------------------------------------------------------------------- P


class EventScheduler:
    """Strategy P (B19-B22, C-44): the earliest available robot proposes its next piece; a rejected
    proposal sends it back (B8) and it waits for the next other robot to finish something."""

    name = "P"

    def __init__(self, rules: PrevalidateRules, standby: dict[int, tuple[float, float]]) -> None:
        self.rules = rules
        self.standby = standby

    def schedule(self, assignment: Assignment, cell: Cell) -> ScheduleResult:
        st = _Run(self.name, cell, self.rules, self.standby)
        worked = sorted(rid for rid, ts in assignment.items() if ts)
        if not worked:
            raise ScheduleError(self.name, "nothing to schedule")
        max_fail = cell.n_robots - 1  # B22: retries per piece
        layers = sorted({t.layer for ts in assignment.values() for t in ts})
        for layer in layers:
            todo = {rid: [t for t in assignment[rid] if t.layer == layer] for rid in worked}
            z_layer = next(t.z for q in todo.values() for t in q)
            for rid in worked:  # B5: robots with nothing to do yet leave home for their standby position
                if not st.chains[rid] and not todo[rid]:
                    v = st.steps(rid, [Step("travel", ((*st.standby[rid], z_layer + st.dz),))])
                    if not v.ok:
                        raise ScheduleError(self.name, f"robot {rid}: move to standby collides", v,
                                            dict(st.notes))
            fails: Counter = Counter()
            budget = 20 * sum(len(q) for q in todo.values()) + 100
            while any(todo.values()):
                budget -= 1
                if budget < 0:
                    raise ScheduleError(self.name, "no progress (iteration limit)", None, dict(st.notes))
                rid = min((q for q in worked if todo[q]), key=lambda q: (st.end[q], q))
                task = todo[rid][0]
                key = (task.pass_index, task.piece_index)
                v = st.piece(rid, task)
                if v.ok:
                    todo[rid].pop(0)
                    if not todo[rid] and not st.at_standby(rid) and not st.hold_ok(rid):
                        v = st.retreat(rid, task.z)  # B8 at the end of the robot's queue
                        if not v.ok:
                            raise ScheduleError(self.name, "retreat collides", v, dict(st.notes))
                    continue
                if v.code not in _COLLISION:
                    raise ScheduleError(self.name, "piece rejected by prevalidate", v, dict(st.notes))
                st.notes["failed_proposals"] += 1
                fails[(rid, key)] += 1
                if fails[(rid, key)] > max_fail:
                    st.notes["deadlocks"] += 1
                    raise ScheduleError(self.name, "deadlock: too many rejected proposals", v,
                                        dict(st.notes))
                if not st.at_standby(rid) and not st.hold_ok(rid):  # C-44 / B8
                    v2 = st.retreat(rid, task.z)
                    if not v2.ok:
                        st.notes["deadlocks"] += 1
                        raise ScheduleError(self.name, "deadlock: the retreat collides", v2,
                                            dict(st.notes))
                later = [st.end[q] for q in worked if q != rid and todo[q] and st.end[q] > st.end[rid]]
                if not later:
                    st.notes["deadlocks"] += 1
                    raise ScheduleError(self.name, "deadlock: no other robot to wait for", v,
                                        dict(st.notes))
                v3 = st.wait_until(rid, min(later))
                if not v3.ok:
                    st.notes["deadlocks"] += 1
                    raise ScheduleError(self.name, "deadlock: the wait collides", v3, dict(st.notes))
            t_layer = max(st.end[q] for q in worked)  # B6, B21
            for rid in worked:
                v = st.wait_until(rid, t_layer)
                if not v.ok:
                    raise ScheduleError(self.name, "waiting at the layer boundary collides", v,
                                        dict(st.notes))
        t_end = max(st.end[q] for q in worked)
        return st.finish(worked, t_end, _park_fn(cell))
