"""T-B16: no robot-count or angle constants in the baseline part-1 modules (AST check)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from _baseline_support import MODELS

SRC = Path(__file__).resolve().parents[1] / "src" / "waam"



PART_MODULES = ["strategy.py", "sector.py", "pieces.py", "standby.py", "assign.py", "schedule.py", "baseline.py"]
_ROBOTISH = ("robot", "rid", "base", "n_robots", "angle", "ang", "theta", "beta", "delta", "phi")
_ANGLE_CONSTANTS = {60, 120, 180, 240, 300, 360}


def _find_constants(source: str) -> list[str]:
    """Constants in robot-count or angle context: compared with a robot/angle expression,
    used as a range bound, a literal id tuple, or a bare angle literal."""
    tree = ast.parse(source)
    bad: list[str] = []

    def robotish(node):
        text = ast.unparse(node).lower()
        return any(w in text for w in _ROBOTISH) and "constants" not in text

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            for a in sides:
                if isinstance(a, ast.Constant) and isinstance(a.value, (int, float)) \
                        and not isinstance(a.value, bool) and a.value not in (0, 1, -1):
                    others = [s for s in sides if s is not a]
                    if any(robotish(o) for o in others):
                        bad.append(f"line {node.lineno}: {ast.unparse(node)}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            consts = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, int)]
            if any(c > 2 for c in consts):
                bad.append(f"line {node.lineno}: {ast.unparse(node)}")
        elif isinstance(node, ast.Tuple):
            vals = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, int)]
            if len(vals) == len(node.elts) >= 3 and vals == list(range(vals[0], vals[0] + len(vals))):
                bad.append(f"line {node.lineno}: {ast.unparse(node)}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool) and node.value in _ANGLE_CONSTANTS:
            bad.append(f"line {node.lineno}: literal {node.value}")
    return bad


def test_ast_checker_flags_robot_count_and_angle_constants():
    assert _find_constants("if len(robots) == 3:\n    pass\n")
    assert _find_constants("for rid in range(1, 4):\n    pass\n")
    assert _find_constants("ids = (1, 2, 3)\n")
    assert _find_constants("sector = angle % 120\n")
    assert _find_constants("if spec.delta > 60:\n    pass\n")
    # innocuous numbers are not flagged
    assert not _find_constants("if len(v) >= 2 and d <= 0.0 and n == 1:\n    pass\nx = 2.0 * y + 1e-9\n")


@pytest.mark.parametrize("module", PART_MODULES)
def test_no_robot_count_or_angle_constants_in_strategy_modules(module):
    source = (SRC / module).read_text(encoding="utf-8")
    assert _find_constants(source) == []
    assert not any(f'"{m}"' in source or f"'{m}'" in source for m in MODELS)  # no model numbers
