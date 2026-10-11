"""toolpath: per-layer cross-sections -> ordered deposition passes (docs/specs/toolpath.md).

``generate(stack, config, params)`` turns a ``LayerStack`` into a ``Toolpath``: per layer a list
of passes (``contour`` / ``hole`` / ``hatch`` / ``medial``) in canonical order (V9), each with its
bead footprint, length and the set of robots that reach every vertex. It assigns nothing, orders
nothing across robots and adds no travel or arc time (assign / schedule / timing own that).

Rules implemented (variable ids refer to the spec):
- contour = ring of ``P (-) o`` (V1, round join, chord <= ``chord_mm``), exterior ``contour`` CCW,
  inner rings ``hole`` CW (V19); ``n_c`` rings per boundary at ``o + i*s`` (V4, V5).
- hatch = parallel lines through ``H = P (-) (o + (n_c-1)s + w/2)`` (V8), 0 deg on even layers and
  90 deg on odd layers (V7). Neighbouring rows are joined by a straight connector when the
  connector bead stays inside ``P`` (V6); otherwise the pass is split.
- walls whose thickness is about ``w`` (V11): ``medial`` single pass (V12) or, as the fallback
  (``wall_mode="double"``, section 6), the ring of the wall zone eroded by ``w/2 - eps_w`` (the
  same line twice). Thinner regions get no pass; only their area is recorded (V10).
- passes with no common reachable robot are kept and counted (V17); a bead outside the workspace
  raises ``ToolpathError("WORKSPACE_VIOLATION")`` (V18).

``config`` is the Validator config or any object with the same attributes (duck typing, like
``slicing``). No model-specific constants or branches: every decision is a geometric rule.

Cache (``.cache/waam/toolpath/``, V21): the key hashes the layer geometries of the stack (they
fix the STL and the slicing parameters, which is why the STL hash itself is not needed), the
parameters, the cell and process values used, library versions, this source file and
``TOOLPATH_VERSION``. A failed cache write never fails ``generate``.
"""

from __future__ import annotations

import hashlib
import math
import os
import uuid
import warnings
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

import numpy as np
import shapely
from shapely import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
    STRtree,
    from_wkb,
    get_parts,
    to_wkb,
)
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from waam.geometry import CellGeometry, in_reach
from waam.slicing import LayerStack

TOOLPATH_VERSION = "toolpath-0"

# Default wall handling (spec section 6-2: switched globally, never per model).
DEFAULT_WALL_MODE: Literal["medial", "double"] = "medial"

_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "waam" / "toolpath"

_MAX_QUAD_SEGS = 4096
_MAX_ROBOTS = 8  # the cache stores the reach set of a pass as one byte
_MEDIAL_GRID_MM = 1e-6  # snapping grid for the medial edges (numerical, not a tuning knob)
_ROBUST_GRID_MM = 1e-6  # grid of the GEOS retry in _difference (numerical, not a tuning knob)
_KIND_CODES = {"contour": 0, "hole": 1, "hatch": 2, "medial": 3}
_KIND_NAMES = {v: k for k, v in _KIND_CODES.items()}
_KIND_STAGE = ("contour", "hole", "medial", "hatch")  # canonical order of V9


