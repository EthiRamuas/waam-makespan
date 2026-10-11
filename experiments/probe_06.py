"""probe_06: model 06 on robot 1 alone, one real Validator run (docs/specs/probe_driver.md, C-41).

    python -m experiments.probe_06 [--source-dir PATH] [--run-id ID]

Plumbing only: slice -> toolpath v0 defaults -> robot-1 chain -> parked robots 2 and 3 ->
prevalidate -> write_trajectory -> ``waam-validator run`` -> results.csv row + probe.json.
It is NOT a submission algorithm (C-31). Nothing here changes ``src/waam``; the Validator is
imported only to score our own footprints (P18). The knobs s, o, n_c, wall_mode do not exist (P3).

Exit codes (P22): 0 PASS and P18 within tolerance | 1 shape FAIL | 2 retries exhausted or
non-shape FAIL/error | 3 abort before a verdict (P2, P4, P12, P13, P15) | 4 PASS but P18 mismatch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:  # same convention as tests/conftest.py
    sys.path.insert(0, str(REPO / "src"))

from shapely import union_all  # noqa: E402
from waam_validator.config.loader import load_config  # noqa: E402
from waam_validator.shape.metrics import compute_shape_metrics  # noqa: E402
from waam_validator.shape.polygon_utils import normalize_polygon  # noqa: E402

from waam import prevalidate as pv  # noqa: E402
from waam import results, writer  # noqa: E402
from waam.lower_bound import lower_bound  # noqa: E402
from waam.prevalidate import PrevalidateRules, Timeline  # noqa: E402
from waam.segment import Segment, Xyz  # noqa: E402
from waam.slicing import slice_stl  # noqa: E402
from waam.timing import Step, TimingParams, build_chain  # noqa: E402
from waam.toolpath import Toolpath, ToolpathParams, generate  # noqa: E402

MODEL = "06"
ALGO = "probe_v0_robot1_only"  # D8
DEFAULT_SOURCE_DIR = Path("C:/Github/WAAM_Validator/tests/06")
PROBE_ROOT = REPO / ".cache" / "waam" / "probe"
RESULTS_CSV = REPO / "experiments" / "results.csv"
EXPECTED_CONFIG_MD5 = "bf3b30c6e762bcc93ff44d8f80bcb46d"
TIMEOUT_S = 1800.0  # D3, hypothesis
PARK_LAMBDAS = (0.0, 0.25, 0.5, 0.75, 1.0)  # D5, hypothesis
TOLERANCE = 0.005  # D14, hypothesis
RETRY_BUDGET = 3  # D18: 3 retries, at most 4 attempts
A1_FAST_WALL_S = 120.0  # P21
RATIO_NOTE = "ratio=ours, 3-robot lower bound, 1-robot probe"
INPUT_FILES = ("config.yaml", "target.stl")

EXIT_PASS, EXIT_SHAPE, EXIT_EXHAUSTED, EXIT_ABORT, EXIT_MISMATCH = 0, 1, 2, 3, 4

# P17: the 13 items results.csv cannot hold (plus the timing split of D7)
PROBE_JSON_KEYS = (
    "coverage", "overfill", "iou", "layer_iou_min", "failed_layer_count", "robot_dtw_s",
    "collision_event_count", "validator_wall_s", "compute_s", "git_commit", "git_dirty",
    "chain_rows", "trajectory_sha256",
    "slicing_s", "toolpath_s", "chain_s",
)


class ProbeAbort(Exception):
    """Stop before a Validator verdict exists. ``code`` is the PROBE_* name of the spec."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code, self.detail = code, detail


class ProbeValidatorTimeout(ProbeAbort):
    def __init__(self, wall_s: float) -> None:
        super().__init__("PROBE_VALIDATOR_TIMEOUT", f"no verdict after {wall_s:.1f} s")
        self.wall_s = wall_s


class FailureClass(str, Enum):
    PASS = "PASS"
    SHAPE = "SHAPE"
    COLLISION = "COLLISION"
    CSV = "CSV"
    SPEED = "SPEED"
    REACH = "REACH"
    OTHER = "OTHER"


# --------------------------------------------------------------------------- helpers


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _f32_equal(a: Xyz, b: Xyz) -> bool:
    return bool((pv.quantize_f32(a) == pv.quantize_f32(b)).all())


