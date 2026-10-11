"""geometry.reachable_mask for any number of bases (baseline spec B12, T-B29)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from waam_validator.config.loader import load_config

from waam import geometry as geo
from _baseline_support import FIXTURE_CONFIG


@pytest.fixture(scope="module")
def cfg():
    return load_config(FIXTURE_CONFIG)




def _geometry(bases, reach=1500.0):
    n = len(bases)
    return geo.CellGeometry(
        base_xy=np.array(bases, float), reach_mm=np.full(n, reach), tcp_radius_mm=np.full(n, 100.0),
        arm_radius_mm=np.full(n, 100.0), arm_clearance_mm=50.0, touching_is_collision=True,
        check_arm_envelope=True, check_tcp_radius=True, eps_mm=1e-6,
        ws_center_xy=np.zeros(2), ws_radius_mm=700.0, bead_width_mm=8.0)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_geometry_reachable_mask_generalized_to_n_robots(n):
    bases = [(1400.0 * math.cos(2 * math.pi * k / n), 1400.0 * math.sin(2 * math.pi * k / n))
             for k in range(n)]
    g = _geometry(bases)
    rng = np.random.default_rng(0)
    pts = rng.uniform(-1800, 1800, size=(200, 2))
    mask = geo.reachable_mask(g, pts)
    assert mask.shape == (200, n)
    for i in range(n):
        np.testing.assert_array_equal(mask[:, i], geo.in_reach(g, i + 1, pts))
    assert geo.reachable_mask(g, pts[0]).shape == (n,)
    assert geo.reachable_mask(g, np.empty((0, 2))).shape == (0, n)


def test_geometry_reachable_mask_three_robots_unchanged(cfg):
    g = geo.CellGeometry.from_config(cfg)
    pts = np.random.default_rng(1).uniform(-900, 900, size=(100, 2))
    old = np.stack([geo.in_reach(g, rid, pts) for rid in (1, 2, 3)], axis=1)
    np.testing.assert_array_equal(geo.reachable_mask(g, pts), old)
