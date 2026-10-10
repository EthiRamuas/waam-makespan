"""results.csv schema (DECISIONS.md C-17): format, append-only, and the skills' own one-liners."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from vref import SAMPLE_JOB
from waam import results
from waam.results import COLUMNS, ResultRow, append_result, make_row, read_results

REPO = Path(__file__).resolve().parents[1]
SAMPLE_SUMMARY = next((SAMPLE_JOB / "output").glob("*/summary.json"))  # the Validator's own file


def _row(**kw):
    base = dict(model="01", algo="a", compute_s=1.5, seed=7, commit="abc1234",
                makespan_s=100.0, run_at="2026-10-10T15:00:00+09:00")
    base.update(kw)
    return make_row(**base)


def _synthetic_summary(tmp_path, status, makespan=50.0, version="1.0.1"):
    """TEST INPUT for the parser only (not a Validator result)."""
    p = tmp_path / f"summary_{status}.json"
    p.write_text(json.dumps({"status": status, "validator_version": version,
                             "schedule": {"makespan_s": makespan}}), encoding="utf-8")
    return p


# ------------------------------------------------------------------- columns / docs


def test_first_six_columns_are_the_skills_promise_and_docstring_defines_compute_s():
    assert COLUMNS[:6] == ("model", "algo", "makespan_s", "ratio", "compute_s", "passed")
    assert COLUMNS[6:] == ("run_at", "commit", "seed", "lower_bound_s", "validator_status",
                           "validator_version", "notes")
    assert "Validator's run time is NOT included" in results.__doc__
    assert "Our algorithm's run time" in results.__doc__


# --------------------------------------------------------------------- make_row


def test_passed_and_makespan_come_from_the_validators_summary_json_unprocessed():
    sj = json.loads(SAMPLE_SUMMARY.read_text(encoding="utf-8"))
    r = make_row("sample", "ref", compute_s=0.1, seed=0, commit="c", summary_path=SAMPLE_SUMMARY,
                 lower_bound_s=6.0)
    assert r.makespan_s == sj["schedule"]["makespan_s"] == 18.0  # taken as is
    assert r.validator_status == sj["status"] == "PASS" and r.passed is True
    assert r.validator_version == sj["validator_version"]
    assert r.ratio == 18.0 / 6.0 and r.lower_bound_s == 6.0


def test_non_pass_summary_gives_passed_false(tmp_path):
    r = make_row("m", "a", compute_s=0.0, seed=1, commit="c",
                 summary_path=_synthetic_summary(tmp_path, "FAIL"))
    assert r.passed is False and r.validator_status == "FAIL"


def test_no_validator_run_leaves_passed_and_validator_fields_empty():
    r = _row(lower_bound_s=50.0)
    assert r.passed is None and r.validator_status == "" and r.validator_version == ""
    assert r.ratio == 2.0


def test_ratio_is_empty_without_a_lower_bound():
    assert _row().ratio is None and _row().lower_bound_s is None


def test_summary_and_explicit_makespan_must_agree(tmp_path):
    s = _synthetic_summary(tmp_path, "PASS", makespan=50.0)
    make_row("m", "a", compute_s=1.0, seed=1, commit="c", summary_path=s, makespan_s=50.0)
    with pytest.raises(ValueError, match="differs from summary"):
        make_row("m", "a", compute_s=1.0, seed=1, commit="c", summary_path=s, makespan_s=51.0)


@pytest.mark.parametrize("kw", [
    dict(makespan_s=None), dict(makespan_s=0.0), dict(makespan_s=float("nan")),
    dict(compute_s=-1.0), dict(compute_s=float("inf")), dict(lower_bound_s=0.0),
    dict(model=""), dict(algo=""),
])
def test_bad_values_are_refused(kw):
    with pytest.raises(ValueError):
        _row(**kw)


# ------------------------------------------------------------------ append / read


def test_roundtrip_header_and_value_formats(tmp_path):
    p = tmp_path / "r" / "results.csv"
    rows = [_row(lower_bound_s=40.0, notes="a, b"), _row(model="02", seed=None)]
    for r in rows:
        append_result(p, r)
    assert read_results(p) == rows
    text = p.read_bytes().decode("utf-8")
    assert text.startswith(",".join(COLUMNS) + "\n") and "\r" not in text
    assert '"a, b"' in text  # commas in notes are quoted


def test_append_only_old_bytes_never_change(tmp_path):
    p = tmp_path / "results.csv"
    append_result(p, _row())
    before = p.read_bytes()
    append_result(p, _row(model="03", algo="b"))
    after = p.read_bytes()
    assert after.startswith(before) and after.count(b"\n") == before.count(b"\n") + 1


def test_header_mismatch_and_truncated_file_are_refused(tmp_path):
    p = tmp_path / "results.csv"
    p.write_text("model,algo\n01,a\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header differs"):
        append_result(p, _row())
    q = tmp_path / "trunc.csv"
    append_result(q, _row())
    q.write_bytes(q.read_bytes()[:-1])  # lose the final newline
    with pytest.raises(ValueError, match="incomplete"):
        append_result(q, _row())
    with pytest.raises(ValueError, match="header differs"):
        read_results(p)


# ------------------------------------------------- invariants (review of results.py)


@pytest.mark.parametrize("payload", [
    {"status": "ERROR", "validator_version": "1.0.1"},                       # error.json-like
    {"status": "PASS", "validator_version": "1.0.1"},                        # no schedule
    {"status": "PASS", "validator_version": "1.0.1", "schedule": None},
    {"status": "PASS", "validator_version": "1.0.1", "schedule": {"makespan_s": True}},
    {"status": "PASS", "validator_version": "1.0.1", "schedule": {"makespan_s": "5"}},
    {"status": "PASS", "schedule": {"makespan_s": 5.0}},                     # no version
    [],                                                                      # not an object
])
def test_malformed_or_non_validation_summary_is_refused(tmp_path, payload):
    p = tmp_path / "summary.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        make_row("m", "a", compute_s=1.0, seed=1, commit="c", summary_path=p, makespan_s=123.0)


def test_summary_without_makespan_never_borrows_the_callers_value(tmp_path):
    p = tmp_path / "summary.json"
    p.write_text(json.dumps({"status": "PASS", "validator_version": "1.0.1"}), encoding="utf-8")
    with pytest.raises(ValueError):
        make_row("m", "a", compute_s=1.0, seed=1, commit="c", summary_path=p, makespan_s=123.0)


def test_makespan_mismatch_threshold_is_tight(tmp_path):
    s = _synthetic_summary(tmp_path, "PASS", makespan=50.0)
    with pytest.raises(ValueError, match="differs from summary"):
        make_row("m", "a", compute_s=1.0, seed=1, commit="c", summary_path=s, makespan_s=50.001)


def test_passed_true_false_and_empty_roundtrip_with_literal_csv_values(tmp_path):
    p = tmp_path / "results.csv"
    rows = [make_row("m", "a", compute_s=1.0, seed=7, commit="c",
                     summary_path=_synthetic_summary(tmp_path, "PASS")),
            make_row("m", "b", compute_s=1.0, seed=8, commit="c",
                     summary_path=_synthetic_summary(tmp_path, "FAIL")),
            _row(seed=9)]
    for r in rows:
        append_result(p, r)
    back = read_results(p)
    assert back == rows and [r.passed for r in back] == [True, False, None]
    assert [r.seed for r in back] == [7, 8, 9]
    body = p.read_text(encoding="utf-8").split("\n")[1:4]
    assert [ln.split(",")[5] for ln in body] == ["True", "False", ""]  # not 1/0, not true/false


def test_read_results_refuses_bad_rows(tmp_path):
    p = tmp_path / "results.csv"
    append_result(p, _row())
    good = p.read_text(encoding="utf-8")
    short = tmp_path / "short.csv"
    short.write_text(good + "01,a,1.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cells"):
        read_results(short)
    bad_bool = tmp_path / "bad_bool.csv"
    cells = good.split("\n")[1].split(",")
    cells[5] = "yes"
    bad_bool.write_text(good.split("\n")[0] + "\n" + ",".join(cells) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_results(bad_bool)


def test_crlf_or_bom_file_is_refused_with_a_diagnosis(tmp_path):
    p = tmp_path / "results.csv"
    append_result(p, _row())
    crlf = tmp_path / "crlf.csv"
    crlf.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="CRLF or BOM"):
        append_result(crlf, _row())
    bom = tmp_path / "bom.csv"
    bom.write_bytes(b"\xef\xbb\xbf" + p.read_bytes())
    with pytest.raises(ValueError, match="CRLF or BOM"):
        append_result(bom, _row())


def _direct(**kw):
    base = dict(model="01", algo="a", makespan_s=10.0, ratio=None, compute_s=1.0, passed=None,
                run_at="t", commit="c", seed=None, lower_bound_s=None, validator_status="",
                validator_version="", notes="")
    base.update(kw)
    return ResultRow(**base)


@pytest.mark.parametrize("kw", [
    dict(passed=True),                                              # claims a verdict, no Validator
    dict(passed=False, validator_status="PASS", validator_version="1"),
    dict(passed=True, validator_status="FAIL", validator_version="1"),
    dict(passed=None, validator_status="PASS", validator_version="1"),
    dict(passed=True, validator_status="PASS", validator_version=""),
    dict(validator_status="ERROR", passed=False, validator_version="1"),
    dict(makespan_s=np.float64(5.0)),                                # numpy repr would be written
    dict(makespan_s=5),                                              # int
    dict(ratio=1.0),                                                 # ratio without lower bound
    dict(lower_bound_s=5.0),                                         # lower bound without ratio
    dict(lower_bound_s=5.0, ratio=3.0),                              # ratio != 10 / 5
    dict(seed=7.9), dict(seed=True),
    dict(notes="line1\nline2"), dict(notes="cr\rhere"), dict(model="0\n1"),
])
def test_result_row_refuses_false_or_unwritable_rows(kw):
    with pytest.raises(ValueError):
        _direct(**kw)


def test_result_row_accepts_a_consistent_row():
    r = _direct(lower_bound_s=5.0, ratio=2.0, passed=True, validator_status="PASS",
                validator_version="1.0.1", seed=3, notes="tab\tok, comma")
    assert r.ratio == 2.0


# ----------------------------------------------------- the skills' own one-liners


def _skill_snippets() -> dict[str, str]:
    """Every ``python -c`` one-liner of the skills that read results.csv, verbatim from the
    skill files Claude Code actually loads (.claude/skills/*/SKILL.md)."""
    found = {}
    for md in sorted((REPO / ".claude" / "skills").glob("*/SKILL.md")):
        for i, m in enumerate(re.finditer(r'!`python -c "(.*?)" 2>&1',
                                          md.read_text(encoding="utf-8"))):
            if "results.csv" in m.group(1):
                found[f"{md.parent.name}#{i}"] = m.group(1)
    return found


def _run_snippet(code: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], cwd=cwd, capture_output=True,
                          text=True, timeout=120)


