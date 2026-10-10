"""writer: format, linter (negative cases), gate, and golden runs through the real Validator."""

from __future__ import annotations

import numpy as np
import pytest
from waam_validator.config.loader import load_config
from waam_validator.constants import MODE_FROM_TEXT
from waam_validator.trajectory.loader import load_trajectory_csv

from test_timing import MODEL01_FIXTURE, _closed, _three_robot_chains
from vref import timelines_of, validator_verdict, write_csv
from waam import prevalidate as pv
from waam import writer
from waam.prevalidate import PrevalidateRules
from waam.segment import Mode

_CODE = {m: int(MODE_FROM_TEXT[m.value]) for m in Mode}  # the Validator's own mode codes
EDGES = ([30.0, 20.0, 10.0], [25.0, 25.0], [40.0])


@pytest.fixture(scope="module")
def cfg():
    path = MODEL01_FIXTURE / "config.yaml"
    if not path.exists():
        pytest.fail(f"{path} is required (DECISIONS.md C-05) but missing")
    return load_config(path)


@pytest.fixture(scope="module")
def rules(cfg):
    return PrevalidateRules.from_config(cfg)


@pytest.fixture()
def chains(cfg):
    return _three_robot_chains(cfg, EDGES)


@pytest.fixture()
def good(cfg, rules, chains, tmp_path):
    return writer.write_trajectory(tmp_path / "trajectory.csv", chains, rules,
                                   _closed(cfg, chains))


def _lines(path):
    return path.read_bytes().decode("utf-8").split("\n")[:-1]


def _lint_mutated(good, rules, tmp_path, fn):
    lines = _lines(good)
    fn(lines)
    bad = tmp_path / "bad.csv"
    bad.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return {i.code for i in writer.lint_csv(bad, rules)}


# ---------------------------------------------------------------------------- format


def test_golden_written_file_passes_validator(cfg, good):
    ok_v, reasons = validator_verdict(good, cfg)
    assert ok_v, reasons


def test_format_is_lf_utf8_no_bom_sorted_with_terminal_w_rows(good, chains):
    raw = good.read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\n")
    lines = _lines(good)
    assert lines[0] == "robot_id,time_s,x_mm,y_mm,z_mm,mode"
    assert len(lines) == 1 + sum(len(c) + 1 for c in chains.values())
    for rid in (1, 2, 3):
        rows = [ln.split(",") for ln in lines[1:] if ln.startswith(f"{rid},")]
        assert rows[-1][5] == "W" and float(rows[0][1]) == 0.0
        assert [r[5] for r in rows[:-1]] == [s.mode.value for s in chains[rid]]
    assert [int(ln[0]) for ln in lines[1:]] == sorted(int(ln[0]) for ln in lines[1:])


def test_bytes_match_long_tested_reference_format_and_are_deterministic(
        cfg, rules, chains, good, tmp_path):
    ref = write_csv(tmp_path / "ref.csv", chains).read_bytes().replace(b"\r\n", b"\n")
    assert good.read_bytes() == ref  # vref.write_csv drove the soundness tests (C-13=a)
    again = writer.write_trajectory(tmp_path / "again.csv", chains, rules, _closed(cfg, chains))
    assert again.read_bytes() == good.read_bytes()


def test_validator_loader_reads_back_exact_times_and_float32_coordinates(cfg, good, chains):
    ts = load_trajectory_csv(good, cfg)
    for rid in (1, 2, 3):
        segs = chains[rid]
        rt = ts.by_id(rid)
        want_t = [s.start_time_s for s in segs] + [segs[-1].end_time_s]
        want_xyz = [s.start_xyz_mm for s in segs] + [segs[-1].end_xyz_mm]
        assert rt.time_s.tolist() == want_t  # bit-exact float64
        assert np.array_equal(rt.xyz_mm, np.asarray(want_xyz, dtype=np.float32))
        assert rt.mode.tolist() == [_CODE[s.mode] for s in segs] + [_CODE[Mode.W]]


