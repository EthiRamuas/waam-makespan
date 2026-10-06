import csv
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from waam_validator.collision.geometry2d import check_arm_envelope_xy_batch
from waam_validator.config.loader import load_config

from waam import geometry as geo

JOB = Path(__file__).parent / "fixtures" / "sample_job"
MODEL01_CFG = Path(r"C:\Github\WAAM_Validator\tests\01\config.yaml")  # read-only reference


@pytest.fixture(scope="module")
def g():
    return geo.CellGeometry.from_config(load_config(JOB / "config.yaml"))


def _rows():
    with open(JOB / "trajectory.csv", newline="") as f:
        return [(int(r["robot_id"]), float(r["time_s"]), float(r["x_mm"]),
                 float(r["y_mm"]), float(r["z_mm"]), r["mode"]) for r in csv.DictReader(f)]


# --- fixture cases: expected values are Validator's summary.json (measured) ---

def test_reach_max_distance_robot1(g):
    margin = geo.reach_margin(g, 1, [40.0, 0.0])
    assert margin == pytest.approx(1299.3335184157092, abs=1e-9)
    assert g.reach_mm[0] - margin == pytest.approx(1200.6664815842908, abs=1e-9)
    assert geo.in_reach(g, 1, [40.0, 0.0])


def test_reach_robots_at_base(g):
    assert geo.reach_margin(g, 2, [1000.0, -600.0]) == pytest.approx(2500.0)
    assert geo.reach_margin(g, 3, [0.0, 1200.0]) == pytest.approx(2500.0)


def test_arm_centerline_at_t14(g):
    # robot 2 TCP sits on its base -> zero-length segment
    d = geo.seg_seg_dist(g.base_xy[0], [40.0, 0.0], g.base_xy[1], [1000.0, -600.0])
    assert d == pytest.approx(1132.0777358467924, abs=1e-9)
    assert geo.arm_margin(g, 1, [40.0, 0.0], 2, [1000.0, -600.0]) == pytest.approx(
        882.0777358467924, abs=1e-9)


def test_tcp_distance_and_required(g):
    assert not geo.tcp_collides(g, 1, [40.0, 0.0], 2, [1000.0, -600.0])
    assert geo._tcp_required(g, 1, 2) == 40.0
    # summary.json tcp_radius.minimum_distance_mm = 1132.0777358467924 (required 40.0)
    margin = geo._tcp_margin_n(g, 1, np.array([[40.0, 0.0]]), 2, np.array([[1000.0, -600.0]]))
    assert margin[0] + 40.0 == pytest.approx(1132.0777358467924, abs=1e-9)


def test_workspace_fixture_deposition(g):
    assert geo.deposition_in_workspace(g, [-40.0, 0.0], [40.0, 0.0])
    assert not geo.deposition_in_workspace(g, [-250.0, 0.0], [0.0, 0.0])


def test_dist3_speed_matches_validator_message():
    assert geo.dist3([-1000, -600, 100], [-40, 0, 2]) / 4.0 == pytest.approx(284.078, abs=5e-4)


def test_fixture_no_collision_over_all_intervals(g):
    rows = _rows()
    tr = {rid: [(t, np.array([x, y])) for r, t, x, y, _, _ in rows if r == rid] for rid in (1, 2, 3)}
    times = sorted({t for v in tr.values() for t, _ in v})

    def pos(rid, t):
        ts = [a for a, _ in tr[rid]]
        return np.array([np.interp(t, ts, [p[i] for _, p in tr[rid]]) for i in (0, 1)])

    worst_arm, worst_tcp = np.inf, np.inf
    for t0, t1 in zip(times, times[1:]):
        for a, b in ((1, 2), (1, 3), (2, 3)):
            r = geo.min_arm_margin_over_interval(
                g, a, pos(a, t0), pos(a, t1), b, pos(b, t0), pos(b, t1), t0, t1)
            assert not r.collides
            worst_arm, worst_tcp = min(worst_arm, r.arm_margin), min(worst_tcp, r.tcp_margin)
            assert not geo.pair_collides(g, a, pos(a, t1), b, pos(b, t1))
    # Measured (summary.json): min arm margin 882.0777358467924; min TCP distance
    # 1132.0777358467924 minus required 40. Ours are lower bounds: at or below the
    # truth and within the sampling slack.
    assert 882.0777358467924 - geo.INTERVAL_MAX_STEP_MM <= worst_arm <= 882.0777358467924 + 1e-9
    assert 1092.0777358467924 - geo.INTERVAL_MAX_STEP_MM <= worst_tcp <= 1092.0777358467924 + 1e-9


# --- synthetic boundary cases (expected values derived from formulas, not measured) ---