def _jsonable(o):
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"{type(o).__name__} is not JSON serialisable")


def _write_json(path: Path, obj: dict) -> None:
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=_jsonable),
                          encoding="utf-8")


def git_info(repo: Path = REPO) -> tuple[str, bool]:
    """(short HEAD hash, working tree dirty) -- D10."""
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                              check=True).stdout.strip()
    return run("rev-parse", "--short", "HEAD"), bool(run("status", "--porcelain"))


# --------------------------------------------------------------------------- P5-P7 chain


def build_robot1_steps(toolpath: Toolpath, home_xyz: Xyz, lift_dz_mm: float) -> list[Step]:
    """Robot-1 steps in ``Toolpath.passes`` order; lift - horizontal - descend between passes."""
    steps: list[Step] = []
    cur: Xyz = tuple(float(c) for c in home_xyz)  # type: ignore[assignment]
    for k, q in enumerate(toolpath.passes):
        pts: tuple[Xyz, ...] = tuple((float(x), float(y), float(q.z)) for x, y in q.vertices)
        start = pts[0]
        if not _f32_equal(start, cur):
            if k == 0:  # P6: home is already high; diagonal to above the start, then descend
                steps.append(Step("travel", ((start[0], start[1], start[2] + lift_dz_mm),)))
            else:
                z_lift = max(cur[2], start[2]) + lift_dz_mm
                steps.append(Step("travel", ((cur[0], cur[1], z_lift),)))
                steps.append(Step("travel", ((start[0], start[1], z_lift),)))
            steps.append(Step("travel", (start,)))
        steps.append(Step("pass", pts))
        cur = pts[-1]
    return steps


def robot1_chain(config, toolpath: Toolpath, timing: TimingParams) -> list[Segment]:
    home = _robot(config, 1).home_xyz_mm
    steps = build_robot1_steps(toolpath, home, toolpath.params.lift_dz_mm)
    return build_chain(1, home, steps, timing)


def _robot(config, robot_id: int):
    return next(r for r in config.robots if r.id == robot_id)


# --------------------------------------------------------------------------- P11-P12 parking


def park_candidates(config, robot_id: int) -> list[Xyz]:
    """home + lambda (base - home) in XY, z = home z (D5, hypothesis)."""
    r = _robot(config, robot_id)
    hx, hy, hz = (float(c) for c in r.home_xyz_mm)
    bx, by = float(r.base_xyz_mm[0]), float(r.base_xyz_mm[1])
    return [(hx + lam * (bx - hx), hy + lam * (by - hy), hz) for lam in PARK_LAMBDAS]


def park_chain(rid: int, xyz: Xyz, t_end: float, timing: TimingParams) -> list[Segment]:
    return build_chain(rid, xyz, [Step("wait", duration_s=t_end)], timing)


def assemble_chains(config, toolpath: Toolpath, park_choice: dict[int, Xyz],
                    timing: TimingParams | None = None) -> dict[int, list[Segment]]:
    timing = timing or TimingParams.from_config(config)
    c1 = robot1_chain(config, toolpath, timing)
    t_end = c1[-1].end_time_s
    return {1: c1, 2: park_chain(2, park_choice[2], t_end, timing),
            3: park_chain(3, park_choice[3], t_end, timing)}


@dataclass(frozen=True, slots=True)
class Plan:
    chains: dict[int, list[Segment]]
    timelines: tuple[Timeline, Timeline, Timeline]
    park_index: dict[int, int]  # robot -> index into park_candidates