def test_file_is_clean_for_lint_and_path_is_returned(good, rules, tmp_path):
    assert good == tmp_path / "trajectory.csv" and good.is_file()
    assert writer.lint_csv(good, rules) == []


# ------------------------------------------------------------------------ lint negatives


def _first(lines, rid, mode=None, skip=0):
    idx = [i for i, ln in enumerate(lines) if ln.startswith(f"{rid},")
           and (mode is None or ln.endswith("," + mode))]
    return idx[skip]


def _set(lines, i, col, value):
    cells = lines[i].split(",")
    cells[col] = value
    lines[i] = ",".join(cells)


@pytest.mark.parametrize("name,expect,fn", [
    ("header_typo", "INVALID_CSV_HEADER", lambda L: L.__setitem__(0, L[0].replace("x_mm", "x"))),
    ("bad_mode", "INVALID_CSV_HEADER", lambda L: _set(L, 2, 5, "X")),
    ("short_row", "INVALID_CSV_HEADER", lambda L: L.__setitem__(2, ",".join(L[2].split(",")[:5]))),
    ("empty_cell", "NONFINITE_VALUE", lambda L: _set(L, 2, 2, "")),
    ("nan", "NONFINITE_VALUE", lambda L: _set(L, 2, 3, "nan")),
    ("overflow_f32", "NONFINITE_VALUE", lambda L: _set(L, 2, 2, "1e300")),
    ("bad_robot", "INVALID_ROBOT_ID", lambda L: _set(L, 2, 0, "4")),
    ("robot3_missing", "MISSING_ROBOT",
     lambda L: [L.pop(i) for i in sorted((i for i, ln in enumerate(L) if ln.startswith("3,")),
                                         reverse=True)]),
    ("robot_rows_swapped", "UNSORTED_TRAJECTORY",
     lambda L: L.insert(1, L.pop(_first(L, 2)))),
    ("time_decreasing", "UNSORTED_TRAJECTORY", lambda L: _set(L, _first(L, 1, skip=2), 1, "0.0")),
    ("duplicate_time", "DUPLICATE_TIMESTAMP",
     lambda L: _set(L, _first(L, 1, skip=1), 1, L[_first(L, 1)].split(",")[1])),
    ("first_time", "FIRST_TIME_NOT_ZERO", lambda L: _set(L, _first(L, 1), 1, "0.25")),
    ("final_not_w", "FINAL_MODE_NOT_W",
     lambda L: _set(L, max(i for i, ln in enumerate(L) if ln.startswith("1,")), 5, "T")),
    ("w_moves", "WAIT_POSITION_CHANGED",
     lambda L: _set(L, _first(L, 1, mode="W"), 2, "123.5")),
    ("d_zero_len", "DEPOSITION_ZERO_LENGTH", None),
    ("d_vertical", "DEPOSITION_VERTICAL_MOVE", None),
])
def test_lint_flags(good, rules, tmp_path, name, expect, fn):
    if name == "d_zero_len":
        def fn(L):  # next row of the first D copies its XY
            i = _first(L, 1, mode="D")
            nxt = L[i + 1].split(",")
            nxt[2:4] = L[i].split(",")[2:4]
            L[i + 1] = ",".join(nxt)
    if name == "d_vertical":
        def fn(L):
            i = _first(L, 1, mode="D")
            _set(L, i + 1, 4, repr(float(L[i].split(",")[4]) + 1.0))
    assert expect in _lint_mutated(good, rules, tmp_path, fn), name


