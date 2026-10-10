"""lower_bound_from_areas (docs/specs/lower_bound.md; DECISIONS.md C-22, L-1..L-5): oracles 1, 3, 4, 5
and the synthetic part of 6. The wrapper over a LayerStack and oracles 2, 7 wait for slicing."""

from __future__ import annotations

import inspect
import io
import math
import re
import tokenize
from pathlib import Path

import numpy as np
import pytest

from vref import SAMPLE_JOB
from waam import lower_bound as lb_module
from waam import results
from waam.lower_bound import LowerBound, lower_bound_from_areas

KW = dict(bead_width_mm=8.0, deposition_speed_mm_s=8.0, n_robots=3)
SRC = Path(lb_module.__file__)

# ---- Model 05 total cross-section area, two sources that must not be confused:
# * SPEC_AREA_05: docs/specs/lower_bound.md section 5, TABLE value 15,543,072.6 mm^2 (rounded to
#   one decimal; the bullet text of the same section gives 15,543,072.6076), measured with the
#   Validator's slicing functions.
# * MEASURED_AREA_05: the full-precision value of the same quantity measured directly on
#   2026-10-10 with the Validator's load_target_mesh + slice_target_layers (scratch probe
#   lb_probe05.py, which summed with sum()), NOT with our own slicing. An independent
#   re-measurement with math.fsum gave 15543072.607622316 (relative difference ~4e-16), so the
#   constant is reproduced to rel 1e-12, not bit for bit. Resulting bound: 80953.50316469959 s.
SPEC_AREA_05 = 15_543_072.6
MEASURED_AREA_05 = 15_543_072.607622322
MEASURED_LB_05_S = 80953.50316469959


# ------------------------------------------------------------------------ oracle 1


def test_synthetic_hand_computed_values():
    r = lower_bound_from_areas([800, 800], **KW)
    assert isinstance(r, LowerBound)
    assert r.total_area_mm2 == 1600.0 and r.centerline_mm == 200.0
    assert r.deposition_s == 25.0 and r.n_robots == 3
    assert r.lower_bound_s == pytest.approx(25.0 / 3.0, rel=1e-15)


@pytest.mark.parametrize("robots,want", [(1, 25.0), (2, 12.5), (3, 25.0 / 3.0), (4, 6.25)])
def test_robot_count_is_an_argument_not_a_constant(robots, want):
    kw = dict(KW, n_robots=robots)
    assert lower_bound_from_areas([800, 800], **kw).lower_bound_s == pytest.approx(want, rel=1e-15)


def test_each_returned_field_uses_the_right_parameter():
    # asymmetric width / speed / robots: a swapped or mixed-up parameter changes a field
    r = lower_bound_from_areas([1000.0, 600.0], bead_width_mm=4.0, deposition_speed_mm_s=16.0,
                               n_robots=5)
    assert r.total_area_mm2 == 1600.0
    assert r.centerline_mm == 1600.0 / 4.0 == 400.0
    assert r.deposition_s == 400.0 / 16.0 == 25.0
    assert r.lower_bound_s == 25.0 / 5 == 5.0


def test_bead_width_and_speed_scale_the_bound_as_defined():
    base = lower_bound_from_areas([1600.0], **KW).lower_bound_s
    assert lower_bound_from_areas([1600.0], **dict(KW, bead_width_mm=4.0)).lower_bound_s \
        == pytest.approx(2 * base, rel=1e-15)
    assert lower_bound_from_areas([1600.0], **dict(KW, deposition_speed_mm_s=16.0)).lower_bound_s \
        == pytest.approx(base / 2, rel=1e-15)
    assert lower_bound_from_areas([3200.0], **KW).lower_bound_s == pytest.approx(2 * base, rel=1e-15)


def test_areas_are_summed_exactly_and_input_types_are_accepted():
    assert lower_bound_from_areas([0.1] * 10, **KW).total_area_mm2 == 1.0  # fsum, not sum()
    r = lower_bound_from_areas((a for a in [np.float64(800.0), np.float32(800.0), 0]), **KW)
    assert r.total_area_mm2 == 1600.0
    assert lower_bound_from_areas(np.array([800.0, 800.0]), **KW).total_area_mm2 == 1600.0
    got = lower_bound_from_areas([800, 800], **dict(KW, n_robots=np.int64(2)))
    assert got.n_robots == 2 and type(got.n_robots) is int
    assert lower_bound_from_areas([800, 800], **KW) == lower_bound_from_areas([800, 800], **KW)
    assert all(type(getattr(r, f)) is float for f in
               ("total_area_mm2", "centerline_mm", "deposition_s", "lower_bound_s"))


