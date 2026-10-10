"""slicing.slice_stl: oracle tests of docs/specs/slicing.md section 5.

Validator imports are used only where an oracle needs them (2, 3, and the synthetic cross-check).
Model data is read from the Validator repo (read-only), like the other tests.
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from shapely import MultiPolygon, Polygon, to_wkb
from shapely.geometry import box
from waam_validator.config.loader import load_config
from waam_validator.shape.target import load_target_mesh, slice_target_layers

from waam import slicing
from waam.slicing import SlicingError, slice_stl

VALIDATOR_TESTS = Path("C:/Github/WAAM_Validator/tests")
SAMPLE_JOB = Path(__file__).parent / "fixtures" / "sample_job"

# Oracle 1: layer counts of the six models (test data only; never in src/).
# Model 05 is included: its first slicing took 6.01 s on an empty cache (measured 2026-10-10 19:39,
# .cache/waam/analysis/time_slicing_05.py), below the 5 min limit of the night prompt.
LAYER_COUNTS = {"01": 6, "02": 8, "03": 6, "04": 50, "05": 350, "06": 51}
ORACLE3_MODELS = ["01", "02", "03", "04", "05", "06"]


def _model(name: str):
    d = VALIDATOR_TESTS / name
    return d / "target.stl", load_config(d / "config.yaml")


@pytest.fixture(scope="module")
def stacks():
    cache: dict[str, object] = {}

    def get(name: str):
        if name not in cache:
            stl, cfg = _model(name)
            cache[name] = slice_stl(stl, cfg, use_cache=False)
        return cache[name]

    return get


# ---------------------------------------------------------------- oracle 1


@pytest.mark.parametrize("name,count", sorted(LAYER_COUNTS.items()))
def test_layer_count_matches_spec_table(stacks, name, count):
    stack = stacks(name)
    assert stack.layer_count == count == len(stack.layers)
    _, cfg = _model(name)
    h, base = cfg.process.layer_height_mm, cfg.process.build_plane_z_mm
    for k, layer in enumerate(stack.layers):
        assert layer.index == k
        assert layer.z_bottom == base + k * h
        assert layer.z_top == layer.z_bottom + h
        assert layer.z_slice == base + (k + 0.5) * h
        assert layer.area_mm2 == layer.geometry.area


# ---------------------------------------------------------------- oracle 2


def test_sample_job_layer0_area_equals_validator_layer_metrics():
    cfg = load_config(SAMPLE_JOB / "config.yaml")
    stack = slice_stl(SAMPLE_JOB / "target.stl", cfg, use_cache=False)
    csv_path = next(SAMPLE_JOB.glob("output/*/layer_metrics.csv"))
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    from_validator = float(rows[0]["target_area_mm2"])
    assert from_validator == 332.48569089999995  # the value the spec cites
    assert stack.layers[0].area_mm2 == from_validator
    assert stack.layer_count == len(rows)


# ---------------------------------------------------------------- oracle 3


@pytest.mark.parametrize("name", ORACLE3_MODELS)
def test_every_layer_equals_validator_slice_target_layers(stacks, name):
    stl, cfg = _model(name)
    stack = stacks(name)
    theirs = slice_target_layers(load_target_mesh(stl, cfg), range(stack.layer_count), cfg)
    for layer in stack.layers:
        ref = theirs[layer.index]
        assert layer.area_mm2 == ref.area, (name, layer.index, layer.area_mm2, ref.area)
        assert to_wkb(layer.geometry) == to_wkb(ref), (name, layer.index)


# ---------------------------------------------------------------- oracle 4 (synthetic)

SYN_CFG = SimpleNamespace(
    process=SimpleNamespace(layer_height_mm=2.0, build_plane_z_mm=0.0),
    shape_validation=SimpleNamespace(polygon_snap_tolerance_mm=1e-6, area_epsilon_mm2=1e-9),
    collision=SimpleNamespace(geometry_epsilon_mm=1e-6),
)


def _write(tmp_path: Path, mesh: trimesh.Trimesh, name: str = "t.stl") -> Path:
    path = tmp_path / name
    mesh.export(path)
    return path


def _prism(poly, z0: float, z1: float) -> trimesh.Trimesh:
    m = trimesh.creation.extrude_polygon(poly, z1 - z0)
    m.apply_translation([0.0, 0.0, z0])
    return m


def _vs_validator(path: Path, stack) -> None:
    mesh = load_target_mesh(path, _validator_like_cfg())
    theirs = slice_target_layers(mesh, range(stack.layer_count), _validator_like_cfg())
    for layer in stack.layers:
        assert to_wkb(layer.geometry) == to_wkb(theirs[layer.index])


def _validator_like_cfg():
    # The Validator's functions read ``validation`` too; take that block from a real config and
    # the process / shape / collision blocks from the synthetic parameters.
    real = load_config(VALIDATOR_TESTS / "01" / "config.yaml")
    return SimpleNamespace(
        validation=real.validation,
        process=SYN_CFG.process,
        shape_validation=SYN_CFG.shape_validation,
        collision=SYN_CFG.collision,
    )


def test_synthetic_one_hole_is_preserved(tmp_path):
    poly = box(0, 0, 20, 20).difference(box(5, 5, 15, 15))
    stl = _write(tmp_path, _prism(poly, 0.0, 10.0))
    stack = slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert stack.layer_count == 5
    for layer in stack.layers:
        assert isinstance(layer.geometry, Polygon)
        assert len(layer.geometry.interiors) == 1
        assert layer.area_mm2 == pytest.approx(300.0, abs=1e-6)
    _vs_validator(stl, stack)


def test_synthetic_two_separate_islands(tmp_path):
    mesh = trimesh.util.concatenate(
        [_prism(box(0, 0, 10, 10), 0.0, 6.0), _prism(box(30, 0, 50, 20), 0.0, 6.0)]
    )
    stl = _write(tmp_path, mesh)
    stack = slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert stack.layer_count == 3
    for layer in stack.layers:
        assert isinstance(layer.geometry, MultiPolygon)
        assert len(layer.geometry.geoms) == 2
        assert layer.area_mm2 == pytest.approx(100.0 + 400.0, abs=1e-6)
    _vs_validator(stl, stack)


def test_synthetic_island_inside_a_hole(tmp_path):
    ring = box(0, 0, 30, 30).difference(box(5, 5, 25, 25))  # 900 - 400 = 500
    core = box(12, 12, 18, 18)  # 36, floats in the ring's hole
    stl = _write(tmp_path, trimesh.util.concatenate([_prism(ring, 0.0, 4.0), _prism(core, 0.0, 4.0)]))
    stack = slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert stack.layer_count == 2
    for layer in stack.layers:
        g = layer.geometry
        assert isinstance(g, MultiPolygon) and len(g.geoms) == 2
        assert sorted(len(p.interiors) for p in g.geoms) == [0, 1]  # ring keeps its hole
        assert layer.area_mm2 == pytest.approx(500.0 + 36.0, abs=1e-6)
        assert not g.contains(box(7, 7, 10, 10))  # the gap between ring and core stays empty
    _vs_validator(stl, stack)


def test_layer_count_rounds_up_and_every_layer_exists(tmp_path):
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), 0.0, 7.0))
    stack = slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert stack.layer_count == 4  # ceil(7 / 2)
    assert [round(layer.z_slice, 9) for layer in stack.layers] == [1.0, 3.0, 5.0, 7.0]
    _vs_validator(stl, stack)  # incl. the layer whose slice plane touches the top face


def test_build_plane_offset_shifts_layers(tmp_path):
    cfg = SimpleNamespace(
        process=SimpleNamespace(layer_height_mm=2.0, build_plane_z_mm=5.0),
        shape_validation=SYN_CFG.shape_validation,
        collision=SYN_CFG.collision,
    )
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), 5.0, 11.0))
    stack = slice_stl(stl, cfg, cache_dir=tmp_path / "c")
    assert stack.layer_count == 3
    assert stack.layers[0].z_slice == 6.0 and stack.layers[0].z_bottom == 5.0
    assert all(layer.area_mm2 == pytest.approx(100.0) for layer in stack.layers)


def test_mesh_below_build_plane_is_refused(tmp_path):
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), -3.0, 5.0))
    with pytest.raises(SlicingError) as e:
        slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert e.value.code == "TARGET_BELOW_BUILD_PLANE"


def test_non_watertight_mesh_raises_without_repair(tmp_path):
    mesh = _prism(box(0, 0, 10, 10), 0.0, 6.0)
    mesh.update_faces(np.arange(len(mesh.faces)) != 0)  # drop one triangle: an open mesh
    stl = _write(tmp_path, mesh)
    with pytest.raises(SlicingError) as e:
        slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert e.value.code == "TARGET_NOT_WATERTIGHT"


def test_bad_parameters_are_refused(tmp_path):
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), 0.0, 6.0))
    bad = SimpleNamespace(
        process=SimpleNamespace(layer_height_mm=0.0, build_plane_z_mm=0.0),
        shape_validation=SYN_CFG.shape_validation,
        collision=SYN_CFG.collision,
    )
    with pytest.raises(ValueError, match="layer_height_mm"):
        slice_stl(stl, bad, cache_dir=tmp_path / "c")


def test_stl_file_is_not_modified(tmp_path):
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), 0.0, 6.0))
    before = stl.read_bytes()
    slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert stl.read_bytes() == before


# ---------------------------------------------------------------- oracle 5 (record only)


@pytest.mark.parametrize("name", ["01", "02", "03", "04", "06"])
def test_volume_relative_error_is_recorded_not_asserted(stacks, name, record_property):
    stl, cfg = _model(name)
    stack = stacks(name)
    h = cfg.process.layer_height_mm
    mesh = load_target_mesh(stl, cfg)
    rel = (sum(layer.area_mm2 for layer in stack.layers) * h - mesh.volume) / mesh.volume
    record_property("volume_relative_error", rel)


# ---------------------------------------------------------------- oracle 6 (cache)


def _wkbs(stack) -> list[bytes]:
    return [to_wkb(layer.geometry) for layer in stack.layers]


def test_cache_hit_does_not_reslice_and_returns_identical_wkb(tmp_path, monkeypatch):
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20).difference(box(5, 5, 15, 15)), 0.0, 10.0))
    cache = tmp_path / "cache"
    first = slice_stl(stl, SYN_CFG, cache_dir=cache)
    assert len(list(cache.glob("*.npz"))) == 1

    def boom(*a, **k):
        raise AssertionError("re-sliced on a cache hit")

    monkeypatch.setattr(slicing, "_slice_layers", boom)
    monkeypatch.setattr(slicing, "_load_mesh", boom)
    second = slice_stl(stl, SYN_CFG, cache_dir=cache)
    assert _wkbs(second) == _wkbs(first)
    assert [layer.area_mm2 for layer in second.layers] == [layer.area_mm2 for layer in first.layers]


def test_cache_misses_when_stl_bytes_change(tmp_path):
    cache = tmp_path / "cache"
    a = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0), "a.stl")
    b = _write(tmp_path, _prism(box(0, 0, 21, 20), 0.0, 10.0), "b.stl")
    sa = slice_stl(a, SYN_CFG, cache_dir=cache)
    sb = slice_stl(b, SYN_CFG, cache_dir=cache)
    assert len(list(cache.glob("*.npz"))) == 2
    assert sa.layers[0].area_mm2 == pytest.approx(400.0)
    assert sb.layers[0].area_mm2 == pytest.approx(420.0)  # not served from a's entry


def test_cache_misses_when_a_parameter_changes(tmp_path):
    cache = tmp_path / "cache"
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))
    slice_stl(stl, SYN_CFG, cache_dir=cache)
    cfg2 = SimpleNamespace(
        process=SimpleNamespace(layer_height_mm=5.0, build_plane_z_mm=0.0),
        shape_validation=SYN_CFG.shape_validation,
        collision=SYN_CFG.collision,
    )
    s2 = slice_stl(stl, cfg2, cache_dir=cache)
    assert len(list(cache.glob("*.npz"))) == 2
    assert s2.layer_count == 2


def test_damaged_cache_entry_is_a_miss_and_is_rewritten(tmp_path):
    cache = tmp_path / "cache"
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))
    good = slice_stl(stl, SYN_CFG, cache_dir=cache)
    entry = next(cache.glob("*.npz"))
    entry.write_bytes(b"not an npz")
    again = slice_stl(stl, SYN_CFG, cache_dir=cache)
    assert _wkbs(again) == _wkbs(good)
    assert slicing._cache_read(entry) is not None  # rewritten


def test_use_cache_false_touches_no_directory(tmp_path):
    cache = tmp_path / "cache"
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))
    slice_stl(stl, SYN_CFG, cache_dir=cache, use_cache=False)
    assert not cache.exists()


def test_cache_roundtrips_empty_layers(tmp_path):
    # a stack with an empty layer survives the WKB cache (exists, area 0)
    cache = tmp_path / "cache"
    slicing._cache_write(cache / "x.npz", [Polygon(), box(0, 0, 1, 1)])
    out = slicing._cache_read(cache / "x.npz")
    assert out is not None and out[0].is_empty and out[1].area == 1.0


def test_second_call_on_a_real_model_is_a_hit(tmp_path, monkeypatch):
    stl, cfg = _model("04")
    first = slice_stl(stl, cfg, cache_dir=tmp_path)

    def boom(*a, **k):
        raise AssertionError("re-sliced on a cache hit")

    monkeypatch.setattr(slicing, "_slice_layers", boom)
    assert _wkbs(slice_stl(stl, cfg, cache_dir=tmp_path)) == _wkbs(first)


def _cfg(h=2.0, base=0.0, snap=1e-6, geo=1e-6, area=1e-9):
    return SimpleNamespace(
        process=SimpleNamespace(layer_height_mm=h, build_plane_z_mm=base),
        shape_validation=SimpleNamespace(polygon_snap_tolerance_mm=snap, area_epsilon_mm2=area),
        collision=SimpleNamespace(geometry_epsilon_mm=geo),
    )


@pytest.mark.parametrize(
    "kw", [dict(h=4.0), dict(base=-1.0), dict(snap=1e-5), dict(geo=1e-5), dict(area=1e-7)]
)
def test_each_cache_key_parameter_changes_the_entry(tmp_path, kw):
    cache = tmp_path / "cache"
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))
    slice_stl(stl, _cfg(), cache_dir=cache)
    slice_stl(stl, _cfg(**kw), cache_dir=cache)
    assert len(list(cache.glob("*.npz"))) == 2


def test_algo_version_change_misses(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))
    slice_stl(stl, SYN_CFG, cache_dir=cache)
    monkeypatch.setattr(slicing, "ALGO_VERSION", "slicing-test-bump")
    slice_stl(stl, SYN_CFG, cache_dir=cache)
    assert len(list(cache.glob("*.npz"))) == 2


def test_same_geometry_but_different_stl_bytes_misses(tmp_path):
    cache = tmp_path / "cache"
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))
    slice_stl(stl, SYN_CFG, cache_dir=cache)
    raw = bytearray(stl.read_bytes())
    raw[0] ^= 0x01  # binary STL: byte 0 is in the 80-byte header, geometry untouched
    other = tmp_path / "other.stl"
    other.write_bytes(bytes(raw))
    slice_stl(other, SYN_CFG, cache_dir=cache)
    assert len(list(cache.glob("*.npz"))) == 2


def test_cache_write_failure_does_not_fail_slicing(tmp_path, monkeypatch):
    stl = _write(tmp_path, _prism(box(0, 0, 20, 20), 0.0, 10.0))

    def deny(*a, **k):
        raise PermissionError("locked")

    monkeypatch.setattr(slicing.os, "replace", deny)
    cache = tmp_path / "cache"
    stack = slice_stl(stl, SYN_CFG, cache_dir=cache)
    assert stack.layer_count == 5
    assert list(cache.glob("*.tmp")) == []  # no leftover temp file


# ---------------------------------------------------------------- fallback / failure / closure


def test_empty_middle_layer_exists_and_matches_validator(tmp_path):
    mesh = trimesh.util.concatenate(
        [_prism(box(0, 0, 10, 10), 0.0, 2.0), _prism(box(0, 0, 10, 10), 4.0, 6.0)]
    )
    stl = _write(tmp_path, mesh)
    stack = slice_stl(stl, SYN_CFG, cache_dir=tmp_path / "c")
    assert [round(layer.area_mm2, 6) for layer in stack.layers] == [100.0, 0.0, 100.0]
    assert stack.layers[1].geometry.is_empty
    _vs_validator(stl, stack)


def test_fallback_offset_is_used_when_exact_plane_is_empty(tmp_path, monkeypatch):
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), 0.0, 6.0))
    real = slicing._section_once
    seen = []

    def fake(mesh, z, params):
        seen.append(z)
        if z == 3.0:
            return Polygon()  # the exact plane yields nothing
        return real(mesh, z, params)

    monkeypatch.setattr(slicing, "_section_once", fake)
    stack = slice_stl(stl, SYN_CFG, use_cache=False)
    assert stack.layers[1].area_mm2 == pytest.approx(100.0)  # taken from z + eps
    assert 3.0 in seen and any(z != 3.0 and abs(z - 3.0) < 1e-4 for z in seen)


def test_section_failure_raises_when_every_attempt_fails(tmp_path, monkeypatch):
    stl = _write(tmp_path, _prism(box(0, 0, 10, 10), 0.0, 6.0))

    def fail(mesh, z, params):
        raise RuntimeError("boom")

    monkeypatch.setattr(slicing, "_section_once", fail)
    with pytest.raises(SlicingError) as e:
        slice_stl(stl, SYN_CFG, use_cache=False)
    assert e.value.code == "TARGET_SECTION_FAILED"


def test_geometry_epsilon_larger_than_snap_matches_validator(tmp_path):
    cfg = _cfg(snap=1e-7, geo=1e-3)
    poly = box(0, 0, 20, 20).difference(box(5, 5, 15, 15))
    stl = _write(tmp_path, _prism(poly, 0.0, 10.0))
    stack = slice_stl(stl, cfg, use_cache=False)
    real = load_config(VALIDATOR_TESTS / "01" / "config.yaml")
    vcfg = SimpleNamespace(
        validation=real.validation,
        process=cfg.process,
        shape_validation=cfg.shape_validation,
        collision=cfg.collision,
    )
    theirs = slice_target_layers(load_target_mesh(stl, vcfg), range(stack.layer_count), vcfg)
    assert [to_wkb(layer.geometry) for layer in stack.layers] == [
        to_wkb(theirs[k]) for k in range(stack.layer_count)
    ]


def test_open_chain_is_dropped_and_nearly_closed_chain_is_kept(monkeypatch):
    def fake_mesh_plane(mesh, plane_origin, plane_normal):
        gap = 5e-4  # between the last and the first point of the square
        sq = [(0, 0), (10, 0), (10, 10), (0, 10), (0, gap)]
        chain = [np.array([[*a, 0.0], [*b, 0.0]]) for a, b in zip(sq[:-1], sq[1:])]
        open_ = [
            np.array([[100.0, 0, 0], [110.0, 0, 0]]),
            np.array([[110.0, 0, 0], [110.0, 10, 0]]),
        ]
        return np.array(chain + open_)

    monkeypatch.setattr(slicing.trimesh.intersections, "mesh_plane", fake_mesh_plane)
    loops = slicing._loop_polygons(None, 0.0, 0.0, 1e-3)
    assert len(loops) == 1 and loops[0].area == pytest.approx(100.0, rel=1e-3)
    assert slicing._loop_polygons(None, 0.0, 0.0, 1e-4) == []  # gap 5e-4 > closure tolerance


def test_mixed_winding_agrees_on_area(tmp_path):
    mesh = _prism(box(0, 0, 20, 20).difference(box(5, 5, 15, 15)), 0.0, 10.0)
    faces = mesh.faces.copy()
    faces[::2] = faces[::2][:, ::-1]
    mesh = trimesh.Trimesh(mesh.vertices, faces, process=False)
    stl = _write(tmp_path, mesh)
    stack = slice_stl(stl, SYN_CFG, use_cache=False)
    for layer in stack.layers:
        assert len(layer.geometry.interiors) == 1
        assert layer.area_mm2 == pytest.approx(300.0, abs=1e-9)
