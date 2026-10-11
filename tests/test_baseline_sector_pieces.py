"""Baseline part 1 (docs/specs/baseline.md, C-46): Cell, sectors, pieces.

T-B01 (Cell part), T-B02, T-B03, T-B15, T-B18, T-B19, T-B20 and the M6 reference values of
``docs/measurements/design_inputs_3stage.md`` section 10. Synthetic cases use the model-01 config
fixture (read-only); the six-model tests read the Validator repo's models (read-only).
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest
from waam_validator.config.loader import load_config

from waam import geometry as geo
from waam.pieces import PieceError, passes_to_tasks, split_at_reach, split_at_sectors
from waam.sector import delta_max, owner_robot, phi_max, sector_bounds
from waam.strategy import Cell, Task
from _baseline_support import FIXTURE_CONFIG, MODELS, SLOW, _pass, fake_cfg, load_model


@pytest.fixture(scope="module")
def cfg():
    return load_config(FIXTURE_CONFIG)


@pytest.fixture(scope="module")
def cell(cfg):
    return Cell.from_config(cfg)




def test_cell_reads_everything_from_config(cfg):
    c = Cell.from_config(cfg)
    robots = sorted(cfg.robots, key=lambda r: r.id)
    assert c.robot_ids == tuple(r.id for r in robots)
    assert c.n_robots == len(robots)
    np.testing.assert_array_equal(c.base_xy, [r.base_xyz_mm[:2] for r in robots])
    np.testing.assert_array_equal(c.home_xyz, [r.home_xyz_mm for r in robots])
    np.testing.assert_array_equal(c.origin_xy, cfg.workspace.center_xy_mm)
    assert c.timing.deposition_speed_mm_s == cfg.process.deposition_speed_mm_s
    assert c.timing.arc_on_s == cfg.process.arc_on_time_s
    assert c.lift_dz_mm == 2.0 * cfg.process.layer_height_mm
    # a different config gives a different cell (nothing is a constant)
    other = fake_cfg(cfg, [10.0, 100.0, 200.0, 300.0], dist=1000.0, reach=1200.0, origin=(5.0, -7.0))
    oc = Cell.from_config(other)
    assert oc.n_robots == 4 and oc.robot_ids == (1, 2, 3, 4)
    np.testing.assert_allclose(oc.origin_xy, (5.0, -7.0))
    np.testing.assert_allclose(oc.geometry.reach_mm, 1200.0)
    np.testing.assert_allclose(np.hypot(*(oc.base_xy - oc.origin_xy).T), 1000.0)
    proc = cfg.process.model_copy(update={"deposition_speed_mm_s": 5.0, "arc_on_time_s": 3.0})
    changed = SimpleNamespace(**{**vars(other), "process": proc})
    cc = Cell.from_config(changed)
    assert cc.timing.deposition_speed_mm_s == 5.0 and cc.timing.arc_on_s == 3.0


def test_cell_sorts_robots_by_id(cfg):
    shuffled = SimpleNamespace(**{**vars(fake_cfg(cfg, [0.0, 120.0, 240.0])),
                                  "robots": tuple(reversed(fake_cfg(cfg, [0.0, 120.0, 240.0]).robots))})
    assert Cell.from_config(shuffled).robot_ids == (1, 2, 3)


# ---------------------------------------------------------------- T-B18, T-B15


def test_sector_bounds_are_bisectors_of_neighbor_directions(cell):
    spec = sector_bounds(cell)
    deg = np.sort(np.mod(np.degrees(spec.boundary_angles()), 360.0))
    np.testing.assert_allclose(deg, [0.0, 120.0, 240.0], atol=1e-4)  # public config, 120 deg apart
    np.testing.assert_allclose(np.degrees(spec.half_lo), 60.0, atol=1e-4)
    np.testing.assert_allclose(np.degrees(spec.half_hi), 60.0, atol=1e-4)
    # each base direction lies in its own sector
    for i, rid in enumerate(cell.robot_ids):
        p = cell.origin_xy + 300.0 * (cell.base_xy[i] - cell.origin_xy) / 1400.0
        assert owner_robot(spec, p[None, :])[0] == rid


def test_sector_bounds_asymmetric_bases_are_bisectors(cfg):
    c = Cell.from_config(fake_cfg(cfg, [0.0, 90.0, 270.0]))
    spec = sector_bounds(c)
    deg = np.sort(np.mod(np.degrees(spec.boundary_angles()), 360.0))
    np.testing.assert_allclose(deg, [45.0, 180.0, 315.0], atol=1e-9)
    # robot 2 (90 deg) owns [45, 180); robot 3 (270 deg) owns [180, 315); robot 1 owns [315, 45)
    # (points exactly on a boundary ray are avoided: cos/sin rounding decides such ties)
    ang = np.radians([44.999, 45.001, 90.0, 179.999, 180.001, 314.999, 315.001, 359.0, 10.0])
    pts = 100.0 * np.stack([np.cos(ang), np.sin(ang)], axis=1)
    assert owner_robot(spec, pts).tolist() == [1, 2, 2, 2, 3, 3, 1, 1, 1]


@pytest.mark.parametrize("bases", [[0.0, 180.0], [0.0, 90.0, 180.0, 270.0], [30.0, 50.0, 200.0, 220.0, 300.0]])
def test_sector_functions_read_robot_count_from_config(cfg, bases):
    c = Cell.from_config(fake_cfg(cfg, bases))
    spec = sector_bounds(c)
    assert spec.n == len(bases) == c.n_robots
    assert len(spec.boundary_angles()) == len(bases)
    assert set(owner_robot(spec, 100.0 * np.stack([np.cos(np.radians(bases)),
                                                   np.sin(np.radians(bases))], axis=1)).tolist()) \
        == set(range(1, len(bases) + 1))
    # the sectors tile the plane: every direction has exactly one owner among the robots
    ang = np.radians(np.arange(0.0, 360.0, 0.5))
    own = owner_robot(spec, 50.0 * np.stack([np.cos(ang), np.sin(ang)], axis=1))
    assert set(own.tolist()) == set(c.robot_ids)
    assert len(phi_max(c, 100.0)) == len(bases)


def test_single_robot_has_no_boundary(cfg):
    c = Cell.from_config(fake_cfg(cfg, [77.0]))
    spec = sector_bounds(c)
    assert len(spec.boundary_angles()) == 0
    assert owner_robot(spec, np.random.default_rng(0).uniform(-50, 50, (20, 2))).tolist() == [1] * 20
    res = split_at_sectors(passes_to_tasks([_pass([(-30, -5), (30, 5), (-30, 5)], reach={1})], c), c, spec)
    assert len(res.tasks) == 1 and res.cut_tasks == 0 and res.extra_pieces == 0


def test_delta_rotates_all_boundaries(cell):
    a = sector_bounds(cell).boundary_angles()
    b = sector_bounds(cell, math.radians(13.0)).boundary_angles()
    np.testing.assert_allclose(b - a, math.radians(13.0))


def test_phi_max_and_delta_max_guarantee_reach(cell):
    """C-43: within |delta| <= delta_max every point of radius <= r_max reaches its owner; beyond, not."""
    r_max = 600.0
    dmax = delta_max(cell, sector_bounds(cell), r_max)
    assert dmax > 0.0
    rng = np.random.default_rng(3)
    rad = r_max * np.sqrt(rng.uniform(0, 1, 40000))
    ang = rng.uniform(0, 2 * math.pi, 40000)
    pts = np.stack([rad * np.cos(ang), rad * np.sin(ang)], axis=1)
    for sign in (+1, -1):
        spec = sector_bounds(cell, sign * dmax * 0.999)
        own = owner_robot(spec, pts)
        ok = np.array([geo.in_reach(cell.geometry, int(o), p) for o, p in zip(own, pts)])
        assert ok.all()
    # tightness: a bit past delta_max some point of radius r_max is out of its owner's reach
    spec = sector_bounds(cell, dmax + math.radians(2.0))
    ang = np.radians(np.arange(0, 360, 0.25))
    ring = r_max * np.stack([np.cos(ang), np.sin(ang)], axis=1)
    own = owner_robot(spec, ring)
    bad = [not geo.in_reach(cell.geometry, int(o), p) for o, p in zip(own, ring)]
    assert any(bad)


# ---------------------------------------------------------------- T-B19


def _ring(radius, n, start_deg):
    a = np.radians(start_deg + np.linspace(0.0, 360.0, n + 1))
    pts = radius * np.stack([np.cos(a), np.sin(a)], axis=1)
    pts[-1] = pts[0]
    return pts


def test_sector_split_counts_and_length_conservation(cell):
    spec = sector_bounds(cell)
    ring = _ring(50.0, 360, 30.0)  # starts inside a sector, crosses all three boundary rays
    task = passes_to_tasks([_pass(ring, kind="contour", reach={1, 2, 3})], cell)
    res = split_at_sectors(task, cell, spec)
    assert len(res.tasks) == 3  # 4 runs, first and last in one sector are merged (U-10)
    assert res.cut_tasks == 1 and res.extra_pieces == 2 and res.fallback_pieces == 0
    assert math.isclose(sum(t.length for t in res.tasks), task[0].length, rel_tol=1e-12)
    assert sorted(t.owner for t in res.tasks) == [1, 2, 3]
    assert [t.piece_index for t in res.tasks] == [0, 1, 2]
    # every piece lies in its owner's sector
    for t in res.tasks:
        mid = np.array(t.vertices)
        mid = (mid[:-1] + mid[1:]) / 2.0
        assert (owner_robot(spec, mid) == t.owner).all()


def test_sector_split_open_polyline_crossing_one_boundary(cell):
    spec = sector_bounds(cell)
    # boundary ray at 0 deg (positive x axis): a vertical line x = 10 crosses it at (10, 0)
    task = passes_to_tasks([_pass([(10, -5), (10, 5)], reach={1, 2, 3})], cell)
    res = split_at_sectors(task, cell, spec)
    assert len(res.tasks) == 2 and res.cut_tasks == 1
    assert [t.length for t in res.tasks] == pytest.approx([5.0, 5.0], abs=1e-9)
    assert res.tasks[0].vertices[-1] == res.tasks[1].vertices[0]
    assert res.tasks[0].vertices[0] == (10.0, -5.0) and res.tasks[1].vertices[-1] == (10.0, 5.0)
    assert res.tasks[0].owner != res.tasks[1].owner


def test_sector_split_boundary_is_half_open_and_zero_length_parts_dropped(cell):
    spec = sector_bounds(cell)
    on_boundary = passes_to_tasks([_pass([(10, 0), (10, 5)], reach={1, 2, 3})], cell)
    res = split_at_sectors(on_boundary, cell, spec)
    assert len(res.tasks) == 1 and res.tasks[0].length == pytest.approx(5.0)
    assert res.tasks[0].owner == int(owner_robot(spec, np.array([[10.0, 2.5]]))[0])
    # a vertex on the ray: two segments, the cut coincides with the vertex -> no zero-length piece
    two = passes_to_tasks([_pass([(10, -5), (10, 0), (10, 5)], reach={1, 2, 3})], cell)
    res = split_at_sectors(two, cell, spec)
    assert len(res.tasks) == 2 and all(t.length > 0 for t in res.tasks)
    assert sum(t.length for t in res.tasks) == pytest.approx(10.0)


def test_sector_split_is_deterministic(cell):
    spec = sector_bounds(cell, math.radians(7.0))
    tasks = passes_to_tasks([_pass(_ring(60.0, 120, 11.0), reach={1, 2, 3})], cell)
    a = split_at_sectors(tasks, cell, spec)
    b = split_at_sectors(tasks, cell, spec)
    assert [t.vertices for t in a.tasks] == [t.vertices for t in b.tasks]
    assert [t.owner for t in a.tasks] == [t.owner for t in b.tasks]


# ---------------------------------------------------------------- T-B02, T-B03


def test_piece_reachable_set_is_vertex_intersection(cell):
    spec = sector_bounds(cell, math.radians(20.0))
    passes = [_pass(_ring(80.0, 200, 5.0), reach={1, 2, 3}), _pass([(-300, 0), (400, 0)], layer=1),
              _pass([(0, 0), (-600, 50)], layer=2, reach={1})]
    tasks = split_at_reach(passes, cell)
    for t in tasks:
        pts = np.array(t.vertices)
        expect = frozenset(rid for rid in cell.robot_ids if geo.in_reach(cell.geometry, rid, pts).all())
        assert t.reachable == expect and expect
    for t in split_at_sectors(tasks, cell, spec).tasks:
        pts = np.array(t.vertices)
        expect = frozenset(rid for rid in cell.robot_ids if geo.in_reach(cell.geometry, rid, pts).all())
        assert t.reachable == expect


def test_empty_reach_pass_is_split_at_reach_boundary(cell):
    # along y = 0: robot 1 reaches x <= ~100, robots 2 and 3 reach x >= ~-183: nobody reaches all
    q = _pass([(-300, 0), (400, 0)], reach=frozenset())
    tasks = split_at_reach([q], cell)
    assert len(tasks) == 2
    assert tasks[0].reachable == {1} and tasks[1].reachable == {2, 3}
    cut = tasks[0].vertices[-1]
    assert tasks[1].vertices[0] == cut
    assert abs(cut[0] - (-1400.0 + 1500.0)) < 1e-4 and cut[1] == 0.0
    assert geo.in_reach(cell.geometry, 1, np.array(cut))  # the cut point is inside the Validator rule
    assert sum(t.length for t in tasks) == pytest.approx(700.0, abs=1e-9)
    assert [t.pass_index for t in tasks] == [0, 0] and [t.piece_index for t in tasks] == [0, 1]
    assert tasks[0].vertices[0] == (-300.0, 0.0) and tasks[1].vertices[-1] == (400.0, 0.0)


def test_nonempty_reach_pass_is_not_split(cell):
    q = _pass([(-50, 0), (50, 0), (50, 60)], reach={1, 2, 3})
    tasks = split_at_reach([q], cell)
    assert len(tasks) == 1 and tasks[0].vertices == q.vertices and tasks[0].reachable == {1, 2, 3}


def test_split_at_reach_keeps_intermediate_vertices_and_order(cell):
    pts = [(-300, 0), (-100, 40), (90, 10), (110, 0), (250, -30), (400, 0)]
    tasks = split_at_reach([_pass(pts)], cell)
    assert len(tasks) >= 2
    seq = [tasks[0].vertices[0]]
    for t in tasks:
        assert t.vertices[0] == seq[-1]
        seq.extend(t.vertices[1:])
    original = {tuple(map(float, p)) for p in pts}
    assert original <= set(seq)  # every original vertex survives, exactly
    assert sum(t.length for t in tasks) == pytest.approx(
        sum(math.dist(a, b) for a, b in zip(pts[:-1], pts[1:])), abs=1e-9)
    for t in tasks:
        assert t.reachable


def test_split_at_reach_raises_for_unreachable_point(cell):
    with pytest.raises(PieceError):
        split_at_reach([_pass([(0, 0), (3000, 0)])], cell)


# M6 (design_inputs_3stage.md section 10, delta = 0): cut passes, extra pieces, total pieces, fallback
M6_REF = {
    "01": (34, 34, 418, 0), "02": (57, 57, 4362, 0), "03": (46, 49, 202, 0),
    "04": (194, 744, 1304, 0), "05": (1404, 3112, 4520, 0), "06": (58, 298, 400, 0),
}
def _model_param(name):
    return pytest.param(name, marks=pytest.mark.slow) if name in SLOW else name


@pytest.mark.parametrize("name", [_model_param(m) for m in MODELS])
def test_six_models_sector_split_matches_m6(name):
    c, res = load_model(name)
    cell6 = Cell.from_config(c)
    out = split_at_sectors(passes_to_tasks(res.passes, cell6), cell6, sector_bounds(cell6, 0.0))
    cut, extra, pieces, fb = M6_REF[name]
    assert (out.cut_tasks, out.extra_pieces, len(out.tasks), out.fallback_pieces) == (cut, extra, pieces, fb)
    assert math.isclose(sum(t.length for t in out.tasks), sum(q.length for q in res.passes), rel_tol=1e-9)


@pytest.mark.parametrize("name", [_model_param(m) for m in ["01", "03", "06", "02", "04", "05"]])
def test_public_config_sector_fallback_is_never_triggered(name):
    c, res = load_model(name)
    cell6 = Cell.from_config(c)
    tasks = passes_to_tasks(res.passes, cell6)
    base = sector_bounds(cell6)
    r_max = float(np.max(np.hypot(*(np.vstack([np.asarray(q.vertices, float) for q in res.passes])
                                    - cell6.origin_xy).T)))
    k = int(math.floor(math.degrees(delta_max(cell6, base, r_max)) / 2.0 + 1e-9))
    for j in range(-k, k + 1):
        out = split_at_sectors(tasks, cell6, sector_bounds(cell6, math.radians(2.0 * j)))
        assert out.fallback_pieces == 0, f"delta = {2 * j} deg"


@pytest.mark.parametrize("name", [_model_param(m) for m in MODELS])
def test_split_at_reach_gives_pieces_every_robot_set_nonempty(name):
    c, res = load_model(name)
    cell6 = Cell.from_config(c)
    tasks = split_at_reach(res.passes, cell6)
    assert all(t.reachable for t in tasks)
    assert math.isclose(sum(t.length for t in tasks), sum(q.length for q in res.passes), rel_tol=1e-9)
    empty = sum(1 for q in res.passes if not q.reachable_robots)
    assert len(tasks) >= len(res.passes) and (empty > 0 or len(tasks) == len(res.passes))


def test_task_is_a_frozen_value():
    t = Task(0, 1.0, "hatch", ((0.0, 0.0), (1.0, 0.0)), 1.0, 0, 0, frozenset({1}))
    with pytest.raises(AttributeError):
        t.owner = 2  # type: ignore[misc]
    assert t.owner is None