# ------------------------------------------------------------------------ oracle 3


@pytest.mark.parametrize("areas", [
    [-1.0, 5.0], [float("nan")], [float("inf")], [float("-inf"), 1.0], [True, 5.0],
    [np.bool_(True)], [np.timedelta64(3)], ["5"], [None], [], [0.0, 0.0],
    {0: 800.0, 349: 900.0}, {800.0, 800.0}, "800", b"800",           # keys / duplicates / text
    800.0, None, 5,                                                  # not a collection
    [10 ** 400], [1e308, 1e308],                                     # out of float range
    [5e-324],                                                        # sum > 0 but bound underflows to 0
    iter(()),                                                        # an exhausted iterator is empty
])
def test_bad_areas_are_refused(areas):
    with pytest.raises(ValueError):
        lower_bound_from_areas(areas, **KW)


def test_a_layer_to_area_mapping_is_refused_not_summed_by_key():
    # slice_target_layers returns {layer_index: geometry}; summing its keys would give a
    # plausible but wrong bound (0 + 349 = 349 mm^2)
    with pytest.raises(ValueError, match="ordered collection"):
        lower_bound_from_areas({0: 800.0, 349: 900.0}, **KW)


@pytest.mark.parametrize("kw", [
    dict(bead_width_mm=0.0), dict(bead_width_mm=-8.0), dict(bead_width_mm=float("nan")),
    dict(bead_width_mm=float("inf")), dict(bead_width_mm=True), dict(bead_width_mm=10 ** 400),
    dict(deposition_speed_mm_s=0.0), dict(deposition_speed_mm_s=-1.0),
    dict(deposition_speed_mm_s=float("nan")), dict(deposition_speed_mm_s=float("inf")),
    dict(deposition_speed_mm_s=True),
    dict(n_robots=0), dict(n_robots=-3), dict(n_robots=2.5), dict(n_robots=3.0),
    dict(n_robots=True), dict(n_robots=np.bool_(True)), dict(n_robots="3"), dict(n_robots=None),
    dict(n_robots=10 ** 400), dict(n_robots=np.timedelta64(3)),
])
def test_bad_parameters_are_refused(kw):
    with pytest.raises(ValueError):
        lower_bound_from_areas([800.0], **dict(KW, **kw))


@pytest.mark.parametrize("areas,kw", [
    ([1e308], dict(bead_width_mm=1e-10)),                    # centerline overflows to inf
    ([1e-300], dict(bead_width_mm=1e10, deposition_speed_mm_s=1e10)),  # subnormal result
])
def test_a_result_that_is_not_finite_and_positive_is_refused(areas, kw):
    with pytest.raises(ValueError):
        lower_bound_from_areas(areas, **dict(KW, **kw))


# ------------------------------------------------------------------------ oracle 4


def test_model_05_unit_is_seconds_not_hours():
    # the two area values agree to 1e-9 (checked before this test was written: 4.9e-10)
    assert math.isclose(SPEC_AREA_05, MEASURED_AREA_05, rel_tol=1e-9)
    r = lower_bound_from_areas([MEASURED_AREA_05], **KW)
    assert r.lower_bound_s == pytest.approx(MEASURED_LB_05_S, rel=1e-12)
    assert r.lower_bound_s / 3600.0 == pytest.approx(22.4871, abs=5e-5)  # hours; spec table: 22.5
    # the rounded spec value gives the same bound to the precision of the area agreement
    s = lower_bound_from_areas([SPEC_AREA_05], **KW)
    assert s.lower_bound_s == pytest.approx(r.lower_bound_s, rel=1e-9)


# ------------------------------------------------------------------------ oracle 5

