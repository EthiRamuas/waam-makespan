"""Stage 1 exit check (DECISIONS.md C-14): Step -> build_chain -> write_trajectory -> the real
``waam-validator run`` on a complete job directory, exit code 0 and status PASS.

The job is the sample_job reference (same target.stl and config.yaml, copied unchanged into a
temp directory) re-created through OUR pipeline. The trajectory.csv is not compared byte for
byte with the reference: it is timed by our rules (travel at the configured speed, not the
reference's hand-picked times).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from waam_validator.config.loader import load_config

from vref import SAMPLE_JOB
from waam import prevalidate as pv
from waam import writer
from waam.prevalidate import PrevalidateRules
from waam.timing import Step, TimingParams, build_chain


def _validator_exe() -> str:
    # only the venv's own executable: a same-named one elsewhere on PATH could be another version
    exe = Path(sys.executable).parent / ("waam-validator.exe" if sys.platform == "win32"
                                         else "waam-validator")
    if not exe.exists():
        pytest.fail(f"{exe} not found: run the tests with the project venv")
    return str(exe)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# the sample_job inputs as shipped with the Validator (examples/sample_job); they must not drift
SAMPLE_MD5 = {"config.yaml": "f19ca946804c0c57e4398ad1b24456f2",
              "target.stl": "3b4fd2a248961a0815763c1dbb6e7d64"}


def test_sample_job_recreated_through_our_pipeline_passes_waam_validator_run(tmp_path):
    cfg = load_config(SAMPLE_JOB / "config.yaml")
    rules = PrevalidateRules.from_config(cfg)

    # 레퍼런스 재현용, 제출 경로 아님.
    # REFERENCE REPRODUCTION ONLY, NOT A SUBMISSION PATH: this config has no arc_on/arc_off
    # and its reference trajectory has no arc W rows, so the arc times are set to 0 here, in
    # this test file only. src/ and TimingParams.from_config still refuse a config without
    # arc times (the arc rule is never relaxed for a real model).
    p = cfg.process
    ref_params = TimingParams(float(p.deposition_speed_mm_s), float(p.travel_speed_mm_s), 0.0, 0.0)

    home1, home2, home3 = (-1000.0, -600.0, 100.0), (1000.0, -600.0, 100.0), (0.0, 1200.0, 100.0)
    a, b = (-40.0, 0.0, 2.0), (40.0, 0.0, 2.0)  # the reference's single deposition pass
    chain1 = build_chain(1, home1, [Step("travel", (a,)), Step("pass", (a, b)),
                                    Step("travel", (home1,))], ref_params)
    done = chain1[-1].end_time_s
    chains = {1: chain1,
              2: build_chain(2, home2, [Step("wait", duration_s=done)], ref_params),
              3: build_chain(3, home3, [Step("wait", duration_s=done)], ref_params)}

    timelines = pv.new_timelines()
    for rid in (1, 2, 3):
        for seg in chains[rid]:
            assert pv.try_append(rules, timelines, seg).ok, (rid, seg)
        assert pv.close_timeline(rules, timelines, rid).ok

    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(SAMPLE_JOB / "config.yaml", job / "config.yaml")  # unchanged inputs
    shutil.copy(SAMPLE_JOB / "target.stl", job / "target.stl")
    for name, want in SAMPLE_MD5.items():
        assert _md5(job / name) == want, f"{name} differs from the shipped sample_job"
    writer.write_trajectory(job / "trajectory.csv", chains, rules, timelines)

    out = tmp_path / "validator_out"
    proc = subprocess.run([_validator_exe(), "run", str(job), "--output", str(out), "--json"],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PASS"
    # sample_job's config only WARNS on speed violations (fail_on_speed_violation: false), so
    # PASS alone cannot see a timing regression: no issue of any kind is allowed here
    assert summary["issues"] == [], summary["issues"]
    # what the Validator recorded is what we scheduled (no processing of the value)
    assert summary["schedule"]["makespan_s"] == pytest.approx(done, rel=1e-12)
    print(f"\nwaam-validator {summary['validator_version']} run: status={summary['status']} "
          f"makespan_s={summary['schedule']['makespan_s']} (summary.json)")