def test_seg_cross_is_zero():
    assert geo.seg_seg_dist([0, 0], [2, 2], [0, 2], [2, 0]) == 0.0


def test_seg_parallel_and_degenerate():
    assert geo.seg_seg_dist([0, 0], [4, 0], [0, 3], [4, 3]) == pytest.approx(3.0)
    assert geo.seg_seg_dist([0, 0], [4, 0], [2, 3], [2, 3]) == pytest.approx(3.0)
    assert geo.seg_seg_dist([0, 0], [0, 0], [3, 4], [3, 4]) == pytest.approx(5.0)


def test_seg_collinear_overlap_is_zero():
    assert geo.seg_seg_dist([0, 0], [4, 0], [2, 0], [6, 0]) == pytest.approx(0.0)


def test_seg_symmetry():
    rng = np.random.default_rng(0)
    p = rng.uniform(-100, 100, (200, 4, 2))
    ab = geo.seg_seg_dist(p[:, 0], p[:, 1], p[:, 2], p[:, 3])
    ba = geo.seg_seg_dist(p[:, 2], p[:, 3], p[:, 0], p[:, 1])
    np.testing.assert_allclose(ab, ba)


def test_far_apart_bases_do_not_collide(g):
    assert not geo.arm_collides(g, 1, g.base_xy[0], 3, g.base_xy[2])


def test_touching_flag_changes_result(g):
    # tcp_a at base_a, tcp_b at base_b -> distance = |base_a - base_b|; shrink via radius
    d = float(np.linalg.norm(g.base_xy[0] - g.base_xy[1]))
    arm = np.array([(d - g.arm_clearance_mm) / 2] * 3)
    gt = replace(g, arm_radius_mm=arm, touching_is_collision=True)
    gf = replace(g, arm_radius_mm=arm, touching_is_collision=False)
    assert geo.arm_collides(gt, 1, g.base_xy[0], 2, g.base_xy[1])  # margin == 0 -> collision
    assert not geo.arm_collides(gf, 1, g.base_xy[0], 2, g.base_xy[1])


def test_reach_boundary(g):
    R = g.reach_mm[0]
    b = g.base_xy[0]
    assert geo.in_reach(g, 1, b + [R, 0])
    assert geo.in_reach(g, 1, b + [R + g.eps_mm * 0.5, 0])
    assert not geo.in_reach(g, 1, b + [R + g.eps_mm * 10, 0])


def test_batch_matches_scalar(g):
    rng = np.random.default_rng(1)
    a = rng.uniform(-300, 300, (50, 2))
    b = rng.uniform(-300, 300, (50, 2))
    batch = geo.arm_margin(g, 1, a, 2, b)
    scalar = [geo.arm_margin(g, 1, a[i], 2, b[i]) for i in range(50)]
    np.testing.assert_allclose(batch, scalar)
    assert geo.reachable_mask(g, a).shape == (50, 3)


def test_interval_finds_mid_interval_minimum(g):
    # TCPs cross paths mid-interval: the bound must be below the endpoint margin and
    # sandwiched between (dense truth - slack) and the dense truth.
    p0a, p1a, p0b, p1b = [-200, 0], [200, 0], [200, 0], [-200, 0]
    r = geo.min_arm_margin_over_interval(g, 1, p0a, p1a, 2, p0b, p1b, 0.0, 10.0)
    assert r.arm_margin < geo.arm_margin(g, 1, p0a, 2, p0b)
    u = np.linspace(0, 1, 40001)[:, None]
    truth = float(np.min(geo.arm_margin(
        g, 1, np.array(p0a) + u * (np.array(p1a) - p0a),
        2, np.array(p0b) + u * (np.array(p1b) - p0b))))
    assert truth - geo.INTERVAL_MAX_STEP_MM <= r.arm_margin <= truth + 1e-9


# --- cross-validation against the Validator's own implementation (import only) ---

def test_crossvalidate_with_validator(g):
    rng = np.random.default_rng(42)
    n = 5000
    ta = rng.uniform(-1500, 1500, (n, 2))
    tb = rng.uniform(-1500, 1500, (n, 2))
    ref = check_arm_envelope_xy_batch(
        g.base_xy[0], ta, g.arm_radius_mm[0], g.base_xy[1], tb, g.arm_radius_mm[1],
        g.arm_clearance_mm, g.eps_mm, g.touching_is_collision)
    ours = geo.seg_seg_dist(g.base_xy[0], ta, g.base_xy[1], tb)
    np.testing.assert_allclose(ours, ref.centerline_distance_mm, atol=1e-9)
    np.testing.assert_array_equal(geo.arm_collides(g, 1, ta, 2, tb), ref.collision)


