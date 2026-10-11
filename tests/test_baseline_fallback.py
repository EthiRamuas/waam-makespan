"""Baseline part 1: B18' fallback (T-B30) and the B3 split-point rule (C-47, U-31)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from waam_validator.config.loader import load_config

from waam import geometry as geo
from waam.pieces import passes_to_tasks, split_at_reach, split_at_sectors
from waam.prevalidate import float32_buffer_mm
from waam.sector import angular_distance_to_sector, owner_robot, sector_arc, sector_bounds
from waam.strategy import Cell
from _baseline_support import FIXTURE_CONFIG, _pass, fake_cfg, load_model


@pytest.fixture(scope="module")
def cfg():
    return load_config(FIXTURE_CONFIG)


@pytest.fixture(scope="module")
def cell(cfg):
    return Cell.from_config(cfg)


def test_angular_distance_to_sector(cell):
    spec = sector_bounds(cell)
    i = cell.robot_ids.index(2)  # base direction 60 deg, sector [0, 120) deg
    lo, hi = sector_arc(spec, i)
    assert math.degrees(lo) % 360 == pytest.approx(0.0, abs=1e-4)
    assert math.degrees(hi) % 360 == pytest.approx(120.0, abs=1e-4)
    for deg, expect in [(60, 0.0), (1, 0.0), (130, 10.0), (-10, 10.0), (180, 60.0), (-90, 90.0)]:
        got = math.degrees(angular_distance_to_sector(spec, i, math.radians(deg)))
        assert got == pytest.approx(expect, abs=1e-4)


def test_fallback_hands_piece_to_the_robot_that_reaches_it(cfg):
    # two robots facing each other, 1000 mm from the origin, reach 1120
    c = Cell.from_config(fake_cfg(cfg, [0.0, 180.0], dist=1000.0, reach=1120.0))
    spec = sector_bounds(c, math.radians(30.0))  # boundaries at 120 and 300 deg: robot 1 owns 300..120
    piece = _pass([(-100, 440), (-100, 480)], reach={2})
    out = split_at_sectors(passes_to_tasks([piece], c), c, spec)
    assert len(out.tasks) == 1 and out.triggered == 1 and out.fallback_pieces == 1
    assert out.unresolved == () and out.tasks[0].owner == 2 and out.tasks[0].reachable == {2}
    assert int(owner_robot(spec, np.array([[-100.0, 460.0]]))[0]) == 1  # the sector owner could not reach it


def test_fallback_picks_nearest_sector_among_robots_that_reach(cfg):
    c = Cell.from_config(fake_cfg(cfg, [0.0, 90.0, 180.0, 270.0], dist=1000.0, reach=1150.0))
    spec = sector_bounds(c, math.radians(20.0))
    pts = [(-190, 150), (190, 150), (-190, -150), (190, -150), (0, 190), (0, -190), (80, 30), (-60, -120)]
    far = [_pass([(x, y), (x + 5, y + 5)], layer=k) for k, (x, y) in enumerate(pts)]
    out = split_at_sectors(passes_to_tasks(far, c), c, spec)
    assert out.unresolved == ()
    for t in out.tasks:
        pv = np.array(t.vertices)
        assert t.owner in t.reachable
        ang = math.atan2(pv[:, 1].mean(), pv[:, 0].mean())  # short pieces: the mean is the midpoint
        best = min(angular_distance_to_sector(spec, c.robot_ids.index(r), ang) for r in t.reachable)
        got = angular_distance_to_sector(spec, c.robot_ids.index(t.owner), ang)
        assert got == pytest.approx(best, abs=1e-9)


def test_fallback_actually_fires_in_the_nearest_sector_case(cfg):
    # robot 1 reaches only 700 mm, the others 1100 mm: pieces in robot 1's sector near the origin are out
    # of its reach; robot 2 (90 deg) reaches them, robot 4 (270 deg) does not
    c = Cell.from_config(fake_cfg(cfg, [0.0, 90.0, 180.0, 270.0], dist=1000.0,
                                  reach=[700.0, 1100.0, 1100.0, 1100.0]))
    spec = sector_bounds(c)
    piece = _pass([(200, 100), (204, 104)])
    out = split_at_sectors(passes_to_tasks([piece], c), c, spec)
    assert out.triggered == 1 and out.unresolved == ()
    assert out.tasks[0].reachable == {2}
    assert out.tasks[0].owner == 2  # nearest sector (90 deg, 26 deg away) among the robots that reach it


def test_fallback_ties_go_to_smaller_robot_id(cfg):
    # robot 1 (0 deg) reaches only 600 mm; a piece on its sector's axis is out of its reach, and the
    # sectors of robots 2 (120 deg) and 3 (240 deg) are symmetric to it: an exact tie
    c = Cell.from_config(fake_cfg(cfg, [0.0, 120.0, 240.0], dist=1000.0, reach=[600.0, 1500.0, 1500.0]))
    spec = sector_bounds(c)  # robot 1 owns [300, 60) deg
    piece = _pass([(700, -2), (700, 2)])  # on robot 1's axis, 300 mm from its base
    out = split_at_sectors(passes_to_tasks([piece], c), c, spec)
    t = out.tasks[0]
    assert geo.in_reach(c.geometry, 1, np.array(t.vertices)).all()  # robot 1 reaches it: no fallback here
    far_piece = _pass([(-200, -2), (-200, 2)])  # 1200 mm from robot 1: out of its 600 mm reach
    out = split_at_sectors(passes_to_tasks([far_piece], c), c, sector_bounds(c, math.radians(180.0)))
    assert out.triggered == 1
    t = out.tasks[0]
    assert not geo.in_reach(c.geometry, 1, np.array(t.vertices)).all()
    assert t.reachable == {2, 3}
    d2 = angular_distance_to_sector(sector_bounds(c, math.radians(180.0)), 1, math.pi)
    d3 = angular_distance_to_sector(sector_bounds(c, math.radians(180.0)), 2, math.pi)
    assert d2 == pytest.approx(d3, abs=1e-9)
    assert t.owner == 2  # smaller id wins the exact tie


def test_fallback_step2_splits_by_reach_and_step3_flags_unreachable(cfg):
    c = Cell.from_config(fake_cfg(cfg, [0.0, 180.0], dist=1000.0, reach=1120.0))
    spec = sector_bounds(c, math.radians(90.0))  # boundaries at 180 and 0 deg
    # a long polyline inside one sector that no robot reaches entirely -> split by reach (step 2)
    line = _pass([(-100, 150), (-100, 480), (100, 480), (100, 150)])
    out = split_at_sectors(passes_to_tasks([line], c), c, spec)
    assert out.unresolved == () and len(out.tasks) >= 2
    assert all(t.owner in t.reachable for t in out.tasks)
    assert sum(t.length for t in out.tasks) == pytest.approx(line.length, abs=1e-9)
    # step 3: a point nobody reaches
    bad = _pass([(0, 900), (10, 900)])
    out = split_at_sectors(passes_to_tasks([bad], c), c, spec)
    assert out.unresolved == (0,) and out.tasks[0].reachable == frozenset()


# ---------------------------------------------------------------- B3 split points (C-47, U-31)


def _cut_points_ok(name):
    c, res = load_model(name)
    cell6 = Cell.from_config(c)
    g = cell6.geometry
    buf = float32_buffer_mm(g)
    checked = 0
    orig = {i: {tuple(map(float, p)) for p in q.vertices} for i, q in enumerate(res.passes)}
    for t in split_at_reach(res.passes, cell6):
        if res.passes[t.pass_index].reachable_robots:
            continue
        for p in (t.vertices[0], t.vertices[-1]):
            if p in orig[t.pass_index]:
                continue
            q32 = np.array(p, dtype=np.float32).astype(np.float64)
            d = np.hypot(*(q32[None, :] - g.base_xy).T)
            assert (d <= g.reach_mm + g.eps_mm).any(), p  # the quantised cut point is reachable
            assert np.min(np.abs(d - (g.reach_mm - buf))) < 1e-4, p  # on the R - buf circle up to float32 rounding
            checked += 1
    return checked


def test_split_points_quantised_to_float32_stay_within_reach_04_pass0():
    c, res = load_model("04")
    cell6 = Cell.from_config(c)
    assert not res.passes[0].reachable_robots  # the regression case: failed at R + eps before
    tasks = [t for t in split_at_reach(res.passes, cell6) if t.pass_index == 0]
    assert len(tasks) == 4 and all(t.reachable for t in tasks)
    assert _cut_points_ok("04") > 0


@pytest.mark.slow
def test_split_points_quantised_to_float32_stay_within_reach_05():
    assert _cut_points_ok("05") > 0


@pytest.mark.parametrize("name,expect", [("04", (60, 650)), pytest.param("05", (1286, 3593), marks=pytest.mark.slow)])
def test_reach_split_counts_unchanged_by_split_point_rule(name, expect):
    c, res = load_model(name)
    tasks = split_at_reach(res.passes, Cell.from_config(c))
    # task 26a measurement with the R + eps/2 rule: empty-reach passes, tasks after the split
    assert (sum(1 for q in res.passes if not q.reachable_robots), len(tasks)) == expect
