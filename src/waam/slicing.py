"""slicing: STL -> per-layer cross-sections (docs/specs/slicing.md).

``slice_stl(stl_path, config)`` returns a ``LayerStack``: one shapely geometry (holes kept) and
one area per layer. The rules follow the Validator's target slicing (mid-plane section, even-odd
loop union, snap, area filter, empty-section fallback) but are re-implemented here: ``src/`` never
imports ``waam_validator``. Equality with the Validator is proven by the oracle tests only.

Differences from the Validator, stated:
- No repair, ever. A mesh that is not watertight after preprocessing raises
  ``SlicingError("TARGET_NOT_WATERTIGHT")`` (C-18 decision 3); the Validator may ``fill_holes``.
- Face-winding repair and the body count are skipped. The set of plane/triangle segments is the
  same up to direction and ``is_watertight`` does not depend on winding, so area and topology
  agree. With MIXED face winding the segment direction differs, so loop start points and
  vertex order in the WKB (and the area, at ulp level; ~3.6e-12 mm2 measured by the reviewer on
  model 01 with half the faces flipped) can differ from the Validator. Uniform winding gave
  identical WKB.
- The Validator rejects meshes whose face orientation cannot be resolved
  (``repair_normals_and_count_bodies`` raises); this module does not check that.
- ``require_watertight_target`` / ``attempt_target_repair`` of the Validator config are ignored.

``config`` is the Validator config or any object with these attributes (never constants here):
``process.layer_height_mm``, ``process.build_plane_z_mm``,
``shape_validation.polygon_snap_tolerance_mm``, ``shape_validation.area_epsilon_mm2``,
``collision.geometry_epsilon_mm``.

Cache (``.cache/waam/slicing/``): key = sha256(STL bytes) + the five parameters + ``ALGO_VERSION``
+ library versions (shapely, GEOS, trimesh, numpy) + sha256 of this source file.
A failed cache write never fails the slicing (the cache is an optimisation only).
The value is the per-layer WKB; the same key returns byte-identical geometry.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import shapely
import trimesh
from shapely import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Polygon,
    from_wkb,
    get_parts,
    line_merge,
    make_valid,
    set_precision,
    to_wkb,
    union_all,
)
from shapely.geometry.base import BaseGeometry

# Bump when the slicing rules change in a way that alters the output; it is part of the cache key.
ALGO_VERSION = "slicing-1"

_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "waam" / "slicing"


class SlicingError(Exception):
    """A target mesh or section that cannot be sliced. ``code`` mirrors the Validator's names."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class Layer:
    index: int
    z_bottom: float
    z_top: float
    z_slice: float
    geometry: BaseGeometry  # Polygon / MultiPolygon, holes preserved; empty polygon if no section
    area_mm2: float


@dataclass(frozen=True, slots=True)
class LayerStack:
    layers: tuple[Layer, ...]

    @property
    def layer_count(self) -> int:
        return len(self.layers)


