"""toolpath.generate: tests 1-14 of docs/specs/toolpath.md section 8 (15 is a measurement, N3).

Synthetic shapes use the model-01 config fixture (read-only). Tests 13 and 14 slice the real
models of the Validator repo (read-only) and score the footprints with the Validator's own
``compute_shape_metrics`` -- Validator imports are used in tests only, never in ``src/``.

Thresholds are the spec's. The hypothesis values of tests 1, 2 and 5 (0.99, 0.97..1.03, 5%) are
asserted as written; none was relaxed after measuring.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from shapely import LineString, Polygon, union_all
from shapely.geometry import box
from waam_validator.config.loader import load_config
from waam_validator.shape.layer_index import determine_layer_index
from waam_validator.shape.metrics import compute_shape_metrics
from waam_validator.shape.polygon_utils import normalize_polygon

from waam import toolpath
from waam.slicing import Layer, LayerStack, slice_stl
from waam.toolpath import Pass, ToolpathError, ToolpathParams, generate

FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "model01" / "config.yaml"
VALIDATOR_TESTS = Path("C:/Github/WAAM_Validator/tests")
W = 8.0


@pytest.fixture(scope="module")
def cfg():
    return load_config(FIXTURE_CONFIG)


def _stack(*geoms) -> LayerStack:
    return LayerStack(
        tuple(
            Layer(i, 2.0 * i, 2.0 * i + 2.0, 2.0 * i + 1.0, g, float(g.area))
            for i, g in enumerate(geoms)
        )
    )


def _params(cfg, **kw) -> ToolpathParams:
    return replace(ToolpathParams.from_config(cfg), **kw)


def _layer(tp, k):
    return [q for q in tp.passes if q.layer == k]


def _footprint(passes):
    return union_all([q.footprint for q in passes])


def _overfill(passes, shape) -> float:
    return float(_footprint(passes).difference(shape).area)


def _coverage(passes, shape) -> float:
    return float(_footprint(passes).intersection(shape).area / shape.area)


def _total_length(passes) -> float:
    return sum(q.length for q in passes)


def _corner_loss() -> float:
    return (1.0 - math.pi / 4.0) * (W / 2.0) ** 2  # c(w) of the spec


SQUARE = box(-50.0, -50.0, 50.0, 50.0)
RING = SQUARE.difference(box(-20.0, -20.0, 20.0, 20.0))
L_SHAPE = Polygon([(-50, -50), (50, -50), (50, 0), (0, 0), (0, 50), (-50, 50)])
STRIP6 = box(-50.0, -3.0, 50.0, 3.0)
STRIP8 = box(-50.0, -4.0, 50.0, 4.0)


# ---------------------------------------------------------------- 1-3


def test_1_square(cfg):
    tp = generate(_stack(SQUARE), cfg, use_cache=False)
    passes = _layer(tp, 0)
    assert _overfill(passes, SQUARE) <= 1e-6 * SQUARE.area
    assert _coverage(passes, SQUARE) >= 0.99
    ratio = _total_length(passes) * W / SQUARE.area
    assert 0.97 <= ratio <= 1.03, ratio


def test_2_ring(cfg):
    tp = generate(_stack(RING), cfg, use_cache=False)
    passes = _layer(tp, 0)
    assert any(q.kind == "hole" for q in passes)
    assert _overfill(passes, RING) <= 1e-6 * RING.area
    assert _coverage(passes, RING) >= 0.99


def test_3_l_shape_connectors_stay_inside(cfg):
    tp = generate(_stack(L_SHAPE), cfg, use_cache=False)
    passes = _layer(tp, 0)
    assert _overfill(passes, L_SHAPE) <= 1e-6 * L_SHAPE.area
    # at least one hatch pass uses a connector, and every connector bead is inside the section
    connectors = 0
    for q in passes:
        if q.kind != "hatch":
            continue
        v = np.asarray(q.vertices)
        for a, b in zip(v[:-1], v[1:]):
            if abs(b[1] - a[1]) > 1e-9:  # even layer: rows are horizontal, the rest connects
                connectors += 1
                bead = LineString([a, b]).buffer(W / 2.0, quad_segs=8)
                assert bead.difference(L_SHAPE).area <= 1e-6 * L_SHAPE.area
    assert connectors > 0


# ---------------------------------------------------------------- 4-6


def test_4_thin_strip_has_no_pass(cfg):
    tp = generate(_stack(STRIP6), cfg, use_cache=False)
    assert tp.passes == ()
    assert tp.thin_lost_mm2[0] == pytest.approx(STRIP6.area, rel=1e-9)


def test_5_strip_of_bead_width(cfg):
    """The criterion set of the default wall_mode, as written in the spec."""
    mode = ToolpathParams.from_config(cfg).wall_mode
    tp = generate(_stack(STRIP8), cfg, use_cache=False)
    passes = _layer(tp, 0)
    medial_length = STRIP8.bounds[2] - STRIP8.bounds[0] - W  # centre line, caps reach the ends
    if mode == "medial":
        assert [q.kind for q in passes] == ["medial"]
        assert _overfill(passes, STRIP8) <= 1e-6 * STRIP8.area
        uncovered = STRIP8.area - _footprint(passes).intersection(STRIP8).area
        assert uncovered <= 4 * _corner_loss() + 1e-3 * STRIP8.area
    else:
        eps_w = tp.params.eps_w_mm
        assert passes and all(q.kind == "contour" for q in passes)
        for q in passes:
            y = np.asarray(q.vertices)[:, 1]
            assert np.all(np.abs(y) <= eps_w + 1e-6)  # all on the centre line (y = 0)
        assert _total_length(passes) == pytest.approx(2 * medial_length, rel=0.05)
        assert _overfill(passes, STRIP8) <= 1e-6 * STRIP8.area


def test_5b_double_mode_strip_is_the_same_line_twice(cfg):
    """Both modes of #5, whatever the default. Not a spec criterion: see the footprint note.

    The spec asks double mode for 'footprint inside P'. A bead of width w centred ``eps_w`` off
    the centre line of a wall of width w sticks out by eps_w, so that criterion cannot hold; the
    bound used here is P grown by eps_w. The default mode's #5 test is asserted as in the spec.
    """
    params = _params(cfg, wall_mode="double")
    tp = generate(_stack(STRIP8), cfg, params, use_cache=False)
    passes = _layer(tp, 0)
    eps_w = params.eps_w_mm
    assert passes and all(q.kind == "contour" for q in passes)
    for q in passes:
        assert np.all(np.abs(np.asarray(q.vertices)[:, 1]) <= eps_w + 1e-6)
    medial_length = 100.0 - W
    assert _total_length(passes) == pytest.approx(2 * medial_length, rel=0.05)
    assert _footprint(passes).difference(STRIP8.buffer(eps_w + 1e-6)).area <= 1e-6 * STRIP8.area


def test_5c_medial_mode_strip(cfg):
    tp = generate(_stack(STRIP8), cfg, _params(cfg, wall_mode="medial"), use_cache=False)
    passes = _layer(tp, 0)
    assert [q.kind for q in passes] == ["medial"]
    assert _overfill(passes, STRIP8) <= 1e-6 * STRIP8.area
    uncovered = STRIP8.area - _footprint(passes).intersection(STRIP8).area
    assert uncovered <= 4 * _corner_loss() + 1e-3 * STRIP8.area


def test_6_two_islands(cfg):
    left, right = box(-150.0, -40.0, -60.0, 40.0), box(60.0, -40.0, 150.0, 40.0)
    tp = generate(_stack(left.union(right)), cfg, use_cache=False)
    passes = _layer(tp, 0)
    sides = set()
    for q in passes:
        x = np.asarray(q.vertices)[:, 0]
        assert np.all(x < 0) or np.all(x > 0), "a pass connects the islands"
        sides.add(bool(x[0] < 0))
    assert sides == {True, False}


# ---------------------------------------------------------------- 7-10


def _bytes(tp) -> bytes:
    out = []
    for q in tp.passes:
        out.append(
            repr((q.layer, q.z, q.kind, q.vertices, q.length, sorted(q.reachable_robots))).encode()
            + q.footprint.wkb
        )
    out.append(repr((tp.thin_lost_mm2, tp.empty_reach_count, tp.medial_fallback_regions)).encode())
    return b"".join(out)


def test_7_deterministic_and_cache_identical(cfg, tmp_path):
    stack = _stack(RING, L_SHAPE, STRIP8)
    first = generate(stack, cfg, use_cache=False)
    second = generate(stack, cfg, use_cache=False)
    assert _bytes(first) == _bytes(second)
    miss = generate(stack, cfg, cache_dir=tmp_path)
    assert list(tmp_path.glob("*.npz")), "the cache was not written"
    hit = generate(stack, cfg, cache_dir=tmp_path)
    assert _bytes(miss) == _bytes(first)
    assert _bytes(hit) == _bytes(first)


def test_8_defaults(cfg):
    p = ToolpathParams.from_config(cfg)
    assert (p.s_mm, p.o_mm, p.n_c, p.chord_mm, p.lift_dz_mm, p.eps_w_mm) == (
        W, W / 2.0, 1, 0.1, 2.0 * cfg.process.layer_height_mm, 0.01,
    )
    assert p.wall_mode == toolpath.DEFAULT_WALL_MODE
    assert p.wall_mode in ("medial", "double")


def test_9_hatch_angle_alternates(cfg):
    tp = generate(_stack(SQUARE, SQUARE, SQUARE, SQUARE), cfg, use_cache=False)
    for k in range(4):
        hatch = [q for q in _layer(tp, k) if q.kind == "hatch"]
        assert hatch
        aligned = 0
        for q in hatch:
            v = np.asarray(q.vertices)
            for a, b in zip(v[:-1], v[1:]):
                d = np.abs(b - a)
                along, across = (d[0], d[1]) if k % 2 == 0 else (d[1], d[0])
                if across <= 1e-9:
                    aligned += 1
                else:  # a connector between two rows: short, never a hatch row
                    assert math.hypot(*d) <= 2 * W
        assert aligned > 0


@pytest.mark.parametrize("ref", ["center", "top"])
def test_10_z_matches_validator(cfg, ref):
    config = cfg.model_copy(update={"process": cfg.process.model_copy(update={"tcp_z_reference": ref})})
    tp = generate(_stack(SQUARE, SQUARE, SQUARE), config, use_cache=False)
    h, base = config.process.layer_height_mm, config.process.build_plane_z_mm
    offset = 0.5 if ref == "center" else 1.0
    for q in tp.passes:
        assert q.z == pytest.approx(base + (q.layer + offset) * h, abs=1e-12)
        assert determine_layer_index(q.z, config) == q.layer


# ---------------------------------------------------------------- 11-12


def test_11_workspace_violation(cfg):
    small = cfg.model_copy(update={"workspace": cfg.workspace.model_copy(update={"radius_mm": 40.0})})
    with pytest.raises(ToolpathError) as err:
        generate(_stack(SQUARE), small, use_cache=False)
    assert err.value.code == "WORKSPACE_VIOLATION"


def test_12_empty_reach(cfg):
    far = [r.model_copy(update={"base_xyz_mm": [1.0e5, 1.0e5, 0.0]}) for r in cfg.robots]
    config = cfg.model_copy(update={"robots": far})
    tp = generate(_stack(SQUARE, RING), config, use_cache=False)
    assert tp.passes
    assert all(q.reachable_robots == frozenset() for q in tp.passes)
    assert tp.empty_reach_count == len(tp.passes)
    normal = generate(_stack(SQUARE, RING), cfg, use_cache=False)
    assert normal.empty_reach_count == 0
    assert all(q.reachable_robots == frozenset({1, 2, 3}) for q in normal.passes)


# ---------------------------------------------------------------- 13-14


def _real(name):
    d = VALIDATOR_TESTS / name
    config = load_config(d / "config.yaml")
    return config, slice_stl(d / "target.stl", config)


def _deposited(tp, stack, config):
    out = {}
    for k in range(stack.layer_count):
        passes = _layer(tp, k)
        if passes:
            out[k] = normalize_polygon(
                _footprint(passes),
                config.shape_validation.polygon_snap_tolerance_mm,
                config.shape_validation.area_epsilon_mm2,
            )
    return out


@pytest.fixture(scope="module")
def real_toolpaths():
    cache: dict[str, tuple] = {}

    def get(name):
        if name not in cache:
            config, stack = _real(name)
            cache[name] = (config, stack, generate(stack, config, use_cache=False))
        return cache[name]

    return get


@pytest.mark.parametrize("name", ["01", "02", "03", "04", "06"])
def test_13_real_model_shape(real_toolpaths, name):
    config, stack, tp = real_toolpaths(name)
    metrics, _ = compute_shape_metrics(
        _deposited(tp, stack, config), {l.index: l.geometry for l in stack.layers}, config
    )
    assert metrics.iou >= 0.93, metrics.iou
    assert metrics.failed_layer_ratio <= 0.05, metrics.failed_layer_ratio
    assert metrics.overfill_ratio <= 0.30, metrics.overfill_ratio


def test_14_model_03_footprints_inside_section(real_toolpaths):
    config, stack, tp = real_toolpaths("03")
    for layer in stack.layers:
        passes = _layer(tp, layer.index)
        assert _overfill(passes, layer.geometry) <= 1e-6 * layer.area_mm2, layer.index


# ---------------------------------------------------------------- extras (not in the spec table)


def test_passes_are_well_formed_and_ordered(cfg):
    tp = generate(_stack(RING, L_SHAPE, STRIP8), cfg, use_cache=False)
    stage = {"contour": 0, "hole": 1, "medial": 2, "hatch": 3}
    last_layer, last_stage = -1, 0
    for q in tp.passes:
        assert isinstance(q, Pass)
        assert q.kind in stage and len(q.vertices) >= 2 and q.length > 0
        if q.layer != last_layer:
            last_layer, last_stage = q.layer, 0
        assert stage[q.kind] >= last_stage, "canonical order (V9)"
        last_stage = stage[q.kind]
        v = np.asarray(q.vertices)
        assert q.length == pytest.approx(float(np.hypot(*(v[1:] - v[:-1]).T).sum()))
        assert np.all(np.hypot(*(v[1:] - v[:-1]).T) > 0), "no zero-length step"
        if q.kind in ("contour", "hole") and q.vertices[0] == q.vertices[-1]:
            ring = Polygon(v)
            assert ring.exterior.is_ccw == (q.kind == "contour")  # V19 (CCW outer, CW hole)


def test_layers_start_where_the_previous_ended(cfg):
    """V9: the first pass of the next layer is the nearest one *of the first stage* (contour)."""
    tp = generate(_stack(RING, RING), cfg, use_cache=False)
    last = np.asarray(_layer(tp, 0)[-1].vertices[-1])
    contours = [q for q in _layer(tp, 1) if q.kind == "contour"]
    start = np.asarray(_layer(tp, 1)[0].vertices[0])
    assert _layer(tp, 1)[0].kind == "contour"
    best = min(min(np.hypot(*(np.asarray(v) - last)) for v in q.vertices) for q in contours)
    assert np.hypot(*(start - last)) == pytest.approx(best)


def test_empty_layer_gives_no_pass_and_zero_loss(cfg):
    tp = generate(_stack(Polygon(), SQUARE), cfg, use_cache=False)
    assert not _layer(tp, 0) and _layer(tp, 1)
    assert tp.thin_lost_mm2[0] == 0.0


def test_medial_exception_falls_back_per_zone(cfg, monkeypatch):
    ok = generate(_stack(STRIP8), cfg, _params(cfg, wall_mode="medial"), use_cache=False)
    assert ok.medial_fallback_regions == 0

    def boom(*a, **k):
        raise RuntimeError("no medial axis")

    monkeypatch.setattr(toolpath, "_medial_chains", boom)
    tp = generate(_stack(STRIP8), cfg, _params(cfg, wall_mode="medial"), use_cache=False)
    assert tp.medial_fallback_regions == 1
    passes = _layer(tp, 0)
    assert passes and all(q.kind == "contour" for q in passes)


@pytest.mark.parametrize(
    "bad",
    [
        {"s_mm": 0.0}, {"s_mm": -1.0}, {"o_mm": float("nan")}, {"chord_mm": 0.0},
        {"n_c": 0}, {"n_c": 1.5}, {"eps_w_mm": -0.1}, {"eps_w_mm": 4.0},
        {"wall_mode": "triple"}, {"medial_sample_mm": 0.0}, {"s_mm": float("inf")},
    ],
)
def test_bad_parameters_raise_value_error(cfg, bad):
    with pytest.raises(ValueError):
        generate(_stack(SQUARE), cfg, _params(cfg, **bad), use_cache=False)


def test_extra_contour_rings_cover_more_boundary(cfg):
    one = generate(_stack(SQUARE), cfg, use_cache=False)
    two = generate(_stack(SQUARE), cfg, _params(cfg, n_c=2), use_cache=False)
    rings = lambda t: [q for q in t.passes if q.kind == "contour"]  # noqa: E731
    assert len(rings(one)) == 1 and len(rings(two)) == 2
    assert _overfill(two.passes, SQUARE) <= 1e-6 * SQUARE.area


def test_damaged_cache_is_a_miss(cfg, tmp_path):
    stack = _stack(SQUARE)
    first = generate(stack, cfg, cache_dir=tmp_path)
    (file,) = tmp_path.glob("*.npz")
    file.write_bytes(b"not an npz")
    again = generate(stack, cfg, cache_dir=tmp_path)
    assert _bytes(again) == _bytes(first)


def test_difference_retries_on_geos_topology_error(monkeypatch):
    """A GEOS TopologyException (seen on a layer of model 05) must not abort generation."""
    import shapely
    from shapely.geometry.base import BaseGeometry

    calls = []

    def rejecting(self, other, grid_size=None):
        calls.append(1)
        raise shapely.errors.GEOSException("TopologyException: Ring edge missing")

    monkeypatch.setattr(BaseGeometry, "difference", rejecting)
    result = toolpath._difference(box(0, 0, 10, 10), box(5, 0, 15, 10))
    assert calls, "the plain operation was not tried first"
    assert result.area == pytest.approx(50.0)