def test_lint_flags_bom_crlf_missing_newline_and_non_utf8(good, rules, tmp_path):
    raw = good.read_bytes()
    cases = {"bom": (b"\xef\xbb\xbf" + raw, "UTF-8 BOM"),
             "crlf": (raw.replace(b"\n", b"\r\n"), "carriage return"),
             "no_final_newline": (raw[:-1], "missing final newline"),
             "latin1": (raw + b"\xff\n", "not UTF-8")}
    for name, (data, detail) in cases.items():
        p = tmp_path / f"{name}.csv"
        p.write_bytes(data)
        found = writer.lint_csv(p, rules)
        assert any(i.code == "INVALID_CSV_HEADER" and detail in i.detail for i in found), name


@pytest.mark.parametrize("name,col,value", [
    ("arabic_indic_robot_id", 0, "١"),
    ("fullwidth_robot_id", 0, "１"),
    ("underscore_in_number", 2, "-21_0.0"),
    ("trailing_space", 2, "-210.0 "),
    ("fullwidth_digits", 2, "１０.0"),
    ("float64_coordinate", 2, "0.1"),
    ("exponent_form_of_time", 1, "0.0e0"),
])
def test_lint_refuses_cells_the_validator_loader_would_refuse_or_not_in_writer_format(
        good, rules, tmp_path, name, col, value):
    lines = _lines(good)
    _set(lines, _first(lines, 1), col, value)
    bad = tmp_path / "bad.csv"
    bad.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    codes = {i.code for i in writer.lint_csv(bad, rules)}
    assert codes & {"FORMAT_CONTRACT", "INVALID_ROBOT_ID"}, (name, codes)


def test_lint_runs_prevalidate_on_the_file_and_finds_a_collision(good, rules, tmp_path):
    def move_r2_onto_r1(lines):  # robot 2 starts (a T row) on top of robot 1's start
        r1 = [ln.split(",") for ln in lines if ln.startswith("1,")][0]
        i = _first(lines, 2)
        c = lines[i].split(",")
        c[2:5] = r1[2:5]
        lines[i] = ",".join(c)

    codes = _lint_mutated(good, rules, tmp_path, move_r2_onto_r1)
    assert codes & {"ARM_ENVELOPE", "TCP_RADIUS"}, codes


# ----------------------------------------------------------------------------- the gate


def test_gate_rejects_open_timelines_without_creating_a_file(cfg, rules, chains, tmp_path):
    out = tmp_path / "x" / "t.csv"
    with pytest.raises(ValueError, match="not closed"):
        writer.write_trajectory(out, chains, rules, timelines_of(chains))
    assert not out.exists() and not list(tmp_path.rglob("*.tmp"))


def test_gate_rejects_colliding_schedule(cfg, rules, chains, tmp_path):
    from waam.segment import Segment
    bad = dict(chains)
    p = (-100.0, 0.0, 5.0)  # inside robot 2's reach, on top of robot 1's arm/TCP
    bad[2] = [Segment(2, Mode.W, 0.0, chains[2][-1].end_time_s, p, p)]
    tls = timelines_of(bad)
    for tl in tls:
        tl.closed = True  # bypass close_timeline (it would already refuse): the gate must too
    codes = {v.code.name for v in pv.check_all(rules, tls).violations}
    assert codes and codes <= {"ARM_ENVELOPE", "TCP_RADIUS"}, codes  # a collision, nothing else
    out = tmp_path / "t.csv"
    with pytest.raises(ValueError, match="ARM_ENVELOPE|TCP_RADIUS"):
        writer.write_trajectory(out, bad, rules, tls)
    assert not out.exists()


def test_gate_rejects_timelines_of_another_schedule(cfg, rules, chains, tmp_path):
    other = _three_robot_chains(cfg, ([30.0, 20.0], [25.0, 25.0], [40.0]))
    out = tmp_path / "t.csv"
    with pytest.raises(ValueError, match="not the schedule being written"):
        writer.write_trajectory(out, chains, rules, _closed(cfg, other))
    assert not out.exists()