@dataclass(frozen=True, slots=True)
class _Params:
    layer_height_mm: float
    build_plane_z_mm: float
    snap_mm: float
    geometry_epsilon_mm: float
    area_epsilon_mm2: float

    @classmethod
    def from_config(cls, config: object) -> _Params:
        return cls(
            layer_height_mm=float(config.process.layer_height_mm),  # type: ignore[attr-defined]
            build_plane_z_mm=float(config.process.build_plane_z_mm),  # type: ignore[attr-defined]
            snap_mm=float(config.shape_validation.polygon_snap_tolerance_mm),  # type: ignore[attr-defined]
            geometry_epsilon_mm=float(config.collision.geometry_epsilon_mm),  # type: ignore[attr-defined]
            area_epsilon_mm2=float(config.shape_validation.area_epsilon_mm2),  # type: ignore[attr-defined]
        )

    def validate(self) -> None:
        if not (math.isfinite(self.layer_height_mm) and self.layer_height_mm > 0.0):
            raise ValueError(f"layer_height_mm must be finite and > 0, got {self.layer_height_mm!r}")
        for name in ("build_plane_z_mm", "snap_mm", "geometry_epsilon_mm", "area_epsilon_mm2"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite, got {getattr(self, name)!r}")


# ---------------------------------------------------------------- mesh

def _load_mesh(stl_bytes: bytes, params: _Params) -> trimesh.Trimesh:
    """Load + preprocess like the Validator's ``load_target_mesh``, without any repair."""
    try:
        loaded = trimesh.load(io.BytesIO(stl_bytes), file_type="stl", process=False)
        if isinstance(loaded, trimesh.Scene):
            meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if not meshes:
                raise ValueError("STL scene contains no triangle mesh")
            mesh = trimesh.util.concatenate(meshes)
        elif isinstance(loaded, trimesh.Trimesh):
            mesh = loaded.copy()
        else:
            raise ValueError(f"Unsupported mesh object: {type(loaded).__name__}")
    except Exception as exc:
        raise SlicingError("TARGET_LOAD_FAILED", str(exc)) from exc
    if mesh.is_empty or len(mesh.faces) == 0:
        raise SlicingError("TARGET_EMPTY", "STL contains no triangles.")
    if not np.isfinite(mesh.vertices).all():
        raise SlicingError("TARGET_NONFINITE", "STL contains non-finite vertices.")
    try:
        mesh.merge_vertices()
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
    except Exception as exc:
        raise SlicingError("TARGET_LOAD_FAILED", str(exc)) from exc
    if mesh.is_empty or len(mesh.faces) == 0:
        raise SlicingError("TARGET_EMPTY", "No valid triangles remain.")
    if not mesh.is_watertight:
        raise SlicingError(
            "TARGET_NOT_WATERTIGHT", "The STL must be watertight after preprocessing (no repair)."
        )
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    if not np.isfinite(bounds).all():
        raise SlicingError("TARGET_NONFINITE", "STL bounds are non-finite.")
    if bounds[0, 2] < params.build_plane_z_mm - params.geometry_epsilon_mm:
        raise SlicingError("TARGET_BELOW_BUILD_PLANE", "The STL extends below the build plane.")
    return mesh


# ---------------------------------------------------------------- one section

def _polygon_components(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        out: list[Polygon] = []
        for child in geometry.geoms:
            out.extend(_polygon_components(child))
        return out
    return []


def _normalize(geometry: BaseGeometry, snap: float, area_eps: float) -> BaseGeometry:
    """make_valid -> snap -> drop pieces <= area_eps -> union (Polygon / MultiPolygon / empty)."""
    if geometry.is_empty:
        return Polygon()
    valid = make_valid(geometry) if not geometry.is_valid else geometry
    if snap > 0:
        valid = set_precision(valid, snap, mode="valid_output")
    pieces = [p for p in _polygon_components(valid) if p.area > area_eps]
    if not pieces:
        return Polygon()
    merged = union_all(pieces)
    if not merged.is_valid:
        merged = make_valid(merged)
    filtered = [p for p in _polygon_components(merged) if p.area > area_eps]
    if not filtered:
        return Polygon()
    if len(filtered) == 1:
        return filtered[0]
    return MultiPolygon(filtered)


def _loop_polygons(mesh: trimesh.Trimesh, z: float, snap: float, closure: float) -> list[Polygon]:
    """Closed XY loops from the triangle/plane segments; open chains are dropped."""
    lines = np.asarray(
        trimesh.intersections.mesh_plane(
            mesh, plane_origin=np.array([0.0, 0.0, z]), plane_normal=np.array([0.0, 0.0, 1.0])
        ),
        dtype=np.float64,
    )
    if lines.size == 0:
        return []
    segments = [seg[:, :2] for seg in lines if len(seg) == 2]
    if not segments:
        return []
    linework: BaseGeometry = MultiLineString(segments)
    if snap > 0:
        linework = set_precision(linework, snap)
    merged = line_merge(linework)
    loops: list[Polygon] = []
    for part in get_parts(merged):
        if not isinstance(part, LineString):
            continue
        pts = np.asarray(part.coords, dtype=np.float64)
        if len(pts) < 3:
            continue
        if np.linalg.norm(pts[0] - pts[-1]) > closure:
            continue
        poly = Polygon(pts)
        if not poly.is_empty:
            loops.append(poly)
    return loops


def _even_odd(loops: list[Polygon]) -> BaseGeometry:
    """Symmetric difference of the loops, biggest first: holes, islands, islands in holes."""
    geometry: BaseGeometry = Polygon()
    for poly in sorted(loops, key=lambda p: (-p.area, p.bounds)):
        geometry = geometry.symmetric_difference(poly)
    return geometry


def _section_once(mesh: trimesh.Trimesh, z: float, params: _Params) -> BaseGeometry:
    loops = _loop_polygons(
        mesh, z, params.snap_mm, max(params.snap_mm, params.geometry_epsilon_mm)
    )
    if not loops:
        return Polygon()
    return _normalize(_even_odd(loops), params.snap_mm, params.area_epsilon_mm2)


def _layer_count(zmax: float, params: _Params) -> int:
    return max(0, math.ceil((zmax - params.build_plane_z_mm) / params.layer_height_mm))


def _slice_layers(mesh: trimesh.Trimesh, params: _Params) -> list[BaseGeometry]:
    h = params.layer_height_mm
    eps_z = min(1e-4, h * 1e-6)
    zmin, zmax = float(mesh.bounds[0, 2]), float(mesh.bounds[1, 2])
    out: list[BaseGeometry] = []
    for k in range(_layer_count(zmax, params)):
        z = params.build_plane_z_mm + (k + 0.5) * h
        error: Exception | None = None
        try:
            geometry = _section_once(mesh, z, params)
        except Exception as exc:
            error = exc
            geometry = Polygon()
        if geometry.is_empty and zmin < z < zmax:
            for offset in (eps_z, -eps_z):
                try:
                    fallback = _section_once(mesh, z + offset, params)
                except Exception:
                    continue
                if not fallback.is_empty:
                    geometry = fallback
                    break
        if error is not None and geometry.is_empty:
            raise SlicingError("TARGET_SECTION_FAILED", f"layer {k}: {error}") from error
        out.append(geometry)
    return out


# ---------------------------------------------------------------- cache

def _cache_key(stl_bytes: bytes, params: _Params) -> str:
    h = hashlib.sha256()
    h.update(hashlib.sha256(stl_bytes).digest())
    h.update(
        repr(
            (
                params.layer_height_mm,
                params.build_plane_z_mm,
                params.snap_mm,
                params.geometry_epsilon_mm,
                params.area_epsilon_mm2,
                ALGO_VERSION,
                shapely.__version__,
                shapely.geos_version_string,
                trimesh.__version__,
                np.__version__,
                _SOURCE_SHA256,
            )
        ).encode()
    )
    return h.hexdigest()


def _cache_write(path: Path, geometries: list[BaseGeometry]) -> None:
    blobs = [to_wkb(g) for g in geometries]
    offsets = np.zeros(len(blobs) + 1, dtype=np.int64)
    np.cumsum([len(b) for b in blobs], out=offsets[1:])
    data = np.frombuffer(b"".join(blobs), dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "wb") as f:
            np.savez(f, offsets=offsets, data=data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _cache_read(path: Path) -> list[BaseGeometry] | None:
    try:
        with np.load(path, allow_pickle=False) as z:
            offsets = z["offsets"]
            data = z["data"].tobytes()
        return [
            from_wkb(data[int(offsets[i]) : int(offsets[i + 1])]) for i in range(len(offsets) - 1)
        ]
    except Exception:
        return None  # missing or damaged: a miss, the caller re-slices and rewrites


# ---------------------------------------------------------------- public

def slice_stl(
    stl_path: str | Path,
    config: object,
    *,
    cache_dir: str | Path | None = None,
    use_cache: bool = True,
) -> LayerStack:
    """Slice ``stl_path`` into a ``LayerStack``. Read-only on the STL.

    ``cache_dir=None`` means ``DEFAULT_CACHE_DIR``. Raises ``SlicingError`` for unusable meshes
    and ``ValueError`` for unusable parameters.
    """
    params = _Params.from_config(config)
    params.validate()
    stl_bytes = Path(stl_path).read_bytes()

    geometries: list[BaseGeometry] | None = None
    cache_file: Path | None = None
    if use_cache:
        root = DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)
        cache_file = root / f"{_cache_key(stl_bytes, params)}.npz"
        geometries = _cache_read(cache_file)
    if geometries is None:
        mesh = _load_mesh(stl_bytes, params)
        geometries = _slice_layers(mesh, params)
        if cache_file is not None:
            try:
                _cache_write(cache_file, geometries)
            except OSError:
                pass  # e.g. a reader holds the file on Windows: skip the write, keep the result

    h, base = params.layer_height_mm, params.build_plane_z_mm
    layers = tuple(
        Layer(
            index=k,
            z_bottom=base + k * h,
            z_top=base + k * h + h,
            z_slice=base + (k + 0.5) * h,
            geometry=g,
            area_mm2=float(g.area),
        )
        for k, g in enumerate(geometries)
    )
    return LayerStack(layers=layers)
