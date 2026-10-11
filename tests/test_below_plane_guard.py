"""C-35: the build-plane guard of ``slicing._load_mesh`` agrees with the Validator.

Closed boxes (12 triangles each) whose lowest z is below the build plane by more than
``geometry_epsilon_mm`` / just across the threshold / less than it. The same STL file goes through
the Validator's ``load_target_mesh`` and our ``_load_mesh`` (STL bytes); both must reject or accept
alike, and for the reject cases with the expected codes.

STL stores float32. With this config the threshold ``build_plane - eps`` = -1e-6 is not a float32
value, so "exactly on the boundary" cannot be written to an STL. The boundary is therefore tested
with its two float32 neighbours: the largest float32 below the threshold (must be rejected) and
the smallest float32 at or above it (must be accepted). Each case asserts that the z_min read back
from the file lies on the intended side of the threshold.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh
from waam_validator.config.loader import load_config
from waam_validator.errors import TargetValidationError
from waam_validator.shape.target import load_target_mesh

from waam.slicing import SlicingError, _load_mesh, _Params

CONFIG = Path(__file__).parent / "fixtures" / "model01" / "config.yaml"


def _box_stl(path: Path, z_min: float) -> bytes:
    mesh = trimesh.creation.box(extents=(20.0, 20.0, 10.0))
    mesh.apply_translation([0.0, 0.0, z_min - mesh.bounds[0, 2]])
    mesh.export(path)
    return path.read_bytes()


def _outcome(call):
    try:
        call()
    except (TargetValidationError, SlicingError) as exc:
        return exc.code
    return None


_VALIDATOR_REJECT = "TARGET_TRAJECTORY_FRAME_MISMATCH"
_OUR_REJECT = "TARGET_BELOW_BUILD_PLANE"


def _cases(thr: float, eps: float):
    f32 = np.float32(thr)
    below = float(np.nextafter(f32, np.float32(-np.inf)))  # float32 neighbour under thr
    at_or_above = float(f32) if float(f32) >= thr else float(np.nextafter(f32, np.float32(np.inf)))
    return [
        ("over_eps", thr - 4.0 * eps, True),
        ("boundary_below", below, True),
        ("boundary_at_or_above", at_or_above, False),
        ("within_eps", thr + 0.5 * eps, False),
    ]


@pytest.mark.parametrize("label", ["over_eps", "boundary_below", "boundary_at_or_above", "within_eps"])
def test_guard_matches_validator(tmp_path, label):
    cfg = load_config(CONFIG)
    eps = cfg.collision.geometry_epsilon_mm
    thr = cfg.process.build_plane_z_mm - eps
    (_, z_min, reject), = [c for c in _cases(thr, eps) if c[0] == label]
    path = tmp_path / f"{label}.stl"
    data = _box_stl(path, z_min)
    read_back = float(trimesh.load(path, process=False).bounds[0, 2])
    assert (read_back < thr) == reject, (label, read_back, thr)

    validator = _outcome(lambda: load_target_mesh(path, cfg))
    ours = _outcome(lambda: _load_mesh(data, _Params.from_config(cfg)))

    assert (validator is not None) == reject, (label, read_back, validator)
    assert (ours is not None) == reject, (label, read_back, ours)
    if reject:
        assert validator == _VALIDATOR_REJECT and ours == _OUR_REJECT
