"""lower_bound(stack, config): oracles 2, 6, 7 of docs/specs/lower_bound.md (wrapper over slicing).

Oracle 2 has two parts, with tolerances fixed by what each reference prints (not tuned):
- Validator-derived: the layer areas from the Validator's own ``load_target_mesh`` +
  ``slice_target_layers``, put through the same pure formula; relative error 1e-9.
- Spec table (section 5): the printed seconds / hours are rounded; compared within half a unit
  of the last printed digit.
"""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from waam_validator.config.loader import load_config
from waam_validator.shape.target import (
    determine_evaluation_layers,
    load_target_mesh,
    slice_target_layers,
)

from waam import results
from waam.lower_bound import LowerBound, lower_bound, lower_bound_from_areas
from waam.slicing import slice_stl

VALIDATOR_TESTS = Path("C:/Github/WAAM_Validator/tests")
SAMPLE_TRAJ = Path(__file__).parent / "fixtures" / "sample_job" / "trajectory.csv"

# (seconds printed in the spec section 5 table, decimals printed) and the spec.md table hours
# (value, decimals printed). Test data only; never in src/.
TABLE_S = {"01": (304.3, 1), "02": (661.5, 1), "03": (513.7, 1),
           "04": (17346.4, 1), "05": (80953.5032, 4), "06": (1656.6, 1)}
TABLE_H = {"01": (0.08, 2), "02": (0.18, 2), "03": (0.14, 2),
           "04": (4.8, 1), "05": (22.5, 1), "06": (0.46, 2)}


@pytest.fixture(scope="module")
def models():
    cache: dict[str, tuple] = {}

    def get(name: str):
        if name not in cache:
            d = VALIDATOR_TESTS / name
            cfg = load_config(d / "config.yaml")
            cache[name] = (d / "target.stl", cfg, slice_stl(d / "target.stl", cfg, use_cache=False))
        return cache[name]

    return get


@pytest.mark.parametrize("name", sorted(TABLE_S))
def test_wrapper_equals_validator_derived_lower_bound(models, name):
    stl, cfg, stack = models(name)
    mesh = load_target_mesh(stl, cfg)
    idx = determine_evaluation_layers(mesh, {}, cfg)  # the Validator's own layer list
    assert stack.layer_count == len(idx)
    theirs = slice_target_layers(mesh, idx, cfg)
    ref = lower_bound_from_areas(
        [theirs[k].area for k in idx],
        bead_width_mm=cfg.process.bead_width_mm,
        deposition_speed_mm_s=cfg.process.deposition_speed_mm_s,
        n_robots=len(cfg.robots),
    )
    got = lower_bound(stack, cfg)
    assert isinstance(got, LowerBound)
    assert got.lower_bound_s == pytest.approx(ref.lower_bound_s, rel=1e-9, abs=0.0)
    assert got.n_robots == len(cfg.robots) == 3


@pytest.mark.parametrize("name", sorted(TABLE_S))
def test_wrapper_matches_the_printed_spec_tables(models, name):
    _, cfg, stack = models(name)
    got = lower_bound(stack, cfg).lower_bound_s
    s, s_dec = TABLE_S[name]
    h, h_dec = TABLE_H[name]
    assert abs(got - s) <= 0.5 * 10 ** (-s_dec), (name, got, s)
    assert abs(got / 3600.0 - h) <= 0.5 * 10 ** (-h_dec), (name, got / 3600.0, h)


def test_model_05_is_80953_5032_seconds_and_in_seconds_not_hours(models):
    _, cfg, stack = models("05")
    got = lower_bound(stack, cfg).lower_bound_s
    assert got == pytest.approx(80953.5032, abs=5e-5)  # seconds; unit checks: test_lower_bound.py


# ---------------------------------------------------------------- oracle 7


def _stack(areas):
    return SimpleNamespace(layers=[SimpleNamespace(area_mm2=a) for a in areas])


def _cfg(n_robots, bead=8.0, speed=8.0):
    return SimpleNamespace(
        robots=[object()] * n_robots,
        process=SimpleNamespace(bead_width_mm=bead, deposition_speed_mm_s=speed),
    )