def plan_parking(config, rules: PrevalidateRules, chain1: list[Segment], timing: TimingParams,
                 first_candidate: int = 0) -> Plan:
    """Robot 1 first (closed), then each parked robot on its first collision-free candidate."""
    tls = [Timeline(1), Timeline(2), Timeline(3)]
    for seg in chain1:
        v = pv.try_append(rules, tuple(tls), seg)
        if not v.ok:
            raise ProbeAbort("PROBE_PREVALIDATE", f"robot 1 chain rejected: {v}")
    v = pv.close_timeline(rules, tuple(tls), 1)
    if not v.ok:
        raise ProbeAbort("PROBE_PREVALIDATE", f"robot 1 cannot be closed: {v}")
    t_end = chain1[-1].end_time_s
    chains = {1: chain1}
    chosen: dict[int, int] = {}
    for rid in (2, 3):
        cands = park_candidates(config, rid)
        for idx in range(first_candidate, len(cands)):
            chain = park_chain(rid, cands[idx], t_end, timing)
            tl = Timeline(rid)
            tls[rid - 1] = tl
            if all(pv.try_append(rules, tuple(tls), s).ok for s in chain) \
                    and pv.close_timeline(rules, tuple(tls), rid).ok:
                chains[rid], chosen[rid] = chain, idx
                break
            tls[rid - 1] = Timeline(rid)
        else:
            raise ProbeAbort("PROBE_PARK_NONE", f"robot {rid}: no collision-free parking candidate")
    final = pv.check_all(rules, tuple(tls))
    if not final.ok:
        raise ProbeAbort("PROBE_PARK_NONE", f"final check failed: {final.verdict}")
    return Plan(chains, tuple(tls), chosen)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- P2, P14, P15


def make_job_dir(source_dir: Path, run_id: str, root: Path = PROBE_ROOT) -> Path:
    source_dir, job = Path(source_dir), Path(root) / run_id
    for name in INPUT_FILES:
        if not (source_dir / name).is_file():
            raise ProbeAbort("PROBE_INPUT", f"{source_dir / name} not found")
    if job.exists():
        raise ProbeAbort("PROBE_RUN_EXISTS", f"{job} already exists (never overwritten)")
    job.mkdir(parents=True)
    for name in INPUT_FILES:
        shutil.copyfile(source_dir / name, job / name)
        if _sha256(job / name) != _sha256(source_dir / name):
            raise ProbeAbort("PROBE_INPUT_COPY", f"{name} differs after copy")
    return job


def validator_exe() -> Path:
    exe = Path(sys.executable).parent / ("waam-validator.exe" if sys.platform == "win32"
                                         else "waam-validator")
    if not exe.exists():
        raise ProbeAbort("PROBE_VALIDATOR_EXE", f"{exe} not found: use the project venv")
    return exe


def run_validator(job_dir: Path, timeout_s: float = TIMEOUT_S) -> tuple[int, float]:
    """``waam-validator run <job> --output <job>/validator_out --json`` -> (exit code, wall s)."""
    job_dir = Path(job_dir)
    cmd = [str(validator_exe()), "run", str(job_dir), "--output", str(job_dir / "validator_out"),
           "--json"]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise ProbeValidatorTimeout(time.perf_counter() - t0) from exc
    wall = time.perf_counter() - t0
    (job_dir / "validator_stdout.json").write_text(proc.stdout, encoding="utf-8")
    if proc.stderr:
        (job_dir / "validator_stderr.txt").write_text(proc.stderr, encoding="utf-8")
    return proc.returncode, wall


# --------------------------------------------------------------------------- outputs, P18


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_validator_outputs(out_dir: Path) -> dict:
    """summary.json (as parsed), layer_metrics.csv and robot_metrics.csv rows, error.json."""
    out_dir = Path(out_dir)

    def load(name: str):
        p = out_dir / name
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return {"summary": load("summary.json"), "error": load("error.json"),
            "layers": _read_csv(out_dir / "layer_metrics.csv"),
            "robots": _read_csv(out_dir / "robot_metrics.csv")}


_SPEED_CODES = ("DEPOSITION_SPEED_VIOLATION", "TRAVEL_SPEED_VIOLATION")
_REACH_CODES = ("PROBE_REACH", "ROBOT_XY_REACH_VIOLATION")
_CONTRACT_CODES = tuple(c.name for c in pv.Code
                        if 3 <= c.value <= 7 or 30 <= c.value <= 34) + ("ArithmeticError",)