def test_failed_lint_leaves_no_final_file_and_no_temp(cfg, rules, chains, tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "render_rows",
                        lambda c: ["robot_id,time_s,x_mm,y_mm,z_mm,mode", "1,0.0,1,2,3,Q"])
    out = tmp_path / "t.csv"
    with pytest.raises(ValueError, match="failed lint"):
        writer.write_trajectory(out, chains, rules, _closed(cfg, chains))
    assert not out.exists() and not list(tmp_path.glob("*.tmp"))


def test_existing_file_survives_a_rejected_write(cfg, rules, chains, good):
    before = good.read_bytes()
    with pytest.raises(ValueError):
        writer.write_trajectory(good, chains, rules, timelines_of(chains))
    assert good.read_bytes() == before


@pytest.mark.parametrize("bad", ["missing_robot", "wrong_owner"])
def test_render_rows_rejects_bad_chains(chains, bad):
    broken = dict(chains)
    if bad == "missing_robot":
        broken.pop(3)
    else:
        broken[1], broken[2] = chains[2], chains[1]
    with pytest.raises(ValueError):
        writer.render_rows(broken)


def _mapped(chain, *, dt=None, dxyz=None, mode_map=None):
    """Same seams, same segment count; only times / positions / modes differ."""
    from waam.segment import Segment
    f = (lambda t: t) if dt is None else (lambda t: t * (1.0 + dt))
    g = (lambda p: p) if dxyz is None else (lambda p: (p[0] + dxyz, p[1], p[2]))
    m = (lambda x: x) if mode_map is None else (lambda x: mode_map.get(x, x))
    return [Segment(s.robot_id, m(s.mode), f(s.start_time_s), f(s.end_time_s),
                    g(s.start_xyz_mm), g(s.end_xyz_mm)) for s in chain]


@pytest.mark.parametrize("what,kwargs,match", [
    ("times", {"dt": 1e-9}, "times differ"),
    ("positions", {"dxyz": 0.01}, "positions differ"),
    ("modes", {"mode_map": {Mode.D: Mode.T}}, "modes differ"),
    ("modes_w_to_t", {"mode_map": {Mode.W: Mode.T}}, "modes differ"),
])
def test_gate_rejects_same_length_chain_that_differs_from_the_timelines(
        cfg, rules, chains, tmp_path, what, kwargs, match):
    tls = _closed(cfg, chains)  # the validated schedule
    other = dict(chains)
    other[1] = _mapped(chains[1], **kwargs)  # same segment count and seams
    out = tmp_path / "t.csv"
    with pytest.raises(ValueError, match=match):
        writer.write_trajectory(out, other, rules, tls)
    assert not out.exists()


def test_gate_rejects_duplicate_robot_ids_in_timelines(cfg, rules, chains, tmp_path):
    tls = _closed(cfg, chains)
    with pytest.raises(ValueError):
        writer.write_trajectory(tmp_path / "t.csv", chains, rules, (tls[0], tls[0], tls[2]))


def test_failed_lint_keeps_an_existing_file_untouched(cfg, rules, chains, good, monkeypatch):
    before = good.read_bytes()
    monkeypatch.setattr(writer, "render_rows",
                        lambda c: ["robot_id,time_s,x_mm,y_mm,z_mm,mode", "1,0.0,1,2,3,Q"])
    with pytest.raises(ValueError, match="failed lint"):
        writer.write_trajectory(good, chains, rules, _closed(cfg, chains))
    assert good.read_bytes() == before and not list(good.parent.glob("*.tmp"))


def test_replace_failure_is_a_value_error_and_leaves_no_temp_file(
        cfg, rules, chains, good, monkeypatch):
    before = good.read_bytes()

    def boom(src, dst):
        raise PermissionError(5, "target is open in another process")

    monkeypatch.setattr(writer.os, "replace", boom)
    with pytest.raises(ValueError, match="cannot replace"):
        writer.write_trajectory(good, chains, rules, _closed(cfg, chains))
    assert good.read_bytes() == before and not list(good.parent.glob("*.tmp"))
