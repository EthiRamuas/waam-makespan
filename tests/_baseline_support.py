"""Shared helpers for the baseline part-1 tests (config-like fakes, model loading)."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

from waam_validator.config.loader import load_config

from waam import toolpath as tp
from waam.slicing import slice_stl

FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "model01" / "config.yaml"
VALIDATOR_TESTS = Path("C:/Github/WAAM_Validator/tests")
MODELS = ["01", "02", "03", "04", "05", "06"]
SLOW = {"02", "04", "05"}


def fake_cfg(cfg, bases_deg, dist=1400.0, reach=1500.0, origin=(0.0, 0.0)):
    """A config-like object with robots on a circle of radius ``dist`` at the given angles."""
    robots = []
    for i, a in enumerate(bases_deg):
        x = origin[0] + dist * math.cos(math.radians(a))
        y = origin[1] + dist * math.sin(math.radians(a))
        robots.append(SimpleNamespace(
            id=i + 1, base_xyz_mm=(x, y, 0.0), home_xyz_mm=(0.5 * x, 0.5 * y, 1000.0),
            tcp_radius_mm=100.0, arm_envelope_radius_mm=100.0, xy_reach_radius_mm=reach))
    ws = SimpleNamespace(shape="circle_xy", center_xy_mm=origin, radius_mm=cfg.workspace.radius_mm)
    return SimpleNamespace(robots=tuple(robots), collision=cfg.collision, workspace=ws,
                           process=cfg.process, shape_validation=cfg.shape_validation)


def _pass(vertices, layer=0, z=1.0, kind="hatch", reach=frozenset()):
    v = [tuple(map(float, p)) for p in vertices]
    n = sum(math.dist(a, b) for a, b in zip(v[:-1], v[1:]))
    return SimpleNamespace(layer=layer, z=z, kind=kind, vertices=tuple(v), length=n,
                           reachable_robots=frozenset(reach))


_MODEL_CACHE: dict[str, tuple] = {}


def load_model(name):
    if name not in _MODEL_CACHE:
        c = load_config(VALIDATOR_TESTS / name / "config.yaml")
        stack = slice_stl(VALIDATOR_TESTS / name / "target.stl", c)
        _MODEL_CACHE[name] = (c, tp.generate(stack, c))
    return _MODEL_CACHE[name]