def classify_failure(outputs: dict) -> FailureClass:
    """§6. Fields are used, not the (unconfirmed) text format of ``failure_reasons``."""
    summary, error = outputs.get("summary"), outputs.get("error")
    if not isinstance(summary, dict) or summary.get("status") not in ("PASS", "FAIL"):
        text = json.dumps(error, ensure_ascii=False) if error is not None else ""
        if any(c in text for c in _SPEED_CODES):
            return FailureClass.SPEED
        if any(c in text for c in _REACH_CODES):
            return FailureClass.REACH
        if any(c in text for c in _CONTRACT_CODES):
            return FailureClass.CSV
        return FailureClass.OTHER
    if summary["status"] == "PASS":
        return FailureClass.PASS

    def passed(key: str) -> bool:
        sec = summary.get(key)
        return not (isinstance(sec, dict) and sec.get("passed") is False)

    if not passed("shape"):
        return FailureClass.SHAPE
    if not passed("reach"):
        return FailureClass.REACH
    if not passed("collision"):
        return FailureClass.COLLISION
    texts = [json.dumps(summary.get("failure_reasons", []), ensure_ascii=False)]
    codes = [str(i.get("code")) for i in summary.get("issues", [])
             if isinstance(i, dict) and i.get("severity") != "warning"]
    blob = " ".join(texts + codes)
    if any(c in blob for c in _SPEED_CODES):
        return FailureClass.SPEED
    if any(c in blob for c in _CONTRACT_CODES):
        return FailureClass.CSV
    return FailureClass.OTHER


def own_shape_metrics(stack, toolpath: Toolpath, config):
    """Footprint union per layer, normalised as the Validator does, scored by its own function."""
    sv = config.shape_validation
    deposited = {}
    for k in range(stack.layer_count):
        fps = [q.footprint for q in toolpath.passes if q.layer == k]
        if fps:
            deposited[k] = normalize_polygon(union_all(fps), sv.polygon_snap_tolerance_mm,
                                             sv.area_epsilon_mm2)
    return compute_shape_metrics(deposited, {l.index: l.geometry for l in stack.layers}, config)


def own_layer_metrics(stack, toolpath: Toolpath, config) -> list:
    return own_shape_metrics(stack, toolpath, config)[1]


@dataclass(slots=True)
class Comparison:
    ok: bool
    max_abs_err: float
    mismatches: list[dict] = field(default_factory=list)
    own_layers: int = 0
    validator_layers: int = 0


_COMPARED = ("coverage", "overfill_ratio", "iou")


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    return float(v)


def compare_layers(own, validator_rows, tol: float = TOLERANCE, *,
                   own_overall: dict | None = None,
                   validator_overall: dict | None = None) -> Comparison:
    """Per layer (and overall, if given): |own - Validator| <= tol for coverage, overfill, iou."""
    mism: list[dict] = []
    worst = 0.0
    own_by = {int(m.layer_index): m for m in own}
    val_by = {int(r["layer_index"]): r for r in validator_rows}

    def check(where, name, a, b):
        nonlocal worst
        if a is None or b is None:
            if a is not b:
                mism.append({"where": where, "metric": name, "own": a, "validator": b})
            return
        err = abs(a - b)
        worst = max(worst, err)
        if not err <= tol:
            mism.append({"where": where, "metric": name, "own": a, "validator": b, "err": err})

    for k in sorted(set(own_by) | set(val_by)):
        if k not in own_by or k not in val_by:
            mism.append({"where": f"layer {k}", "metric": "presence",
                         "own": k in own_by, "validator": k in val_by})
            continue
        for name in _COMPARED:
            check(f"layer {k}", name, _num(getattr(own_by[k], name)), _num(val_by[k][name]))
    if own_overall is not None and validator_overall is not None:
        for name in _COMPARED:
            check("overall", name, _num(own_overall.get(name)), _num(validator_overall.get(name)))
    return Comparison(not mism, worst, mism, len(own_by), len(val_by))


def a1_points(wall_s: float) -> int:
    """P21: 10 sweep points if one Validator run took <= 120 s, else 5."""
    return 10 if wall_s <= A1_FAST_WALL_S else 5


# --------------------------------------------------------------------------- probe.json


def _dtw(robots: list[dict]) -> dict:
    out = {}
    for r in robots:
        out[str(r["robot_id"])] = {"D": _num(r["deposition_time_s"]), "T": _num(r["travel_time_s"]),
                                   "W": _num(r["wait_time_s"])}
    return out


def validator_items(outputs: dict) -> dict:
    """Items for probe.json, copied from the Validator files without processing."""
    s = outputs.get("summary") or {}
    shape, coll = s.get("shape") or {}, s.get("collision") or {}
    ious = [_num(r["iou"]) for r in outputs.get("layers", [])]
    return {"coverage": shape.get("coverage"), "overfill": shape.get("overfill_ratio"),
            "iou": shape.get("iou"),
            "layer_iou_min": min(ious) if ious else None,
            "failed_layer_count": shape.get("failed_layer_count"),
            "robot_dtw_s": _dtw(outputs.get("robots", [])) or None,
            "collision_event_count": coll.get("collision_event_count")}


