"""Baseline part 1: standby positions (B7, hull method) and parking candidates (B9 (a)).

T-B07 and the M7' reference values of ``docs/measurements/design_inputs_3stage.md`` section 13.
"""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import LineString
from waam_validator.config.loader import load_config

from waam import geometry as geo
from waam.standby import PARK_LAMBDAS, arm_hulls, park_candidates, standby_positions, standby_rho
from waam.strategy import Cell
from _baseline_support import FIXTURE_CONFIG, MODELS, SLOW, _pass, fake_cfg, load_model


@pytest.fixture(scope="module")
def cfg():
    return load_config(FIXTURE_CONFIG)


@pytest.fixture(scope="module")
def cell(cfg):
    return Cell.from_config(cfg)




def _arm_need(cell, i, j, buf):
    g = cell.geometry
    return float(g.arm_radius_mm[i] + g.arm_radius_mm[j] + g.arm_clearance_mm + buf)


def _vertex_points(passes):
    return np.unique(np.round(np.vstack([np.asarray(q.vertices, float) for q in passes]), 3), axis=0)


def _check_standby(cell, passes, rhos):
    from waam.prevalidate import float32_buffer_mm

    g = cell.geometry
    buf = float32_buffer_mm(g)
    hulls = arm_hulls(cell, passes)
    pts = _vertex_points(passes)
    for i, rid in enumerate(cell.robot_ids):
        rho = rhos[rid]
        assert rho is not None
        rel = g.base_xy[i] - cell.origin_xy
        d = float(np.hypot(*rel))
        u = rel / d

        def clear(r):
            seg = LineString([tuple(g.base_xy[i]), tuple(cell.origin_xy + r * u)])
            return all(seg.distance(hulls[j]) >= _arm_need(cell, i, j, buf)
                       for j in range(cell.n_robots) if j != i)

        assert clear(rho)
        assert rho == 0 or not clear(rho - 1)  # minimal integer rho
        s = cell.origin_xy + rho * u
        for j in range(cell.n_robots):
            if j == i:
                continue
            kj = pts[geo.in_reach(g, cell.robot_ids[j], pts)]
            # consequences of the hull condition: no vertex configuration collides, arm gap is kept
            assert not geo.pair_collides(g, rid, s, cell.robot_ids[j], kj).any()
            gap = geo.seg_seg_dist(g.base_xy[i], s, g.base_xy[j], kj)
            assert (np.asarray(gap) >= _arm_need(cell, i, j, buf) - 1e-9).all()


def test_standby_position_is_collision_free_against_reachable_vertices(cell):
    c, res = load_model("06")
    cell6 = Cell.from_config(c)
    rhos = standby_rho(cell6, res.passes)
    assert all(v is not None for v in rhos.values())
    _check_standby(cell6, res.passes, rhos)
    pos = standby_positions(cell6, res.passes)
    for i, rid in enumerate(cell6.robot_ids):  # the position is on the ray origin -> base at distance rho
        rel = cell6.base_xy[i] - cell6.origin_xy
        np.testing.assert_allclose(np.hypot(*(np.array(pos[rid]) - cell6.origin_xy)), rhos[rid], atol=1e-9)
        cross = rel[0] * (pos[rid][1] - cell6.origin_xy[1]) - rel[1] * (pos[rid][0] - cell6.origin_xy[0])
        assert abs(cross) < 1e-6


def test_standby_is_at_least_the_vertex_based_standby_and_works_with_fake_cells(cfg):
    q = _pass([(-60, -40), (60, -40), (60, 40), (-60, 40), (-60, -40)])
    for bases in ([0.0, 120.0, 240.0], [0.0, 180.0], [0.0, 90.0, 180.0, 270.0]):
        c = Cell.from_config(fake_cfg(cfg, bases))
        rhos = standby_rho(c, [q])
        assert set(rhos) == set(c.robot_ids)
        _check_standby(c, [q], rhos)
    # more robots can only push a standby outward (a robot needs room against each other robot)
    r3 = standby_rho(Cell.from_config(fake_cfg(cfg, [0.0, 120.0, 240.0])), [q])
    r2 = standby_rho(Cell.from_config(fake_cfg(cfg, [0.0, 120.0])), [q])
    assert r2[1] <= r3[1]


def test_standby_falls_back_to_base_when_no_rho_qualifies(cfg):
    # a huge part reached by all robots: no point of the ray is clear of the others' arm hulls
    q = _pass([(-600, 0), (600, 0), (0, 600), (0, -600)])
    c = Cell.from_config(fake_cfg(cfg, [0.0, 120.0, 240.0], dist=800.0, reach=1500.0))
    rhos = standby_rho(c, [q])
    pos = standby_positions(c, [q])
    for i, rid in enumerate(c.robot_ids):
        if rhos[rid] is None:
            assert pos[rid] == (float(c.base_xy[i][0]), float(c.base_xy[i][1]))
    assert any(v is None for v in rhos.values())


def test_park_candidates_follow_probe_a2(cell):
    cands = park_candidates(cell, 2)
    assert len(cands) == len(PARK_LAMBDAS) == 5
    assert cands[0] == tuple(float(c) for c in cell.home_xyz[1])
    bx, by = cell.base_xy[1]
    assert cands[-1][:2] == pytest.approx((bx, by))
    assert all(c[2] == cell.home_xyz[1][2] for c in cands)


# M7' (section 13): rho_min per robot (hull method)
M7H_REF = {
    "01": (360, 360, 360), "02": (409, 391, 427), "03": (402, 396, 408),
    "04": (468, 447, 447), "05": (558, 559, 559), "06": (307, 359, 359),
}


def _model_param(name):
    return pytest.param(name, marks=pytest.mark.slow) if name in SLOW else name


@pytest.mark.parametrize("name", [_model_param(m) for m in MODELS])
def test_six_models_standby_matches_m7_prime(name):
    c, res = load_model(name)
    cell6 = Cell.from_config(c)
    rhos = standby_rho(cell6, res.passes)
    assert tuple(rhos[rid] for rid in cell6.robot_ids) == M7H_REF[name]