def _populate(tmp_path, *, with_empty_ratio_pass=False):
    out = tmp_path / "experiments" / "results.csv"
    append_result(out, make_row("sample", "ref", compute_s=0.1, seed=0, commit="c",
                                summary_path=SAMPLE_SUMMARY, lower_bound_s=6.0))
    append_result(out, make_row("sample", "ref2", compute_s=0.2, seed=0, commit="c",
                                summary_path=SAMPLE_SUMMARY, lower_bound_s=9.0))
    append_result(out, _row(lower_bound_s=40.0))  # Validator not run: passed stays empty
    append_result(out, make_row("m2", "failed", compute_s=0.3, seed=0, commit="c",
                                summary_path=_synthetic_summary(tmp_path, "FAIL"),
                                lower_bound_s=10.0))
    if with_empty_ratio_pass:  # a PASS before lower_bound.py exists: ratio is empty
        append_result(out, make_row("m3", "noratio", compute_s=0.3, seed=0, commit="c",
                                    summary_path=SAMPLE_SUMMARY))
    return out


def test_all_skill_one_liners_exist_and_run_on_our_file(tmp_path):
    snippets = _skill_snippets()
    assert len(snippets) == 3, list(snippets)  # status x2, decide x1: a changed skill is noticed
    _populate(tmp_path)
    for name, code in snippets.items():
        proc = _run_snippet(code, tmp_path)
        assert proc.returncode == 0 and "Traceback" not in proc.stderr, (name, proc.stderr)