# --------------------------------------------------------------------------- main loop


@dataclass(slots=True)
class Context:
    source_dir: Path
    run_id: str
    runner: object
    probe_root: Path
    results_path: Path
    timeout_s: float
    git: tuple[str, bool]


class _Log:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __call__(self, msg: str) -> None:
        line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _attempt(ctx: Context, cfg, stack, attempt: int, first_candidate: int, slicing_s: float):
    """One attempt. Returns (FailureClass | None, info). Raises ProbeAbort before a verdict."""
    run = ctx.run_id if attempt == 1 else f"{ctx.run_id}-a{attempt}"
    job = make_job_dir(ctx.source_dir, run, ctx.probe_root)
    log = _Log(job / "probe.log")
    probe: dict = {k: None for k in PROBE_JSON_KEYS}
    probe.update(run_id=run, attempt=attempt, slicing_s=slicing_s,
                 git_commit=ctx.git[0], git_dirty=ctx.git[1],
                 config_md5=hashlib.md5((job / "config.yaml").read_bytes()).hexdigest())
    info = {"job": job, "probe": probe, "log": log}
    log(f"attempt a{attempt} run={run} config_md5={probe['config_md5']}")
    if probe["config_md5"] != EXPECTED_CONFIG_MD5:
        log(f"WARNING config md5 differs from {EXPECTED_CONFIG_MD5} (not an abort)")
    try:
        t = time.perf_counter()
        params = ToolpathParams.from_config(cfg)  # P3: defaults only
        tp = generate(stack, cfg, params, use_cache=False)
        probe["toolpath_s"] = time.perf_counter() - t
        probe["toolpath_params"] = params
        probe["pass_count"] = len(tp.passes)
        missing = sum(1 for q in tp.passes if 1 not in q.reachable_robots)
        if missing:
            raise ProbeAbort("PROBE_REACH", f"{missing} of {len(tp.passes)} passes not reachable by robot 1")

        t = time.perf_counter()
        timing = TimingParams.from_config(cfg)
        chain1 = robot1_chain(cfg, tp, timing)
        probe["chain_s"] = time.perf_counter() - t

        t = time.perf_counter()
        rules = PrevalidateRules.from_config(cfg)
        plan = plan_parking(cfg, rules, chain1, timing, first_candidate)
        prevalidate_s = time.perf_counter() - t
        info["plan"], info["toolpath"] = plan, tp
        probe["park_index"] = plan.park_index
        probe["chain_rows"] = sum(len(c) + 1 for c in plan.chains.values())

        t = time.perf_counter()
        traj = job / "trajectory.csv"
        try:
            writer.write_trajectory(traj, plan.chains, rules, plan.timelines)
        except ValueError as exc:
            raise ProbeAbort("PROBE_CSV", str(exc)) from exc
        write_s = time.perf_counter() - t
        compute_s = probe["toolpath_s"] + probe["chain_s"] + prevalidate_s + write_s
        probe.update(prevalidate_s=prevalidate_s, write_s=write_s, compute_s=compute_s,
                     trajectory_sha256=_sha256(traj))
        log(f"trajectory written: {probe['chain_rows']} rows, compute_s={compute_s:.3f}")

        exit_code, wall = ctx.runner(job, ctx.timeout_s)
        probe.update(validator_exit_code=exit_code, validator_wall_s=wall,
                     a1_points=a1_points(wall))
        outputs = read_validator_outputs(job / "validator_out")
        cls = classify_failure(outputs)
        probe.update(validator_items(outputs))
        probe["failure_class"] = cls.value
        info["outputs"] = outputs
        log(f"validator exit={exit_code} wall={wall:.1f}s class={cls.value}")

        summary = outputs["summary"]
        if isinstance(summary, dict) and summary.get("status") in ("PASS", "FAIL"):  # P16
            lb = lower_bound(stack, cfg).lower_bound_s
            notes = f"{RATIO_NOTE}; run={run}; a{attempt}" + ("; dirty" if ctx.git[1] else "")
            row = results.make_row(MODEL, ALGO, compute_s=compute_s, seed=None, commit=ctx.git[0],
                                   trajectory_path=traj, lower_bound_s=lb,
                                   summary_path=job / "validator_out" / "summary.json",
                                   notes=notes)
            results.append_result(ctx.results_path, row)
            probe["results_row"] = {"makespan_s": row.makespan_s, "ratio": row.ratio,
                                    "passed": row.passed}
        if cls is FailureClass.COLLISION:
            probe["prevalidate_missed_collision"] = True  # soundness contract violated
        return cls, info
    except ProbeAbort as exc:
        probe["abort"] = exc.code
        log(f"ABORT {exc}")
        if isinstance(exc, ProbeValidatorTimeout):
            probe["validator_wall_s_lower_bound"] = exc.wall_s
        raise
    finally:
        _write_json(job / "probe.json", probe)