def test_crossvalidate_touching_false(g):
    gf = replace(g, touching_is_collision=False)
    rng = np.random.default_rng(43)
    ta = rng.uniform(-1500, 1500, (3000, 2))
    tb = rng.uniform(-1500, 1500, (3000, 2))
    ref = check_arm_envelope_xy_batch(
        gf.base_xy[0], ta, gf.arm_radius_mm[0], gf.base_xy[1], tb, gf.arm_radius_mm[1],
        gf.arm_clearance_mm, gf.eps_mm, False)
    np.testing.assert_array_equal(geo.arm_collides(gf, 1, ta, 2, tb), ref.collision)


# --- review fixes: shapes, bounds, TCP circle, golden counterexample ---

S = np.array([0.0, 0.0])
B = np.array([[0.0, 0.0], [-1000.0, 0.0], [300.0, 0.0]])


@pytest.mark.parametrize("fn", ["arm_margin", "arm_collides", "tcp_collides", "pair_collides"])
def test_mixed_single_batch_shapes(g, fn):
    f = getattr(geo, fn)
    expected = np.array([f(g, 1, S, 2, b) for b in B])
    for a, b in ((S, B), (B, S), (B, B[::-1]), (B[:1], B), (B, B[:1])):
        assert np.shape(f(g, 1, a, 2, b)) == (3,)
    np.testing.assert_array_equal(f(g, 1, S, 2, B), expected)
    assert np.shape(f(g, 1, S, 2, S)) == ()  # all single -> scalar
    assert np.shape(f(g, 1, B[:1], 2, S)) == (1,)  # (1,2) batch stays an array


def test_mixed_shapes_workspace_and_seg(g):
    expected = np.array([geo.deposition_in_workspace(g, S, b) for b in B])
    np.testing.assert_array_equal(geo.deposition_in_workspace(g, S, B), expected)
    np.testing.assert_array_equal(geo.deposition_in_workspace(g, B, S), expected)
    assert geo.seg_seg_dist(g.base_xy[0], B, g.base_xy[1], S).shape == (3,)
    assert geo.reachable_mask(g, S).shape == (3,)
    assert geo.reachable_mask(g, B).shape == (3, 3)


def test_mismatched_batch_lengths_raise(g):
    with pytest.raises(ValueError):
        geo.arm_margin(g, 1, B, 2, B[:2])
    with pytest.raises(ValueError):
        geo.deposition_in_workspace(g, B, B[:2])


@pytest.mark.parametrize(
    "bad", [[0.0, 0.0, 1.0], [[0.0, 0.0, 1.0], [300.0, 0.0, 1.0]], 5.0, [[[0.0, 0.0]]]])
def test_non_xy_shapes_raise(g, bad):
    for call in (
        lambda: geo.reach_margin(g, 1, bad),
        lambda: geo.in_reach(g, 1, bad),
        lambda: geo.arm_margin(g, 1, bad, 2, S),
        lambda: geo.tcp_collides(g, 1, S, 2, bad),
        lambda: geo.pair_collides(g, 1, bad, 2, bad),
        lambda: geo.deposition_in_workspace(g, bad, S),
        lambda: geo.seg_seg_dist(bad, S, S, S),
        lambda: geo.reachable_mask(g, bad),
    ):
        with pytest.raises(ValueError):
            call()


def test_empty_batches_return_empty_arrays(g):
    e = np.empty((0, 2))
    for out in (
        geo.reach_margin(g, 1, e), geo.in_reach(g, 1, e),
        geo.arm_margin(g, 1, e, 2, e), geo.arm_collides(g, 1, e, 2, e),
        geo.tcp_collides(g, 1, e, 2, e), geo.pair_collides(g, 1, e, 2, e),
        geo.arm_margin(g, 1, e, 2, S), geo.deposition_in_workspace(g, e, e),
        geo.seg_seg_dist(e, e, e, e),
    ):
        assert out.shape == (0,)
    assert geo.reachable_mask(g, e).shape == (0, 3)


def test_interval_input_validation(g):
    with pytest.raises(ValueError):  # t1 < t0
        geo.min_arm_margin_over_interval(g, 1, [0, 0], [10, 0], 2, [300, 0], [300, 0], 5.0, 1.0)
    with pytest.raises(ValueError):  # xyz endpoints
        geo.min_arm_margin_over_interval(
            g, 1, [0, 0, 1], [10, 0, 1], 2, [300, 0], [300, 0], 0.0, 1.0)
    with pytest.raises(ValueError):  # batch endpoints
        geo.min_arm_margin_over_interval(g, 1, B[:2], B[:2], 2, B[1:], B[1:], 0.0, 1.0)
    geo.min_arm_margin_over_interval(  # t1 == t0 is allowed
        g, 1, [0, 0], [10, 0], 2, [300, 0], [300, 0], 1.0, 1.0)