class ToolpathError(Exception):
    """A layer set that cannot be turned into passes. ``code`` names the failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class ToolpathParams:
    s_mm: float  # hatch / ring spacing, default w (C-29)
    o_mm: float  # contour offset, default w/2 (C-37, I1)
    n_c: int  # contour rings per boundary, default 1
    chord_mm: float  # arc chord bound, 0.1 (hypothesis)
    lift_dz_mm: float  # lift between passes, 2h (hypothesis, recorded only)
    eps_w_mm: float  # wall tolerance, 0.01 (V10, V11)
    wall_mode: Literal["medial", "double"]  # default DEFAULT_WALL_MODE (C-38)
    # V12 details chosen by the implementer (R3). All values are hypotheses, not measured optima.
    medial_sample_mm: float = 0.5  # boundary densification spacing before the Voronoi step
    medial_tol_mm: float = 0.02  # slack on the wall-zone test and on the distance window
    medial_simplify_mm: float = 0.01  # Douglas-Peucker tolerance of a medial chain
    medial_min_chain_mm: float = 0.0  # chains not longer than this are dropped
    connect_slack_mm: float = 0.001  # extra erosion for the V6 connector test
    zone_min_inradius_mm: float = 0.05  # a wall zone must hold a disc of this radius (slivers do not)

    @classmethod
    def from_config(cls, config: object) -> ToolpathParams:
        w = float(config.process.bead_width_mm)  # type: ignore[attr-defined]
        h = float(config.process.layer_height_mm)  # type: ignore[attr-defined]
        return cls(
            s_mm=w,
            o_mm=w / 2.0,
            n_c=1,
            chord_mm=0.1,
            lift_dz_mm=2.0 * h,
            eps_w_mm=0.01,
            wall_mode=DEFAULT_WALL_MODE,
        )

    def validate(self, bead_width_mm: float | None = None) -> None:
        for name in (
            "s_mm", "o_mm", "chord_mm", "lift_dz_mm", "eps_w_mm", "medial_sample_mm",
            "medial_tol_mm", "medial_simplify_mm", "medial_min_chain_mm", "connect_slack_mm",
            "zone_min_inradius_mm",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number, got {value!r}")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        for name in ("s_mm", "o_mm", "chord_mm", "medial_sample_mm"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be > 0, got {getattr(self, name)!r}")
        for name in (
            "eps_w_mm", "medial_tol_mm", "medial_simplify_mm", "medial_min_chain_mm",
            "connect_slack_mm", "zone_min_inradius_mm",
        ):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name} must be >= 0, got {getattr(self, name)!r}")
        if isinstance(self.n_c, bool) or not isinstance(self.n_c, int) or self.n_c < 1:
            raise ValueError(f"n_c must be an int >= 1, got {self.n_c!r}")
        if self.wall_mode not in ("medial", "double"):
            raise ValueError(f"wall_mode must be 'medial' or 'double', got {self.wall_mode!r}")
        if bead_width_mm is not None and self.eps_w_mm >= bead_width_mm / 2.0:
            raise ValueError("eps_w_mm must be smaller than w/2")


@dataclass(frozen=True, slots=True)
class Pass:
    layer: int
    z: float
    kind: Literal["contour", "hole", "hatch", "medial"]
    vertices: tuple[tuple[float, float], ...]  # closed rings repeat the first point at the end
    length: float
    footprint: BaseGeometry  # LineString(vertices).buffer(w/2), Validator resolution
    reachable_robots: frozenset[int]


@dataclass(frozen=True, slots=True)
class Toolpath:
    passes: tuple[Pass, ...]  # (layer, canonical order)
    params: ToolpathParams
    thin_lost_mm2: tuple[float, ...]  # per layer (V10)
    empty_reach_count: int
    medial_fallback_regions: int  # wall zones handled by the double fallback after an exception


# ---------------------------------------------------------------- context


@dataclass(frozen=True, slots=True)
class _Ctx:
    w: float
    h: float
    build: float
    tcp_ref: str
    buffer_res: int
    area_eps: float
    cell: CellGeometry

    @classmethod
    def from_config(cls, config: object) -> _Ctx:
        proc = config.process  # type: ignore[attr-defined]
        w = float(proc.bead_width_mm)
        h = float(proc.layer_height_mm)
        if not (math.isfinite(w) and w > 0.0 and math.isfinite(h) and h > 0.0):
            raise ValueError("bead_width_mm and layer_height_mm must be finite and > 0")
        tcp_ref = str(proc.tcp_z_reference)
        if tcp_ref not in ("center", "top"):
            raise ValueError(f"unsupported tcp_z_reference {tcp_ref!r}")
        cell = CellGeometry.from_config(config)
        if not 1 <= len(cell.base_xy) <= _MAX_ROBOTS:
            raise ValueError(f"1..{_MAX_ROBOTS} robots supported, got {len(cell.base_xy)}")
        return cls(
            w=w,
            h=h,
            build=float(proc.build_plane_z_mm),
            tcp_ref=tcp_ref,
            buffer_res=int(config.shape_validation.polygon_buffer_resolution),  # type: ignore[attr-defined]
            area_eps=float(config.shape_validation.area_epsilon_mm2),  # type: ignore[attr-defined]
            cell=cell,
        )

    def z_of(self, layer: int) -> float:
        # Validator layer_index.py: center -> build + (k + 0.5) h, top -> build + (k + 1) h
        offset = 0.5 if self.tcp_ref == "center" else 1.0
        return self.build + (layer + offset) * self.h


def _quad_segs(radius: float, chord: float) -> int:
    """Quarter-circle segments so that an arc of ``radius`` has chords <= ``chord``."""
    if radius <= 0.0:
        return 1
    x = chord / (2.0 * radius)
    if x >= 1.0:
        return 1
    theta = 2.0 * math.asin(x)
    return int(min(_MAX_QUAD_SEGS, max(1, math.ceil((math.pi / 2.0) / theta))))


# ---------------------------------------------------------------- small geometry helpers


def _polygons(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        out: list[Polygon] = []
        for part in geometry.geoms:
            out.extend(_polygons(part))
        return out
    return []


def _erode(geometry: BaseGeometry, distance: float, chord: float) -> BaseGeometry:
    if distance <= 0.0:
        return geometry
    return geometry.buffer(-distance, quad_segs=_quad_segs(distance, chord), join_style="round")


def _opening(geometry: BaseGeometry, radius: float, chord: float) -> BaseGeometry:
    if radius <= 0.0:
        return geometry
    eroded = _erode(geometry, radius, chord)
    if eroded.is_empty:
        return eroded
    return eroded.buffer(radius, quad_segs=_quad_segs(radius, chord), join_style="round")


def _difference(a: BaseGeometry, b: BaseGeometry) -> BaseGeometry:
    """``a - b``; when GEOS rejects the plain operation (a ring edge missing after two
    buffers), repeat it on a fixed 1e-6 mm grid, which is robust and far below any tolerance."""
    try:
        return a.difference(b)
    except shapely.errors.GEOSException:
        return shapely.difference(a, b, grid_size=_ROBUST_GRID_MM)


def _clean(coords: np.ndarray) -> np.ndarray:
    """Drop consecutive duplicate points (zero-length steps)."""
    arr = np.asarray(coords, dtype=np.float64)[:, :2]
    if len(arr) < 2:
        return arr
    keep = np.ones(len(arr), dtype=bool)
    keep[1:] = np.any(arr[1:] != arr[:-1], axis=1)
    return arr[keep]


def _path_length(arr: np.ndarray) -> float:
    if len(arr) < 2:
        return 0.0
    return float(np.hypot(*(arr[1:] - arr[:-1]).T).sum())


def _swap(geometry: BaseGeometry) -> BaseGeometry:
    """(x, y) -> (y, x): exact, its own inverse (hatching in the rotated frame)."""
    if geometry.is_empty:
        return geometry
    return shapely.transform(geometry, lambda c: c[:, ::-1])


# ---------------------------------------------------------------- contours


def _ring_passes(region: BaseGeometry, ctx: _Ctx, out: list[tuple[str, np.ndarray]]) -> None:
    for poly in sorted(_polygons(region), key=lambda g: g.bounds):
        poly = orient(poly, 1.0)  # exterior CCW, interiors CW (V19)
        if Polygon(poly.exterior).area > ctx.area_eps:
            ring = _clean(np.asarray(poly.exterior.coords))
            if len(ring) >= 4:
                out.append(("contour", ring))
        for inner in poly.interiors:
            if Polygon(inner).area > ctx.area_eps:
                ring = _clean(np.asarray(inner.coords))
                if len(ring) >= 4:
                    out.append(("hole", ring))


# ---------------------------------------------------------------- medial (V12)


def _medial_chains(
    poly: Polygon, zones: list[Polygon], ctx: _Ctx, p: ToolpathParams
) -> list[np.ndarray]:
    """Medial axis of the wall zones via the Voronoi diagram of the densified boundary.

    Only the boundary within ``w`` of a zone is used as sites: the medial axis of a zone depends
    on the boundary within about ``w/2`` of it, so the cut ends of the windowed boundary only
    affect Voronoi cells far from every zone.
    """
    zone_geom = shapely.union_all([z.buffer(p.medial_tol_mm) for z in zones])
    window = shapely.union_all([z.buffer(ctx.w) for z in zones])
    near_boundary = shapely.intersection(poly.boundary, window)
    dense_parts = [
        shapely.segmentize(g, p.medial_sample_mm)
        for g in get_parts(near_boundary)
        if isinstance(g, LineString) and not g.is_empty
    ]
    if not dense_parts:
        return []
    sites_xy = np.unique(
        np.concatenate([shapely.get_coordinates(g) for g in dense_parts]), axis=0
    )
    if len(sites_xy) < 3:
        return []
    edges = shapely.voronoi_polygons(shapely.MultiPoint(sites_xy), only_edges=True)
    coords, index = shapely.get_coordinates(get_parts(edges), return_index=True)
    if len(coords) < 2:
        return []
    same = index[1:] == index[:-1]
    starts, ends = coords[:-1][same], coords[1:][same]
    # Keep edges lying in the polygon (the rays that run on past it have an end outside) whose
    # middle is in a wall zone. The distance test below drops the cell edges that are not medial.
    inside = shapely.contains_xy(poly, starts[:, 0], starts[:, 1]) & shapely.contains_xy(
        poly, ends[:, 0], ends[:, 1]
    )
    if not inside.any():
        return []
    starts, ends = starts[inside], ends[inside]
    mids = 0.5 * (starts + ends)
    in_zone = shapely.contains_xy(zone_geom, mids[:, 0], mids[:, 1])
    if not in_zone.any():
        return []
    starts, ends, mids = starts[in_zone], ends[in_zone], mids[in_zone]

    # Exact distance to the (densified) boundary segments, mid and both ends.
    seg_parts = []
    for g in dense_parts:
        c = shapely.get_coordinates(g)
        if len(c) >= 2:
            seg_parts.append(shapely.linestrings(np.stack([c[:-1], c[1:]], axis=1)))
    tree = STRtree(np.concatenate(seg_parts))
    low = ctx.w / 2.0 - p.eps_w_mm - p.medial_tol_mm
    ok = np.ones(len(mids), dtype=bool)
    for pts in (mids, starts, ends):
        found, dist = tree.query_nearest(
            shapely.points(pts), return_distance=True, all_matches=False
        )
        full = np.full(len(pts), np.inf)
        full[found[0]] = dist
        ok &= full >= low
    if not ok.any():
        return []
    kept = shapely.linestrings(np.stack([starts[ok], ends[ok]], axis=1))
    # Snap to a fine grid so that edges meeting at one Voronoi vertex share it exactly, dissolve
    # duplicated pieces, then chain the edges between branch points.
    snapped = shapely.set_precision(MultiLineString(list(kept)), _MEDIAL_GRID_MM)
    merged = shapely.line_merge(shapely.union_all(get_parts(snapped)))
    chains: list[np.ndarray] = []
    for part in get_parts(merged):
        if not isinstance(part, LineString) or part.is_empty:
            continue
        if p.medial_simplify_mm > 0.0:
            part = part.simplify(p.medial_simplify_mm, preserve_topology=False)
        arr = _clean(np.asarray(part.coords))
        if len(arr) >= 2 and _path_length(arr) > p.medial_min_chain_mm:
            chains.append(arr)
    chains.sort(key=lambda a: (a[:, 0].min(), a[:, 1].min(), len(a)))
    return chains


def _double_rings(zones: list[Polygon], ctx: _Ctx, p: ToolpathParams) -> list[np.ndarray]:
    """Fallback b: ring of each wall zone eroded by w/2 - eps_w (the same line twice)."""
    out: list[np.ndarray] = []
    for zone in zones:
        eroded = _erode(zone, ctx.w / 2.0 - p.eps_w_mm, p.chord_mm)
        rings: list[tuple[str, np.ndarray]] = []
        _ring_passes(eroded, ctx, rings)
        # a wall sliver can be thinner than area_eps: keep its out-and-back ring anyway
        if not rings:
            for poly in _polygons(eroded):
                ring = _clean(np.asarray(orient(poly, 1.0).exterior.coords))
                if len(ring) >= 4 and _path_length(ring) > 0.0:
                    rings.append(("contour", ring))
        out.extend(r for _, r in rings)
    return out


# ---------------------------------------------------------------- hatching (V6, V7, V8)


def _hatch_component(
    comp: Polygon, connect_zone: BaseGeometry, s: float
) -> list[np.ndarray]:
    """Rows of one hatch-region component (already in the frame where rows are horizontal)."""
    xmin, ymin, xmax, ymax = comp.bounds
    height = ymax - ymin
    if height <= 0.0:
        return []
    n_rows = max(1, math.ceil(height / s - 1e-9))
    rows: list[list[tuple[float, float, float]]] = []  # per row: (x0, x1, y)
    for i in range(n_rows):
        y = min(ymin + s / 2.0 + i * s, ymax)
        line = LineString([(xmin - 1.0, y), (xmax + 1.0, y)])
        pieces: list[tuple[float, float, float]] = []
        for part in get_parts(shapely.intersection(line, comp)):
            if isinstance(part, LineString) and not part.is_empty:
                xs = np.asarray(part.coords)[:, 0]
                x0, x1 = float(xs.min()), float(xs.max())
                if x1 > x0:
                    pieces.append((x0, x1, y))
        pieces.sort()
        rows.append(pieces)

    chains: list[dict] = []
    prev_chains: list[dict] = []
    for pieces in rows:
        used: set[int] = set()
        cur_chains: list[dict] = []
        for x0, x1, y in pieces:
            best = None
            for ci, ch in enumerate(prev_chains):
                if ci in used:
                    continue
                end = ch["pts"][-1]
                target = (x1, y) if ch["dir"] > 0 else (x0, y)
                if target == end:
                    continue
                conn = LineString([end, target])
                if connect_zone.covers(conn):
                    cand = (conn.length, ci, target)
                    if best is None or cand[:2] < best[:2]:
                        best = cand
            if best is None:
                ch = {"pts": [(x0, y), (x1, y)], "dir": 1}
                chains.append(ch)
                cur_chains.append(ch)
            else:
                _, ci, target = best
                used.add(ci)
                ch = prev_chains[ci]
                if ch["dir"] > 0:  # ended on the right: enter this row on its right end
                    ch["pts"].extend([(x1, y), (x0, y)])
                    ch["dir"] = -1
                else:
                    ch["pts"].extend([(x0, y), (x1, y)])
                    ch["dir"] = 1
                cur_chains.append(ch)
        # chains that were not extended are finished; extended ones stay available
        prev_chains = cur_chains
    return [_clean(np.asarray(ch["pts"])) for ch in chains]


def _hatch_passes(
    poly: Polygon, region: BaseGeometry, layer: int, ctx: _Ctx, p: ToolpathParams
) -> list[np.ndarray]:
    if region.is_empty:
        return []
    rotate = layer % 2 == 1  # V7: even layers 0 deg (+x rows), odd layers 90 deg
    if rotate:
        poly, region = _swap(poly), _swap(region)  # type: ignore[assignment]
    zone = _erode(poly, ctx.w / 2.0 + p.connect_slack_mm, p.chord_mm)
    if not zone.is_empty:
        shapely.prepare(zone)
    out: list[np.ndarray] = []
    for comp in sorted(_polygons(region), key=lambda g: g.bounds):
        out.extend(_hatch_component(comp, zone, p.s_mm))
    if rotate:
        out = [a[:, ::-1].copy() for a in out]
    return out


# ---------------------------------------------------------------- one layer


def _layer_raw(
    geometry: BaseGeometry, layer: int, ctx: _Ctx, p: ToolpathParams
) -> tuple[list[tuple[str, np.ndarray]], float, int]:
    raw: list[tuple[str, np.ndarray]] = []
    thin_lost = 0.0
    fallbacks = 0
    r_lo = ctx.w / 2.0 - p.eps_w_mm
    r_hi = ctx.w / 2.0
    for poly in sorted(_polygons(geometry), key=lambda g: g.bounds):
        opened_lo = _opening(poly, r_lo, p.chord_mm)
        thin_lost += max(0.0, poly.area - opened_lo.area)

        for i in range(p.n_c):  # contour rings (V1, V4, V5)
            _ring_passes(_erode(poly, p.o_mm + i * p.s_mm, p.chord_mm), ctx, raw)

        zones: list[Polygon] = []
        if not opened_lo.is_empty:
            wall = _difference(opened_lo, _opening(poly, r_hi, p.chord_mm))
            # Slivers left by the two openings are not walls: a wall zone holds a disc of this radius.
            zones = sorted(
                (
                    z
                    for z in _polygons(wall)
                    if z.area > ctx.area_eps
                    and not _erode(z, p.zone_min_inradius_mm, p.chord_mm).is_empty
                ),
                key=lambda g: g.bounds,
            )
        if zones:
            if p.wall_mode == "medial":
                try:
                    chains = _medial_chains(poly, zones, ctx, p)
                    raw.extend(("medial", c) for c in chains)
                except Exception as exc:
                    warnings.warn(
                        f"layer {layer}: medial extraction failed ({type(exc).__name__}: "
                        f"{str(exc).splitlines()[0] if str(exc) else ''}); wall zone handled "
                        "by the double fallback",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    fallbacks += len(zones)
                    raw.extend(("contour", r) for r in _double_rings(zones, ctx, p))
            else:
                raw.extend(("contour", r) for r in _double_rings(zones, ctx, p))

        hatch_region = _erode(poly, p.o_mm + (p.n_c - 1) * p.s_mm + ctx.w / 2.0, p.chord_mm)
        raw.extend(("hatch", a) for a in _hatch_passes(poly, hatch_region, layer, ctx, p))
    return [(k, a) for k, a in raw if len(a) >= 2 and _path_length(a) > 0.0], thin_lost, fallbacks


def _order_layer(
    raw: list[tuple[str, np.ndarray]], start: np.ndarray | None
) -> tuple[list[tuple[str, np.ndarray]], np.ndarray | None]:
    """Canonical order (V9): contour -> hole -> medial -> hatch, nearest next pass each time."""
    if not raw:
        return [], start
    if start is None:
        allv = np.concatenate([a for _, a in raw])
        start = allv[np.lexsort((allv[:, 1], allv[:, 0]))[0]]
    cur = np.asarray(start, dtype=np.float64)
    ordered: list[tuple[str, np.ndarray]] = []
    for stage in _KIND_STAGE:
        pool = [a for k, a in raw if k == stage]
        if not pool:
            continue
        closed = [bool(len(a) >= 4 and np.all(a[0] == a[-1])) for a in pool]
        # Candidate start points: every vertex of a ring, both ends of an open path.
        rows = [a[:-1] if c else a[[0, -1]] for a, c in zip(pool, closed)]
        owner = np.concatenate([np.full(len(r), i) for i, r in enumerate(rows)])
        first = np.cumsum([0] + [len(r) for r in rows])
        cand = np.concatenate(rows)
        live = np.ones(len(cand), dtype=bool)
        for _ in range(len(pool)):
            d = np.hypot(cand[:, 0] - cur[0], cand[:, 1] - cur[1])
            d[~live] = np.inf
            j = int(np.argmin(d))
            i = int(owner[j])
            local = j - int(first[i])
            arr = pool[i]
            if closed[i]:
                ring = arr[:-1]
                arr = np.concatenate([np.roll(ring, -local, axis=0), ring[local : local + 1]])
            elif local == 1:
                arr = arr[::-1]
            live[first[i] : first[i + 1]] = False
            ordered.append((stage, arr))
            cur = arr[-1]
    return ordered, cur


# ---------------------------------------------------------------- finalising


def _finalise(
    layer: int, kind: str, arr: np.ndarray, ctx: _Ctx
) -> tuple[Pass, bool]:
    cell = ctx.cell
    r = np.hypot(*(arr - cell.ws_center_xy).T)
    if float(r.max()) + ctx.w / 2.0 > cell.ws_radius_mm + cell.eps_mm:
        raise ToolpathError(
            "WORKSPACE_VIOLATION",
            f"layer {layer} {kind} pass: bead reaches {float(r.max()) + ctx.w / 2.0:.6g} mm "
            f"from the workspace centre, limit {cell.ws_radius_mm:.6g} mm",
        )
    n_robots = len(cell.base_xy)
    robots = frozenset(
        rid for rid in range(1, n_robots + 1) if bool(np.all(in_reach(cell, rid, arr)))
    )
    footprint = LineString(arr).buffer(
        ctx.w / 2.0, quad_segs=ctx.buffer_res, cap_style="round", join_style="round"
    )
    return (
        Pass(
            layer=layer,
            z=ctx.z_of(layer),
            kind=kind,  # type: ignore[arg-type]
            vertices=tuple((float(x), float(y)) for x, y in arr),
            length=_path_length(arr),
            footprint=footprint,
            reachable_robots=robots,
        ),
        not robots,
    )


def _compute(stack: LayerStack, ctx: _Ctx, p: ToolpathParams) -> Toolpath:
    passes: list[Pass] = []
    thin: list[float] = []
    empty = 0
    fallbacks = 0
    cur: np.ndarray | None = None
    for layer in stack.layers:
        raw, lost, fb = _layer_raw(layer.geometry, layer.index, ctx, p)
        thin.append(lost)
        fallbacks += fb
        ordered, cur = _order_layer(raw, cur)
        for kind, arr in ordered:
            one, is_empty = _finalise(layer.index, kind, arr, ctx)
            passes.append(one)
            empty += int(is_empty)
    return Toolpath(
        passes=tuple(passes),
        params=p,
        thin_lost_mm2=tuple(thin),
        empty_reach_count=empty,
        medial_fallback_regions=fallbacks,
    )


# ---------------------------------------------------------------- cache (V21)


def _cache_key(stack: LayerStack, ctx: _Ctx, p: ToolpathParams) -> str:
    h = hashlib.sha256()
    for layer in stack.layers:
        h.update(repr((layer.index, layer.z_bottom, layer.z_top, layer.z_slice)).encode())
        h.update(to_wkb(layer.geometry))
    cell = ctx.cell
    h.update(
        repr(
            (
                [getattr(p, f.name) for f in fields(p)],
                cell.base_xy.tolist(), cell.reach_mm.tolist(), cell.eps_mm,
                cell.ws_center_xy.tolist(), cell.ws_radius_mm,
                ctx.w, ctx.h, ctx.build, ctx.tcp_ref, ctx.buffer_res, ctx.area_eps,
                TOOLPATH_VERSION, shapely.__version__, shapely.geos_version_string,
                np.__version__, _SOURCE_SHA256,
            )
        ).encode()
    )
    return h.hexdigest()


def _cache_write(path: Path, tp: Toolpath) -> None:
    passes = tp.passes
    nv = np.array([len(q.vertices) for q in passes], dtype=np.int64)
    verts = (
        np.concatenate([np.asarray(q.vertices, dtype=np.float64) for q in passes])
        if passes
        else np.zeros((0, 2))
    )
    blobs = [to_wkb(q.footprint) for q in passes]
    offsets = np.zeros(len(blobs) + 1, dtype=np.int64)
    np.cumsum([len(b) for b in blobs], out=offsets[1:])
    reach = np.array(
        [sum(1 << (r - 1) for r in q.reachable_robots) for q in passes], dtype=np.uint8
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "wb") as f:
            np.savez(
                f,
                layer=np.array([q.layer for q in passes], dtype=np.int64),
                z=np.array([q.z for q in passes], dtype=np.float64),
                kind=np.array([_KIND_CODES[q.kind] for q in passes], dtype=np.uint8),
                length=np.array([q.length for q in passes], dtype=np.float64),
                nv=nv,
                verts=verts,
                reach=reach,
                fp_offsets=offsets,
                fp_data=np.frombuffer(b"".join(blobs), dtype=np.uint8),
                thin=np.array(tp.thin_lost_mm2, dtype=np.float64),
                counts=np.array([tp.empty_reach_count, tp.medial_fallback_regions], dtype=np.int64),
            )
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _cache_read(path: Path, p: ToolpathParams, n_robots: int) -> Toolpath | None:
    try:
        with np.load(path, allow_pickle=False) as z:
            layer, zz, kind = z["layer"], z["z"], z["kind"]
            length, nv, verts = z["length"], z["nv"], z["verts"]
            reach, offsets, data = z["reach"], z["fp_offsets"], z["fp_data"].tobytes()
            thin, counts = z["thin"], z["counts"]
        passes: list[Pass] = []
        pos = 0
        for i in range(len(layer)):
            v = verts[pos : pos + int(nv[i])]
            pos += int(nv[i])
            passes.append(
                Pass(
                    layer=int(layer[i]),
                    z=float(zz[i]),
                    kind=_KIND_NAMES[int(kind[i])],  # type: ignore[arg-type]
                    vertices=tuple((float(a), float(b)) for a, b in v),
                    length=float(length[i]),
                    footprint=from_wkb(data[int(offsets[i]) : int(offsets[i + 1])]),
                    reachable_robots=frozenset(
                        r + 1 for r in range(n_robots) if int(reach[i]) >> r & 1
                    ),
                )
            )
        return Toolpath(
            passes=tuple(passes),
            params=p,
            thin_lost_mm2=tuple(float(x) for x in thin),
            empty_reach_count=int(counts[0]),
            medial_fallback_regions=int(counts[1]),
        )
    except Exception:
        return None  # missing or damaged: a miss, the caller recomputes and rewrites


# ---------------------------------------------------------------- public


def generate(
    stack: LayerStack,
    config: object,
    params: ToolpathParams | None = None,
    *,
    cache_dir: str | Path | None = None,
    use_cache: bool = True,
) -> Toolpath:
    """Passes for every layer of ``stack``. Deterministic; raises ``ToolpathError`` / ``ValueError``."""
    ctx = _Ctx.from_config(config)
    p = params if params is not None else ToolpathParams.from_config(config)
    p.validate(ctx.w)

    cache_file: Path | None = None
    if use_cache:
        root = DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)
        cache_file = root / f"{_cache_key(stack, ctx, p)}.npz"
        cached = _cache_read(cache_file, p, len(ctx.cell.base_xy))
        if cached is not None:
            return cached
    result = _compute(stack, ctx, p)
    if cache_file is not None:
        try:
            _cache_write(cache_file, result)
        except OSError:
            pass  # e.g. a reader holds the file on Windows: skip the write, keep the result
    return result
