"""Baseline part 2 (docs/specs/baseline.md): assignment, schedulers, portfolio.

T-B04, 05, 06, 08, 09, 10, 11, 13, 14, 17, 21, 22, 23, 24, 25, 26, 28 on model 06 (the one model where a
strategy passes prevalidate at the spec parameters, task 26b) and on small synthetic cases. T-B27
(six models) is NOT here: five of the six models have no strategy that passes prevalidate (see
docs/measurements/baseline_26b.md).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from waam_validator.config.loader import load_config

from waam import baseline as B
from waam import schedule as S
from waam.assign import Assignment, HandoverAssigner, SectorAssigner
from waam.baseline import BaselineError, Candidate, choose, run_baseline
from waam.prevalidate import PrevalidateRules
from waam.segment import Mode
from waam.slicing import slice_stl
from waam.standby import park_candidates, standby_positions
from waam.strategy import Cell, Task
from _baseline_support import FIXTURE_CONFIG, VALIDATOR_TESTS

W_06 = 6149.0  # M8: 47560 mm / 8 mm/s + 102 passes x 2 s
PROBE_06 = 6174.838943466003  # probe_06 run 1, docs/measurements/probe_06_run1.md


@pytest.fixture(scope="module")
def cfg():
    return load_config(FIXTURE_CONFIG)


@pytest.fixture(scope="module")
def cell(cfg):
    return Cell.from_config(cfg)


@pytest.fixture(scope="module")
def rules(cfg):
    return PrevalidateRules.from_config(cfg)


@pytest.fixture(scope="module")
def r06():
    c = load_config(VALIDATOR_TESTS / "06" / "config.yaml")
    stack = slice_stl(VALIDATOR_TESTS / "06" / "target.stl", c)
    return c, stack, run_baseline(stack, c)


def mk(layer, verts, reach, pi, owner=None):
    length = sum(math.dist(a, b) for a, b in zip(verts[:-1], verts[1:]))
    return Task(layer, 2.0 * layer + 1.0, "hatch", tuple(verts), length, pi, 0, frozenset(reach), owner)


# ---------------------------------------------------------------- assignment: T-B13, T-B21


def test_handover_processes_current_robot_pieces_first_then_hands_over(cell):
    tasks = [mk(0, [(0, 0), (10, 0)], {1}, 0), mk(0, [(0, 5), (10, 5)], {1, 2}, 1),
             mk(0, [(0, 9), (10, 9)], {2, 3}, 2), mk(0, [(0, 12), (10, 12)], {2}, 3),
             mk(1, [(0, 0), (10, 0)], {1, 2, 3}, 4), mk(1, [(0, 5), (10, 5)], {3}, 5)]
    a = HandoverAssigner().assign(tasks, cell)
    runs = [(r.robot, r.layer, [t.pass_index for t in r.tasks]) for r in a.runs]
    # layer 0: robot 1 first (most reachable length: pieces 0 and 1 = 20 vs robot 2: 1, 2, 3 = 30 -> robot 2)
    assert runs[0][0] == 2 and runs[0][2] == [1, 2, 3]  # robot 2 reaches the most remaining length
    assert runs[1] == (1, 0, [0])
    # layer 1: the last robot (1) continues with what it reaches, then the rest goes to robot 3
    assert runs[2] == (1, 1, [4]) and runs[3] == (3, 1, [5])
    assert sum(len(r.tasks) for r in a.runs) == len(tasks)
    assert {rid: [t.pass_index for t in ts] for rid, ts in a.items()} == {1: [0, 4], 2: [1, 2, 3], 3: [5]}


def test_handover_ties_go_to_smaller_id_and_handovers_are_bounded(cell):
    tasks = [mk(0, [(0, 0), (10, 0)], {1, 2, 3}, 0), mk(0, [(0, 5), (10, 5)], {1, 2, 3}, 1)]
    a = HandoverAssigner().assign(tasks, cell)
    assert [r.robot for r in a.runs] == [1]  # equal reach length: smaller id, and one robot does it all
    rng = np.random.default_rng(2)
    many = [mk(0, [(0, i), (10, i)], set(rng.choice([1, 2, 3], size=rng.integers(1, 4), replace=False).tolist()), i)
            for i in range(30)]
    runs = HandoverAssigner().assign(many, cell).runs
    assert len(runs) <= cell.n_robots  # at most (robots needed - 1) handovers in one layer


def test_sector_assignment_orders_pieces_outer_to_inner(cell):
    tasks = [mk(0, [(-20, 0), (-20, 4)], {1, 2, 3}, 0), mk(0, [(-90, 0), (-90, 4)], {1, 2, 3}, 1),
             mk(0, [(-50, 0), (-50, 4)], {1, 2, 3}, 2), mk(0, [(90, 40), (90, 44)], {1, 2, 3}, 3)]
    a = SectorAssigner().assign(tasks, cell)  # part centre = bounding box centre = (0, 22)
    assert [t.pass_index for t in a[1]] == [1, 2, 0]  # farthest from the part centre first (T-B21)
    assert all(t.owner == 1 for t in a[1])
    assert [t.pass_index for t in a[2]] == [3] and a[3] == []


# ---------------------------------------------------------------- the scheduler on model 06 (S)


def test_model06_strategy_s_passes_and_p_is_reported_as_failed(r06):
    _, _, r = r06
    assert r.strategy == "S"
    names = {c.name: c for c in r.candidates}
    assert names["S"].ok and not names["P"].ok
    assert "deadlock" in names["P"].reason and names["P"].notes["deadlocks"] == 1  # T-B23 (real case)
    assert names["P"].compute_s >= 0.0 and names["S"].compute_s > 0.0  # T-B25, T-B26 inputs


def test_model06_makespan_not_below_serial_work_bound(r06):
    _, _, r = r06
    assert r.makespan_s >= W_06  # T-B28: sum of D times + arc times, 06 allows only serial work
    assert r.makespan_s == pytest.approx(PROBE_06, abs=1e-6)  # robot 1 alone does what the probe did


def test_every_robot_starts_at_time_zero_and_robot_1_at_home(r06):
    c, _, r = r06
    cell6 = Cell.from_config(c)
    for rid, segs in r.chains.items():
        assert segs[0].start_time_s == 0.0
    assert r.chains[1][0].start_xyz_mm == tuple(float(v) for v in cell6.home_xyz[0])  # T-B05


def test_parked_robots_follow_probe_a2(r06):
    c, _, r = r06
    cell6 = Cell.from_config(c)
    for rid in (2, 3):  # robots that never worked: one W at a park candidate, until the makespan
        segs = r.chains[rid]
        assert len(segs) == 1 and segs[0].mode == Mode.W
        assert segs[0].end_time_s == r.makespan_s
        assert segs[0].start_xyz_mm == segs[0].end_xyz_mm in park_candidates(cell6, rid)  # T-B09 (a)


def test_all_timelines_closed_and_submittable_and_writer_accepts(r06, tmp_path):
    c, stack, r = r06
    assert all(tl.closed for tl in r.timelines)  # T-B10
    from waam.prevalidate import check_all, require_submittable
    assert check_all(r.rules, r.timelines).ok
    require_submittable(r.rules, r.timelines)
    r2 = run_baseline(stack, c, out_path=tmp_path / "trajectory.csv")
    assert (tmp_path / "trajectory.csv").exists() and r2.write_s is not None


def test_same_input_twice_gives_byte_identical_csv(r06, tmp_path):
    c, stack, _ = r06
    run_baseline(stack, c, out_path=tmp_path / "a.csv")
    run_baseline(stack, c, out_path=tmp_path / "b.csv")
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()  # T-B11


def test_layer_synchronization_invariant_on_model06(r06):
    c, _, r = r06
    h = c.process.layer_height_mm
    by_layer: dict[int, list[tuple[float, float]]] = {}
    for segs in r.chains.values():
        for s in segs:
            if s.mode == Mode.D:
                k = int(round((s.start_xyz_mm[2] - c.process.build_plane_z_mm) / h - 0.5))
                by_layer.setdefault(k, []).append((s.start_time_s, s.end_time_s))
    layers = sorted(by_layer)
    assert len(layers) > 10
    for a, b in zip(layers[:-1], layers[1:]):  # T-B06: layer k ends before layer k+1 starts
        assert max(e for _, e in by_layer[a]) <= min(s for s, _ in by_layer[b])


def test_transit_between_pieces_is_lift_horizontal_descend(r06):
    c, _, r = r06
    dz = 2.0 * c.process.layer_height_mm
    segs = r.chains[1]
    i = 0
    checked = 0
    while i < len(segs):
        if segs[i].mode == Mode.T:
            j = i
            while j < len(segs) and segs[j].mode == Mode.T:
                j += 1
            run = segs[i:j]
            if i > 0 and j < len(segs):  # a transit between two pieces
                assert len(run) == 3  # T-B04: vertical, horizontal, vertical
                zl = run[0].end_xyz_mm[2]
                assert zl == pytest.approx(max(run[0].start_xyz_mm[2], run[2].end_xyz_mm[2]) + dz)
                assert run[1].start_xyz_mm[2] == run[1].end_xyz_mm[2] == zl
                assert run[0].end_xyz_mm[:2] == run[0].start_xyz_mm[:2]
                checked += 1
            i = j
        else:
            i += 1
    assert checked > 10


# ---------------------------------------------------------------- synthetic S and P


def _standby(cell, tasks):
    return standby_positions(cell, tasks)


def test_serial_strategy_never_has_two_robots_on_part_and_idle_robot_waits_at_standby(cell, rules):
    tasks = [mk(0, [(-40, -10), (-40, 30)], {1}, 0), mk(0, [(40, -10), (40, 30)], {3}, 1),
             mk(1, [(40, 30), (40, -10)], {3}, 2), mk(1, [(-40, 30), (-40, -10)], {1}, 3)]
    st = _standby(cell, tasks)
    res = S.SerialHandoverScheduler(rules, st).schedule(HandoverAssigner().assign(tasks, cell), cell)
    assert res.notes["handovers"] == 2
    d_spans = {rid: [(s.start_time_s, s.end_time_s) for s in segs if s.mode == Mode.D]
               for rid, segs in res.chains.items()}
    allspans = [(a, b, rid) for rid, sp in d_spans.items() for a, b in sp]
    for i, (a0, a1, r0) in enumerate(allspans):  # T-B14
        for b0, b1, r1 in allspans[i + 1:]:
            if r0 != r1:
                assert a1 <= b0 or b1 <= a0
    # robot 3 (works second) waits at its standby position before its first piece; robot 2 never works
    first_d = next(s for s in res.chains[3] if s.mode == Mode.D)
    waits = [s for s in res.chains[3] if s.mode == Mode.W and s.end_time_s <= first_d.start_time_s
             and s.start_xyz_mm[:2] == pytest.approx(st[3], abs=1e-3) and s.end_xyz_mm == s.start_xyz_mm]
    assert waits  # T-B08
    assert len(res.chains[2]) == 1 and res.chains[2][0].mode == Mode.W  # T-B09 (a)


def test_serial_strategy_failure_is_reported_not_hidden(cell, rules, monkeypatch):
    tasks = [mk(0, [(-40, -10), (-40, 30)], {1}, 0)]
    st = _standby(cell, tasks)
    asg = HandoverAssigner().assign(tasks, cell)
    real = S.append_checked

    def failing(rl, tl, seg):
        v = real(rl, tl, seg)
        if seg.mode == Mode.D:
            tl[seg.robot_id - 1].pop_last()
            return S.Verdict(False, S.Code.ARM_ENVELOPE, seg.start_time_s, seg.robot_id, 2)
        return v

    monkeypatch.setattr(S, "append_checked", failing)
    with pytest.raises(S.ScheduleError) as exc:
        S.SerialHandoverScheduler(rules, st).schedule(asg, cell)
    assert exc.value.verdict.code == S.Code.ARM_ENVELOPE and exc.value.strategy == "S"  # T-B17


def test_append_checked_checks_the_hold_of_a_robot_whose_timeline_ended_earlier(cell, rules):
    """Section 5-4: try_append alone accepts a move into a robot that has stopped before it."""
    from waam.prevalidate import new_timelines, try_append
    from waam.segment import Segment

    def fresh():
        t = new_timelines()  # robot 2 holds (100, 100) during [0, 5] and has nothing committed after
        assert try_append(rules, t, Segment(2, Mode.W, 0.0, 5.0, (100.0, 100.0, 5.0), (100.0, 100.0, 5.0))).ok
        assert try_append(rules, t, Segment(3, Mode.W, 0.0, 6.0, (100.0, -250.0, 5.0), (100.0, -250.0, 5.0))).ok
        return t

    dist = math.dist((100.0, -250.0, 5.0), (110.0, 100.0, 5.0))
    move = Segment(3, Mode.T, 6.0, 6.0 + dist / 150.0, (100.0, -250.0, 5.0), (110.0, 100.0, 5.0))
    t = fresh()
    assert try_append(rules, t, move).ok  # robot 2's timeline ends at 5 < 6: the plain check sees nothing
    t = fresh()
    v = S.append_checked(rules, t, move)  # the hold check puts robot 2 at (100, 100) during the move
    assert not v.ok and v.code in (S.Code.ARM_ENVELOPE, S.Code.TCP_RADIUS)
    assert t[2].n_segments == 1  # and the move was removed again


def test_event_scheduler_runs_parallel_pieces_and_keeps_layer_synchronization(cell, rules):
    pt = [mk(0, [(-200, 0), (-200, 40)], {1, 2, 3}, 0, 1), mk(0, [(200, -100), (200, -60)], {1, 2, 3}, 1, 3),
          mk(0, [(-200, 40), (-160, 40)], {1, 2, 3}, 2, 1), mk(1, [(200, -60), (200, -100)], {1, 2, 3}, 3, 3),
          mk(1, [(-160, 40), (-200, 40)], {1, 2, 3}, 4, 1)]
    asg = Assignment({1: [pt[0], pt[2], pt[4]], 2: [], 3: [pt[1], pt[3]]})
    res = S.EventScheduler(rules, _standby(cell, pt)).schedule(asg, cell)
    d = [(s.start_xyz_mm[2], s.start_time_s, s.end_time_s, rid) for rid, segs in res.chains.items()
         for s in segs if s.mode == Mode.D]
    z0 = [x for x in d if x[0] == 1.0]
    z1 = [x for x in d if x[0] == 3.0]
    assert max(e for _, _, e, _ in z0) <= min(s for _, s, _, _ in z1)  # T-B06 for P
    assert {x[3] for x in z0} == {1, 3}
    overlap = any(a[1] < b[2] and b[1] < a[2] for a in z0 for b in z0 if a[3] == 1 and b[3] == 3)
    assert overlap  # robots 1 and 3 really work at the same time
    assert all(tl.closed for tl in res.timelines)


def test_event_scheduler_recovers_from_a_rejected_proposal(cell, rules):
    pt = [mk(0, [(-60, -20), (-60, 20)], {1, 2, 3}, 0, 1), mk(0, [(-240, 0), (-240, 40)], {1, 2, 3}, 1, 1),
          mk(0, [(60, -20), (60, 20)], {1, 2, 3}, 2, 3)]
    asg = Assignment({1: [pt[0], pt[1]], 2: [], 3: [pt[2]]})
    res = S.EventScheduler(rules, _standby(cell, pt)).schedule(asg, cell)
    assert res.notes["failed_proposals"] >= 1 and "deadlocks" not in res.notes  # T-B22
    from waam.prevalidate import check_all
    assert check_all(rules, res.timelines).ok


def test_event_scheduler_reports_deadlock(cell, rules):
    pt = [mk(0, [(-60, -10), (-60, 30)], {1, 2, 3}, 0, 1), mk(0, [(60, -10), (60, 30)], {1, 2, 3}, 1, 3),
          mk(0, [(-60, 30), (-30, 30)], {1, 2, 3}, 2, 1), mk(0, [(60, 30), (30, 30)], {1, 2, 3}, 3, 3)]
    asg = Assignment({1: [pt[0], pt[2]], 2: [], 3: [pt[1], pt[3]]})
    with pytest.raises(S.ScheduleError) as exc:
        S.EventScheduler(rules, _standby(cell, pt)).schedule(asg, cell)
    assert "deadlock" in exc.value.reason and exc.value.notes["deadlocks"] == 1  # T-B23


# ---------------------------------------------------------------- portfolio: T-B24, T-B25, T-B26


def _cand(name, ok, ms):
    return Candidate(name, ok, ms, "" if ok else "failed", {}, 0.1)


def test_portfolio_selects_smaller_makespan_ties_to_serial():
    assert choose([_cand("S", True, 10.0), _cand("P", True, 9.0)]).name == "P"
    assert choose([_cand("S", True, 9.0), _cand("P", True, 10.0)]).name == "S"
    assert choose([_cand("S", True, 9.0), _cand("P", True, 9.0)]).name == "S"  # tie -> S
    assert choose([_cand("P", True, 9.0), _cand("S", True, 9.0)]).name == "S"  # independent of order
    assert choose([_cand("S", False, None), _cand("P", True, 99.0)]).name == "P"
    with pytest.raises(BaselineError) as exc:
        choose([_cand("S", False, None), _cand("P", False, None)])
    assert set(exc.value.reasons) == {"S", "P"}


def test_portfolio_records_both_candidates_and_choice(r06):
    _, _, r = r06
    assert [c.name for c in r.candidates] == ["S", "P"]
    assert r.strategy == "S" and r.candidates[0].makespan_s == r.makespan_s
    assert r.candidates[1].reason  # the failure reason is kept (T-B25)


def test_compute_time_covers_toolpath_and_both_strategies(r06):
    _, _, r = r06
    assert r.compute_s >= r.toolpath_s + sum(c.compute_s for c in r.candidates)  # T-B26
    assert r.write_s is None