def test_best_per_model_picks_lowest_ratio_among_validator_pass_rows_only(tmp_path):
    _populate(tmp_path)
    code = next(c for c in _skill_snippets().values() if "idxmin" in c)
    out = _run_snippet(code, tmp_path).stdout
    # ref2 (18/9) beats ref (18/6); the not-run row and the FAIL row are not candidates
    assert "ref2" in out and out.count("ref") == 1 and "failed" not in out, out


def test_best_per_model_survives_a_pass_row_without_ratio(tmp_path):
    _populate(tmp_path, with_empty_ratio_pass=True)
    code = next(c for c in _skill_snippets().values() if "idxmin" in c)
    proc = _run_snippet(code, tmp_path)
    assert proc.returncode == 0 and "ref2" in proc.stdout


def test_best_per_model_with_only_ratioless_pass_rows_does_not_crash(tmp_path):
    out = tmp_path / "experiments" / "results.csv"
    append_result(out, make_row("m3", "noratio", compute_s=0.3, seed=0, commit="c",
                                summary_path=SAMPLE_SUMMARY))  # PASS, ratio empty
    code = next(c for c in _skill_snippets().values() if "idxmin" in c)
    proc = _run_snippet(code, tmp_path)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr


def test_skill_output_keeps_model_and_commit_as_text(tmp_path):
    out = tmp_path / "experiments" / "results.csv"
    append_result(out, make_row("01", "a", compute_s=0.3, seed=0, commit="1234e56",
                                summary_path=SAMPLE_SUMMARY, lower_bound_s=6.0))
    code = next(c for c in _skill_snippets().values() if "tail(10)" in c)
    shown = _run_snippet(code, tmp_path).stdout
    assert re.search(r"\b01\b", shown) and "1234e56" in shown, shown  # not 1 / 1.234e+59