def test_interval_bound_is_conservative_property(g):
    rng = np.random.default_rng(7)
    u = np.linspace(0, 1, 20001)[:, None]
    for _ in range(40):
        p = rng.uniform(-400, 400, (4, 2))
        r = geo.min_arm_margin_over_interval(g, 1, p[0], p[1], 2, p[2], p[3], 0.0, 3.0)
        ta, tb = p[0] + u * (p[1] - p[0]), p[2] + u * (p[3] - p[2])
        truth_arm = float(np.min(geo.arm_margin(g, 1, ta, 2, tb)))
        truth_tcp = float(np.min(np.hypot(*(ta - tb).T) - 40.0))
        assert r.arm_margin <= truth_arm + 1e-9
        assert r.tcp_margin <= truth_tcp + 1e-9
        assert r.arm_margin >= truth_arm - geo.INTERVAL_MAX_STEP_MM - 1e-6
        assert r.tcp_margin >= truth_tcp - geo.INTERVAL_MAX_STEP_MM - 1e-6


def test_interval_stationary_uses_one_sample(g):
    r = geo.min_arm_margin_over_interval(g, 1, [0, 0], [0, 0], 2, [300, 0], [300, 0], 0.0, 1000.0)
    assert r.arm_margin == pytest.approx(geo.arm_margin(g, 1, [0, 0], 2, [300, 0]))


def test_interval_includes_tcp_circle_and_flags(g):
    # Arm capsules small & apart, TCP circles huge -> only the TCP circle collides.
    gt = replace(g, arm_radius_mm=np.array([1.0, 1.0, 1.0]), arm_clearance_mm=0.0,
                 tcp_radius_mm=np.array([700.0, 700.0, 700.0]))
    a, b = [-100.0, -600.0], [100.0, -600.0]
    r = geo.min_arm_margin_over_interval(gt, 1, a, a, 2, b, b, 0.0, 1.0)
    assert r.arm_margin > 0 and r.tcp_margin < 0 and r.collides
    assert geo.pair_collides(gt, 1, a, 2, b)
    off = replace(gt, check_tcp_radius=False)
    assert not geo.min_arm_margin_over_interval(off, 1, a, a, 2, b, b, 0.0, 1.0).collides
    assert not geo.pair_collides(off, 1, a, 2, b)


@pytest.mark.skipif(not MODEL01_CFG.exists(), reason="Validator tests/01 config not available")
def test_golden_interval_counterexample_vs_validator():
    """Reviewer's counterexample: a sampled-only check (n=5) says safe, the Validator says FAIL.

    R1 TCP moves (-249.999,-4)->(-249.999,8) in 0.23 s; R2 TCP fixed at (0,0); R3 parked at its
    base. The continuous minimum arm margin is 249.999 - 250 = -0.001 mm.
    """
    from waam_validator.collision.simulator import run_collision_analysis
    from waam_validator.constants import MODE_T, MODE_W
    from waam_validator.models import RobotTrajectory, TrajectorySet

    cfg = load_config(MODEL01_CFG)
    gm = geo.CellGeometry.from_config(cfg)
    x, dt = -249.999, 0.23
    p0, p1 = np.array([x, -4.0]), np.array([x, 8.0])
    b3 = gm.base_xy[2]

    def traj(rid, a, b, mode):
        return RobotTrajectory(
            robot_id=rid, time_s=np.array([0.0, dt]),
            xyz_mm=np.array([[*a, 1.0], [*b, 1.0]], dtype=np.float32),
            mode=np.array([mode, MODE_W], dtype=np.uint8))

    ts = TrajectorySet(
        robots=(traj(1, p0, p1, MODE_T), traj(2, S, S, MODE_W), traj(3, b3, b3, MODE_W)),
        row_count=6)
    ref = run_collision_analysis(ts, cfg)
    assert len(ref.events) >= 1 and ref.minimum_arm_safety_margin_mm < 0  # Validator: FAIL

    r = geo.min_arm_margin_over_interval(gm, 1, p0, p1, 2, S, S, 0.0, dt)
    assert r.collides  # ours must not call it safe
    assert r.arm_margin <= -0.001 + 1e-9  # lower bound of the true continuous minimum

    # Why sampling density alone is not enough: end-inclusive n=5 sampling misses it.
    u = np.linspace(0, 1, 6)[:, None]
    naive = float(np.min(geo.arm_margin(gm, 1, p0 + u * (p1 - p0), 2, S)))
    assert naive > 0
