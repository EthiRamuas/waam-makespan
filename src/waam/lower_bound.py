"""lower_bound: the theoretical makespan used as the denominator of ``ratio`` (docs/specs/lower_bound.md).

Definition (docs/spec.md section 6; unit: SECONDS)::

    centerline length = sum of layer cross-section areas / bead width
    deposition time   = centerline length / deposition speed
    lower bound       = deposition time / number of robots

``lower_bound_from_areas`` is the pure function: the layer areas, bead width, speed and robot count
are arguments, never constants. ``lower_bound(stack, config)`` is the thin wrapper that reads them
from a ``slicing.LayerStack`` and a config (``n_robots = len(config.robots)``).

Limits (stated, not hidden)
---------------------------
- The definition assumes full fill. It is an approximation, NOT a proven bound: the Validator
  accepts shapes that are less than fully filled, so a makespan below this value is possible.
  ``ratio = makespan / lower_bound_s`` can therefore be below 1 (``ratio < 1``). Nothing here
  or in ``results`` clamps or rejects such a value.
- Arc on/off time is not part of the bound, while our makespan contains it.
- The result is in seconds; docs/spec.md prints the same quantity in hours.
"""

from __future__ import annotations

import math
import numbers
import sys
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .slicing import LayerStack


@dataclass(frozen=True, slots=True)
class LowerBound:
    total_area_mm2: float
    centerline_mm: float
    deposition_s: float  # total deposition time of all robots together
    n_robots: int
    lower_bound_s: float  # deposition_s / n_robots


def _real(name: str, v: object) -> float:
    if isinstance(v, (bool, np.bool_, np.timedelta64, np.datetime64)) \
            or not isinstance(v, numbers.Real):
        raise ValueError(f"{name} must be a real number, got {v!r}")
    try:
        f = float(v)
    except OverflowError as exc:
        raise ValueError(f"{name} is too large to be a float: {exc}") from exc
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite, got {v!r}")
    return f


def _areas(areas_mm2: object) -> list[float]:
    """The per-layer areas as floats. A mapping would sum its KEYS (layer numbers), a set would
    drop duplicate areas and a string is not a list of numbers: refuse all of them."""
    if isinstance(areas_mm2, (Mapping, Set, str, bytes)):
        raise ValueError(f"areas must be an ordered collection of numbers, got "
                         f"{type(areas_mm2).__name__}")
    if not isinstance(areas_mm2, Iterable):
        raise ValueError(f"areas must be iterable, got {type(areas_mm2).__name__}")
    out = [_real("area", a) for a in areas_mm2]
    if not out:
        raise ValueError("no areas")
    if any(a < 0.0 for a in out):
        raise ValueError("areas must be >= 0")
    return out


def lower_bound_from_areas(areas_mm2: Iterable[float], *, bead_width_mm: float,
                           deposition_speed_mm_s: float, n_robots: int) -> LowerBound:
    """Lower bound in seconds from the per-layer cross-section areas (mm^2).

    Raises ``ValueError`` for any input that cannot give a finite lower bound > 0.
    """
    areas = _areas(areas_mm2)
    width = _real("bead_width_mm", bead_width_mm)
    speed = _real("deposition_speed_mm_s", deposition_speed_mm_s)
    if not width > 0.0 or not speed > 0.0:
        raise ValueError("bead_width_mm and deposition_speed_mm_s must be > 0")
    if (isinstance(n_robots, (bool, np.bool_, np.timedelta64)) or n_robots is None
            or not isinstance(n_robots, numbers.Integral) or n_robots < 1):
        raise ValueError(f"n_robots must be an integer >= 1, got {n_robots!r}")
    try:
        n = int(n_robots)
        total = math.fsum(areas)
        centerline = total / width
        deposition = centerline / speed
        bound = deposition / n
    except (OverflowError, ValueError) as exc:  # fsum overflow, n too large for a float
        raise ValueError(f"the lower bound is out of floating-point range: {exc}") from exc
    for name, v in (("total area", total), ("centerline", centerline),
                    ("deposition time", deposition), ("lower bound", bound)):
        # finite and in the normal range: 0, inf and subnormal values give no usable ratio
        if not (math.isfinite(v) and v >= sys.float_info.min):
            raise ValueError(f"{name} is {v!r}: no lower bound (and no ratio) exists")
    return LowerBound(total_area_mm2=total, centerline_mm=centerline, deposition_s=deposition,
                      n_robots=n, lower_bound_s=bound)


def lower_bound(stack: LayerStack, config: object) -> LowerBound:
    """Lower bound in seconds for a sliced part (docs/specs/lower_bound.md section 3, L-3, L-5).

    ``stack`` is a ``slicing.LayerStack`` (anything with ``.layers[*].area_mm2``). ``config`` is
    the Validator config or any object with ``.robots`` (a sized sequence: ``n_robots`` is
    ``len(config.robots)``), ``.process.bead_width_mm`` and ``.process.deposition_speed_mm_s``.
    Nothing is clamped: ``ratio = makespan / lower_bound_s`` may be below 1 (see the module
    docstring). Raises ``ValueError`` like ``lower_bound_from_areas``.
    """
    try:
        areas = [layer.area_mm2 for layer in stack.layers]  # type: ignore[attr-defined]
    except (AttributeError, TypeError) as exc:
        raise ValueError(f"stack must have .layers[*].area_mm2: {exc}") from exc
    robots = getattr(config, "robots", None)
    if isinstance(robots, (str, bytes, Mapping)):
        raise ValueError(f"config.robots must be a sequence of robots, got {type(robots).__name__}")
    try:
        n_robots = len(config.robots)  # type: ignore[attr-defined]
        bead = config.process.bead_width_mm  # type: ignore[attr-defined]
        speed = config.process.deposition_speed_mm_s  # type: ignore[attr-defined]
    except (AttributeError, TypeError) as exc:
        raise ValueError(
            "config needs .robots (sized), .process.bead_width_mm, .process.deposition_speed_mm_s: "
            f"{exc}"
        ) from exc
    return lower_bound_from_areas(
        areas, bead_width_mm=bead, deposition_speed_mm_s=speed, n_robots=n_robots
    )
