"""Validation-only selection of the global abstention threshold.

The rule is fixed by `ML_SYSTEM_DESIGN.md`: enumerate candidate thresholds from
the sorted unique validation confidences plus endpoints, discard any candidate
whose coverage falls below the configured minimum, then choose the lowest
selective risk, breaking ties by higher coverage and then by lower threshold.

This module is pure: it performs no file I/O and imports no model framework, so
the same selection can be replayed from a persisted validation record. It also
never sees text, example IDs, or a split name.

**Leakage control is structural.** `select_threshold` accepts only per-item
confidence and correctness. There is no parameter through which a test label or
a test-derived quantity could reach it, so test-set selection is not something
this API can express — it is not merely discouraged by convention.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

THRESHOLD_RULE: Final = "min_selective_risk_at_min_coverage"
THRESHOLD_RULE_VERSION: Final = 1
THRESHOLD_SOURCE: Final = "validation"


class ThresholdError(ValueError):
    """Raised when threshold selection inputs violate the selection contract."""


@dataclass(frozen=True, slots=True)
class CoveragePoint:
    """Selective-prediction behaviour at one candidate threshold."""

    threshold: float
    coverage: float
    accepted_count: int
    accepted_accuracy: float
    selective_risk: float


@dataclass(frozen=True, slots=True)
class ThresholdSelection:
    """The selected threshold and the validation evidence that produced it."""

    threshold: float
    rule: str
    rule_version: int
    source: str
    minimum_coverage: float
    validation_example_count: int
    coverage: float
    accepted_count: int
    accepted_accuracy: float
    selective_risk: float
    candidate_count: int


def _validated_inputs(
    confidences: Sequence[float], correct: Sequence[bool]
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    if len(confidences) != len(correct):
        raise ThresholdError("Confidence and correctness lengths differ")
    if len(confidences) == 0:
        raise ThresholdError("Threshold selection requires at least one validation example")

    for index, value in enumerate(confidences):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.floating)):
            raise ThresholdError(f"confidences[{index}] is not a real number")
        if not np.isfinite(float(value)):
            raise ThresholdError(f"confidences[{index}] is not finite")
        if not 0.0 <= float(value) <= 1.0:
            raise ThresholdError(f"confidences[{index}] is outside [0, 1]")

    for index, value in enumerate(correct):
        if not isinstance(value, (bool, np.bool_)):
            raise ThresholdError(f"correct[{index}] is not a boolean")

    return (
        np.asarray([float(value) for value in confidences], dtype=np.float64),
        np.asarray([bool(value) for value in correct], dtype=np.bool_),
    )


def candidate_thresholds(confidences: Sequence[float]) -> tuple[float, ...]:
    """Enumerate candidates: the sorted unique confidences plus both endpoints.

    Including each observed confidence exactly makes the acceptance boundary
    reachable, because acceptance is `confidence >= threshold`. Adding `0.0` and
    `1.0` covers full coverage and total abstention, so the enumeration spans the
    whole achievable range rather than only the interior.
    """

    values, _ = _validated_inputs(confidences, [True] * len(confidences))
    return tuple(sorted(set(values.tolist()) | {0.0, 1.0}))


def coverage_curve(
    confidences: Sequence[float], correct: Sequence[bool]
) -> tuple[CoveragePoint, ...]:
    """Compute coverage, accepted accuracy, and selective risk at every candidate.

    A threshold that accepts nothing has zero coverage and is reported with zero
    accepted accuracy and unit selective risk. That keeps the curve total, while
    the minimum-coverage floor is what actually excludes such a point from
    selection.
    """

    values, hits = _validated_inputs(confidences, correct)
    total = int(values.size)

    points: list[CoveragePoint] = []
    for threshold in candidate_thresholds(confidences):
        accepted = values >= threshold
        accepted_count = int(np.count_nonzero(accepted))
        if accepted_count == 0:
            points.append(
                CoveragePoint(
                    threshold=threshold,
                    coverage=0.0,
                    accepted_count=0,
                    accepted_accuracy=0.0,
                    selective_risk=1.0,
                )
            )
            continue
        accepted_accuracy = float(np.count_nonzero(hits & accepted)) / accepted_count
        points.append(
            CoveragePoint(
                threshold=threshold,
                coverage=accepted_count / total,
                accepted_count=accepted_count,
                accepted_accuracy=accepted_accuracy,
                selective_risk=1.0 - accepted_accuracy,
            )
        )
    return tuple(points)


def select_threshold(
    confidences: Sequence[float],
    correct: Sequence[bool],
    *,
    minimum_coverage: float,
) -> ThresholdSelection:
    """Select the abstention threshold from validation predictions only.

    `confidences` and `correct` must both come from the validation split. No
    argument can carry a test label, which is what makes AC-005 structural.

    Ties are broken deterministically — higher coverage first, then lower
    threshold — so two runs over identical input select the identical threshold.
    """

    if (
        isinstance(minimum_coverage, bool)
        or not isinstance(minimum_coverage, (int, float))
        or not np.isfinite(float(minimum_coverage))
        or not 0.0 < float(minimum_coverage) < 1.0
    ):
        raise ThresholdError("minimum_coverage must be a finite value between zero and one")

    curve = coverage_curve(confidences, correct)
    eligible = [point for point in curve if point.coverage >= float(minimum_coverage)]
    if not eligible:
        # Unreachable while `0.0` is enumerated as a candidate: it accepts every
        # example, so its coverage is exactly 1.0, and `minimum_coverage` is
        # strictly below 1.0. Kept so that a future change to candidate
        # enumeration fails with this message rather than with `min()` on an
        # empty sequence.
        raise ThresholdError(
            f"No candidate threshold reaches the minimum coverage {minimum_coverage}"
        )

    best = min(eligible, key=lambda point: (point.selective_risk, -point.coverage, point.threshold))
    return ThresholdSelection(
        threshold=best.threshold,
        rule=THRESHOLD_RULE,
        rule_version=THRESHOLD_RULE_VERSION,
        source=THRESHOLD_SOURCE,
        minimum_coverage=float(minimum_coverage),
        validation_example_count=len(confidences),
        coverage=best.coverage,
        accepted_count=best.accepted_count,
        accepted_accuracy=best.accepted_accuracy,
        selective_risk=best.selective_risk,
        candidate_count=len(curve),
    )


def decide(confidence: float, threshold: float) -> str:
    """Return `accept` when confidence reaches the threshold, otherwise `abstain`.

    One definition of the boundary, shared by training, evaluation, and serving,
    so an artifact's reload-parity check and the API can never disagree on an
    exactly-at-threshold confidence.
    """

    for name, value in (("confidence", confidence), ("threshold", threshold)):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.floating)):
            raise ThresholdError(f"{name} is not a real number")
        if not np.isfinite(float(value)):
            raise ThresholdError(f"{name} is not finite")
    return "accept" if float(confidence) >= float(threshold) else "abstain"


def selection_payload(selection: ThresholdSelection) -> dict[str, object]:
    """Render the selection as a JSON-serialisable payload with stable keys."""

    return {
        "threshold": selection.threshold,
        "rule": selection.rule,
        "rule_version": selection.rule_version,
        "source": selection.source,
        "minimum_coverage": selection.minimum_coverage,
        "validation_example_count": selection.validation_example_count,
        "coverage": selection.coverage,
        "accepted_count": selection.accepted_count,
        "accepted_accuracy": selection.accepted_accuracy,
        "selective_risk": selection.selective_risk,
        "candidate_count": selection.candidate_count,
    }
