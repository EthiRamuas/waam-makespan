"""Vectorised interval functions: must agree with the scalar reference and stay sound."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from waam_validator.config.loader import load_config

from waam import geometry as geo

JOB = Path(__file__).parent / "fixtures" / "sample_job"


@pytest.fixture(scope="module")
def g():
    return geo.CellGeometry.from_config(load_config(JOB / "config.yaml"))


@pytest.fixture(scope="module")
def gdense(g):
    # fatter arms / TCP circles so random intervals produce a healthy mix of hits and misses
    return replace(g, arm_radius_mm=np.array([120.0] * 3), arm_clearance_mm=50.0,
                   tcp_radius_mm=np.array([150.0] * 3))


def _random_intervals(rng, k, spread=500.0, stationary_frac=0.2):
    p = rng.uniform(-spread, spread, (k, 4, 2))
    still = rng.random(k) < stationary_frac
    p[still, 1] = p[still, 0]  # robot a stationary
    p[still, 3] = p[still, 2] if k else p[still, 3]  # robot b stationary too
    return p[:, 0], p[:, 1], p[:, 2], p[:, 3]


def test_margins_batch_matches_scalar(g):
    rng = np.random.default_rng(11)
    a0, a1, b0, b1 = _random_intervals(rng, 200)
    arm, tcp = geo.interval_margins_batch(g, 1, a0, a1, 2, b0, b1)
    assert arm.shape == tcp.shape == (200,)
    for i in range(200):
        r = geo.min_arm_margin_over_interval(g, 1, a0[i], a1[i], 2, b0[i], b1[i], 0.0, 1.0)
        assert arm[i] == pytest.approx(r.arm_margin, abs=1e-9)
        assert tcp[i] == pytest.approx(r.tcp_margin, abs=1e-9)


def test_margins_batch_long_moves_and_other_pair(g):
    rng = np.random.default_rng(12)
    a0, a1, b0, b1 = _random_intervals(rng, 40, spread=1500.0)
    arm, tcp = geo.interval_margins_batch(g, 2, a0, a1, 3, b0, b1, max_step_mm=7.0)
    for i in range(40):
        r = geo.min_arm_margin_over_interval(
            g, 2, a0[i], a1[i], 3, b0[i], b1[i], 0.0, 1.0, max_step_mm=7.0)
        assert arm[i] == pytest.approx(r.arm_margin, abs=1e-9)
        assert tcp[i] == pytest.approx(r.tcp_margin, abs=1e-9)


def test_margins_batch_broadcast_and_empty(g):
    rng = np.random.default_rng(13)
    a0, a1, _, _ = _random_intervals(rng, 7)
    arm, tcp = geo.interval_margins_batch(g, 1, a0, a1, 2, [300.0, 0.0], [300.0, 0.0])
    assert arm.shape == tcp.shape == (7,)
    one = geo.interval_margins_batch(g, 1, [0, 0], [10, 0], 2, [300, 0], [300, 0])
    assert one[0].shape == (1,)
    e = np.empty((0, 2))
    arm, tcp = geo.interval_margins_batch(g, 1, e, e, 2, e, e)
    assert arm.shape == tcp.shape == (0,)
    assert geo.intervals_collide(g, 1, e, e, 2, e, e).shape == (0,)
    assert geo.interval_clear_mask(g, 1, e, e, 2, e, e).shape == (0,)
    with pytest.raises(ValueError):
        geo.interval_margins_batch(g, 1, np.zeros((3, 3)), np.zeros((3, 3)), 2, S2, S2)
    with pytest.raises(ValueError):
        geo.interval_margins_batch(g, 1, np.zeros((3, 2)), np.zeros((3, 2)), 2,
                                   np.zeros((4, 2)), np.zeros((4, 2)))


S2 = np.zeros((2, 2))


def test_chunking_does_not_change_results(g, monkeypatch):
    rng = np.random.default_rng(14)
    a0, a1, b0, b1 = _random_intervals(rng, 150, spread=900.0)
    ref = geo.interval_margins_batch(g, 1, a0, a1, 2, b0, b1)
    monkeypatch.setattr(geo, "_CHUNK_SAMPLES", 300)  # force many chunks (some single-interval)
    got = geo.interval_margins_batch(g, 1, a0, a1, 2, b0, b1)
    np.testing.assert_allclose(got[0], ref[0], atol=1e-12)
    np.testing.assert_allclose(got[1], ref[1], atol=1e-12)


def test_collide_batch_matches_scalar_without_prefilter(gdense):
    rng = np.random.default_rng(15)
    a0, a1, b0, b1 = _random_intervals(rng, 300, spread=450.0)
    hit = geo.intervals_collide(gdense, 1, a0, a1, 2, b0, b1, prefilter=False)
    ref = np.array([
        geo.min_arm_margin_over_interval(gdense, 1, a0[i], a1[i], 2, b0[i], b1[i], 0.0, 1.0).collides
        for i in range(300)])
    np.testing.assert_array_equal(hit, ref)
    assert 20 < hit.sum() < 280  # the test exercises both outcomes


def test_prefilter_only_removes_hits_never_adds(gdense):
    rng = np.random.default_rng(16)
    a0, a1, b0, b1 = _random_intervals(rng, 400, spread=1200.0)
    full = geo.intervals_collide(gdense, 1, a0, a1, 2, b0, b1, prefilter=False)
    fast = geo.intervals_collide(gdense, 1, a0, a1, 2, b0, b1, prefilter=True)
    assert not np.any(fast & ~full)  # the boxes can only certify "clear"


def test_clear_mask_is_sound_against_dense_truth(gdense):
    rng = np.random.default_rng(17)
    a0, a1, b0, b1 = _random_intervals(rng, 300, spread=1200.0)
    buf = 0.3
    clear = geo.interval_clear_mask(gdense, 1, a0, a1, 2, b0, b1, buffer_mm=buf)
    gap = geo.interval_aabb_gap(gdense, 1, a0, a1, 2, b0, b1)
    u = np.linspace(0, 1, 2001)[:, None]
    for i in range(300):
        ta, tb = a0[i] + u * (a1[i] - a0[i]), b0[i] + u * (b1[i] - b0[i])
        d_arm = geo.seg_seg_dist(np.broadcast_to(gdense.base_xy[0], ta.shape), ta,
                                 np.broadcast_to(gdense.base_xy[1], tb.shape), tb)
        d_tcp = np.hypot(*(ta - tb).T)
        assert gap[i] <= d_arm.min() + 1e-9
        assert gap[i] <= d_tcp.min() + 1e-9
        if clear[i]:
            assert not geo.arm_collides(gdense, 1, ta, 2, tb).any()
            assert not geo.tcp_collides(gdense, 1, ta, 2, tb).any()
    assert 0 < clear.sum() < 300


def test_buffer_is_monotone_and_flags_respected(gdense):
    rng = np.random.default_rng(18)
    a0, a1, b0, b1 = _random_intervals(rng, 300, spread=450.0)
    h0 = geo.intervals_collide(gdense, 1, a0, a1, 2, b0, b1, buffer_mm=0.0)
    h1 = geo.intervals_collide(gdense, 1, a0, a1, 2, b0, b1, buffer_mm=5.0)
    assert not np.any(h0 & ~h1) and h1.sum() > h0.sum()
    none = replace(gdense, check_arm_envelope=False, check_tcp_radius=False)
    assert not geo.intervals_collide(none, 1, a0, a1, 2, b0, b1).any()
    assert geo.interval_clear_mask(none, 1, a0, a1, 2, b0, b1).all()
    tcp_only = replace(gdense, check_arm_envelope=False)
    arm_only = replace(gdense, check_tcp_radius=False)
    both = geo.intervals_collide(gdense, 1, a0, a1, 2, b0, b1)
    union = (geo.intervals_collide(tcp_only, 1, a0, a1, 2, b0, b1)
             | geo.intervals_collide(arm_only, 1, a0, a1, 2, b0, b1))
    np.testing.assert_array_equal(both, union)


def test_aabb_gap_overlap_is_zero_and_separated_positive(g):
    z = geo.interval_aabb_gap(g, 1, [0, 0], [0, 0], 2, [0, 0], [0, 0])
    assert z[0] == 0.0  # both hull boxes contain the shared point (0,0): touching boxes -> gap 0
    near = geo.interval_aabb_gap(g, 1, [500, 0], [600, 0], 2, [550, 0], [650, 0])
    assert near.shape == (1,) and near[0] >= 0
    far = geo.interval_aabb_gap(g, 1, [-1000, -600], [-1000, -600], 2, [1000, -600], [1000, -600])
    assert far[0] == pytest.approx(2000.0)