# Bound values of docs/spec.md section 6 (hours) and section 5 of the spec (seconds). They must
# not be literals of the module. Text rule: a value is a match only when no digit or dot touches
# it (14.8, 122.5, 0.085, 10.08 are not matches); trailing zeros and an omitted leading 0 do not
# hide a value (4.80, 0.180, .46).
SPEC_TABLE_VALUES = (
    r"(?<![\d.])(?:0?\.080*|0?\.180*|0?\.140*|4\.80*|22\.50*|0?\.460*"          # hours
    r"|304\.30*|661\.50*|513\.70*|17_?346\.40*|80_?953\.50*|1_?656\.60*)(?![\d.])"  # seconds
)
SPEC_NUMBERS = {0.08, 0.18, 0.14, 4.8, 22.5, 0.46, 304.3, 661.5, 513.7, 17346.4, 80953.5, 1656.6}


@pytest.mark.parametrize("text", ["14.8", "122.5", "0.085", "10.08", "x14.8y", "4.85", "0.081",
                                  "122.55", "1.0.46", "40.46", "4.8.1", "4x8", "304.35", "1304.3",
                                  "180953.5", "80_953.51", "17_346.45"])
def test_boundary_regex_has_no_false_positives(text):
    assert re.search(SPEC_TABLE_VALUES, text) is None, text


@pytest.mark.parametrize("text", ["4.8", "22.5", "0.08", "0.18", "0.14", "0.46",
                                  "h = 4.8 s", "(22.5)", "x=0.46,", "[0.08]", "4.8 h",
                                  "0.1800", "4.80", ".46", "0.080", "22.50", "80953.5", "80_953.5",
                                  "17_346.4", "17346.40", "_M05 = 80953.5", "304.3", "1656.6"])
def test_boundary_regex_catches_standalone_values(text):
    assert re.search(SPEC_TABLE_VALUES, text) is not None, text


def _number_literals(source: str) -> set[float]:
    out = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.NUMBER:
            try:
                out.add(float(tok.string.replace("_", "")))
            except ValueError:
                pass
    return out


@pytest.mark.parametrize("source,found", [("x = 22.5e0", True), ("x = 0.080", True), ("x = .46", True),
                                         ("x = 17_346.4", True), ("x = 4.8", True),
                                         ("x = 14.8", False), ("x = 8.0", False), ("'4.8'", False)])
def test_numeric_literal_scan_catches_spellings_the_text_rule_may_miss(source, found):
    assert bool(_number_literals(source) & SPEC_NUMBERS) is found, source


def test_source_has_no_model_specific_bound_constants():
    text = SRC.read_text(encoding="utf-8")
    assert re.search(SPEC_TABLE_VALUES, text) is None
    assert not (_number_literals(text) & SPEC_NUMBERS)


def test_docstrings_state_definition_and_limits_only():
    text = SRC.read_text(encoding="utf-8")
    doc = lb_module.__doc__ + (lower_bound_from_areas.__doc__ or "")
    assert "ratio < 1" in doc and "clamp" in doc.lower() and "SECONDS" in doc
    assert "not part of the bound" in doc  # arc time
    # C-24: no statement about a coverage strategy, in either language
    for phrase in ("취한다", "취하지", "strategy", "policy", "exploit", "we do not", "we will",
                   "coverage"):
        assert phrase not in text.lower(), phrase
    assert "n_robots" in inspect.signature(lower_bound_from_areas).parameters


# --------------------------------------------------------- oracle 6, synthetic part


def test_ratio_below_one_is_recorded_without_clamping_or_rejection(tmp_path):
    lb = lower_bound_from_areas([800, 800], **KW)  # 8.33.. s
    row = results.make_row("synthetic", "x", compute_s=0.0, seed=0, commit="c",
                           trajectory_path=SAMPLE_JOB / "trajectory.csv",
                           makespan_s=5.0, lower_bound_s=lb.lower_bound_s)
    assert row.ratio == pytest.approx(5.0 / lb.lower_bound_s) and row.ratio < 1.0
    path = tmp_path / "results.csv"
    results.append_result(path, row)
    assert results.read_results(path)[0].ratio == row.ratio  # stored as is
    # and above one it is the plain quotient too
    above = results.make_row("synthetic", "y", compute_s=0.0, seed=0, commit="c",
                             trajectory_path=SAMPLE_JOB / "trajectory.csv",
                             makespan_s=10.0, lower_bound_s=lb.lower_bound_s)
    assert above.ratio == pytest.approx(1.2)