def run_probe(source_dir: Path = DEFAULT_SOURCE_DIR, run_id: str | None = None, *,
              runner=run_validator, probe_root: Path = PROBE_ROOT,
              results_path: Path = RESULTS_CSV, timeout_s: float = TIMEOUT_S,
              git: tuple[str, bool] | None = None) -> int:
    git = git or git_info()
    run_id = run_id or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{MODEL}-{git[0]}"
    ctx = Context(Path(source_dir), run_id, runner, Path(probe_root), Path(results_path),
                  timeout_s, git)
    try:
        cfg = load_config(ctx.source_dir / "config.yaml")
        t = time.perf_counter()
        stack = slice_stl(ctx.source_dir / "target.stl", cfg, use_cache=False)  # P22: no cache writes
        slicing_s = time.perf_counter() - t
    except Exception as exc:  # noqa: BLE001 -- unusable input is an abort, not a crash
        print(f"ABORT PROBE_INPUT: {exc}", file=sys.stderr)
        return EXIT_ABORT

    seen: set[FailureClass] = set()
    first_candidate, attempt = 0, 0
    while True:
        attempt += 1
        retries_left = RETRY_BUDGET - (attempt - 1)
        try:
            cls, info = _attempt(ctx, cfg, stack, attempt, first_candidate, slicing_s)
        except ProbeAbort as exc:
            if exc.code == "PROBE_CSV" and FailureClass.CSV not in seen and retries_left > 0:
                seen.add(FailureClass.CSV)  # D2: regenerate once in a new run folder
                continue
            print(f"ABORT {exc}", file=sys.stderr)
            return EXIT_ABORT
        if cls is FailureClass.PASS:
            return _finish_pass(cfg, stack, info)
        if cls is FailureClass.SHAPE:
            return EXIT_SHAPE
        retry = False
        if cls is FailureClass.COLLISION:
            first_candidate = max(info["plan"].park_index.values()) + 1
            retry = True
        elif cls in (FailureClass.CSV, FailureClass.SPEED):
            retry = cls not in seen  # reproduced -> stop (D2)
            seen.add(cls)
        if not retry or retries_left <= 0:
            return EXIT_EXHAUSTED


def _finish_pass(cfg, stack, info) -> int:
    """P18: our per-layer metrics vs the Validator's. A mismatch is reported, never retried."""
    probe, outputs = info["probe"], info["outputs"]
    overall, own_layers = own_shape_metrics(stack, info["toolpath"], cfg)
    shape = outputs["summary"].get("shape") or {}
    cmp = compare_layers(own_layers, outputs["layers"], TOLERANCE,
                         own_overall={n: getattr(overall, n) for n in _COMPARED},
                         validator_overall=shape)
    probe["layer_comparison"] = {"tolerance": TOLERANCE, "ok": cmp.ok,
                                 "max_abs_err": cmp.max_abs_err, "own_layers": cmp.own_layers,
                                 "validator_layers": cmp.validator_layers,
                                 "mismatches": cmp.mismatches}
    _write_json(info["job"] / "probe.json", probe)
    info["log"](f"P18 comparison ok={cmp.ok} max_abs_err={cmp.max_abs_err:.3g}")
    return EXIT_PASS if cmp.ok else EXIT_MISMATCH


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m experiments.probe_06", description=__doc__.splitlines()[0])
    ap.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)
    return run_probe(args.source_dir, args.run_id)


if __name__ == "__main__":
    sys.exit(main())