def test_synthetic_stack_three_robots():
    got = lower_bound(_stack([800.0, 800.0]), _cfg(3))
    assert got.centerline_mm == pytest.approx(200.0)
    assert got.deposition_s == pytest.approx(25.0)
    assert got.lower_bound_s == pytest.approx(25.0 / 3.0)


@pytest.mark.parametrize("n,expected", [(2, 12.5), (4, 6.25), (1, 25.0)])
def test_robot_count_is_len_of_robots_not_a_constant(n, expected):
    got = lower_bound(_stack([800.0, 800.0]), _cfg(n))
    assert got.n_robots == n
    assert got.lower_bound_s == pytest.approx(expected)


def test_robots_may_be_a_tuple_and_process_values_are_used():
    cfg = SimpleNamespace(robots=(1, 2, 3, 4, 5),
                          process=SimpleNamespace(bead_width_mm=4.0, deposition_speed_mm_s=10.0))
    got = lower_bound(_stack([100.0]), cfg)
    assert got.lower_bound_s == pytest.approx(100.0 / 4.0 / 10.0 / 5.0)
    # bead and speed are interchangeable in lower_bound_s; these two fields tell them apart
    assert got.centerline_mm == pytest.approx(100.0 / 4.0)
    assert got.deposition_s == pytest.approx(25.0 / 10.0)


def test_real_validator_config_gives_three_robots(models):
    _, cfg, stack = models("01")
    assert lower_bound(stack, cfg).n_robots == 3


@pytest.mark.parametrize(
    "stack,cfg",
    [
        (_stack([]), _cfg(3)),                       # no layers
        (_stack([0.0, 0.0]), _cfg(3)),               # total area 0
        (_stack([-1.0]), _cfg(3)),
        (_stack([float("nan")]), _cfg(3)),
        (_stack([100.0]), _cfg(0)),                  # no robots
        (_stack([100.0]), _cfg(3, bead=0.0)),
        (_stack([100.0]), _cfg(3, speed=-1.0)),
        (object(), _cfg(3)),                         # no .layers
        (SimpleNamespace(layers=None), _cfg(3)),
        (SimpleNamespace(layers=5), _cfg(3)),
        (_stack([100.0]), SimpleNamespace(robots="abc", process=SimpleNamespace(
            bead_width_mm=8.0, deposition_speed_mm_s=8.0))),
        (_stack([100.0]), SimpleNamespace(robots={"a": 1}, process=SimpleNamespace(
            bead_width_mm=8.0, deposition_speed_mm_s=8.0))),
        (_stack([100.0]), SimpleNamespace(process=SimpleNamespace(bead_width_mm=8.0,
                                                                   deposition_speed_mm_s=8.0))),
        (_stack([100.0]), SimpleNamespace(robots=7, process=SimpleNamespace(
            bead_width_mm=8.0, deposition_speed_mm_s=8.0))),  # robots has no len
        (_stack([100.0]), SimpleNamespace(robots=[1])),     # no .process
    ],
)
def test_bad_inputs_raise_value_error(stack, cfg):
    with pytest.raises(ValueError):
        lower_bound(stack, cfg)


# ---------------------------------------------------------------- oracle 6


def test_result_row_ratio_uses_wrapper_value_and_ratio_below_one_is_kept(models):
    _, cfg, stack = models("01")
    lb = lower_bound(stack, cfg).lower_bound_s
    row = results.make_row("01", "wrapper-test", compute_s=0.1, seed=1, commit="abc1234",
                           trajectory_path=SAMPLE_TRAJ, lower_bound_s=lb, makespan_s=2.0 * lb)
    assert row.lower_bound_s == lb
    assert row.ratio == pytest.approx(2.0)
    below = results.make_row("01", "wrapper-test", compute_s=0.1, seed=1, commit="abc1234",
                             trajectory_path=SAMPLE_TRAJ, lower_bound_s=lb, makespan_s=0.9 * lb)
    assert below.ratio == pytest.approx(0.9) and math.isfinite(below.ratio)
    assert below.ratio < 1.0  # recorded, not rejected or clamped (L-1)
