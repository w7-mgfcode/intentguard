"""Pure, versioned classification metrics shared by evaluation and reporting."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import precision_recall_fscore_support  # type: ignore[import-untyped]

METRIC_VERSION: Final = 1

CALIBRATION_BIN_COUNT: Final = 15
CALIBRATION_BINNING: Final = "equal_width_left_closed"


class MetricError(ValueError):
    """Raised when a metric request violates the metric contract."""


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    """Precision, recall, F1, and support for exactly one label."""

    label_id: int
    label_name: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    """Aggregate and per-class metrics for one evaluated split."""

    metric_version: int
    example_count: int
    accuracy: float
    macro_f1: float
    weighted_f1: float
    per_class: tuple[ClassMetrics, ...]


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """One confidence bin's occupancy, mean confidence, and observed accuracy."""

    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float
    gap: float


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    """Expected calibration error and the bins it was computed from."""

    metric_version: int
    example_count: int
    bin_count: int
    binning: str
    expected_calibration_error: float
    mean_confidence: float
    accuracy: float
    non_empty_bin_count: int
    bins: tuple[CalibrationBin, ...]


def label_id_array(values: Sequence[int], name: str, label_count: int) -> NDArray[np.int64]:
    """Validate label IDs against the label map and return them as int64.

    This is the single definition of the label-ID contract. Training and metrics
    both use it, so a value that would be rejected in a report can never be
    silently accepted into a fitted model. Booleans are rejected explicitly
    because `bool` is a subclass of `int`, and floats are rejected rather than
    truncated, so `0.9` cannot become label `0`.
    """

    for index, value in enumerate(values):
        if not isinstance(value, (int, np.integer)) or isinstance(value, bool):
            raise MetricError(f"{name}[{index}] is not an integer label ID")
        if not 0 <= int(value) < label_count:
            raise MetricError(f"{name}[{index}] is outside the label map")
    return np.asarray(values, dtype=np.int64)


def compute_classification_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    label_names: Sequence[str],
) -> ClassificationMetrics:
    """Compute accuracy plus macro, weighted, and per-class classification metrics.

    Every label in ``label_names`` appears in the per-class report, including
    labels with zero support, which report ``0.0`` for precision, recall, and F1
    rather than being silently dropped. The macro and weighted aggregates are
    derived from those same per-class values, so a report can never disagree
    with its own summary.
    """

    if not label_names:
        raise MetricError("Label names must not be empty")
    if any(not name for name in label_names):
        raise MetricError("Label names must not contain an empty name")
    if len(set(label_names)) != len(label_names):
        raise MetricError("Label names must be unique")
    if len(y_true) != len(y_pred):
        raise MetricError("Truth and prediction lengths differ")
    if len(y_true) == 0:
        raise MetricError("Metrics require at least one example")

    label_count = len(label_names)
    truth = label_id_array(y_true, "y_true", label_count)
    predicted = label_id_array(y_pred, "y_pred", label_count)

    precision, recall, f1, support = precision_recall_fscore_support(
        truth,
        predicted,
        labels=list(range(label_count)),
        average=None,
        zero_division=0,
    )

    example_count = int(truth.size)
    return ClassificationMetrics(
        metric_version=METRIC_VERSION,
        example_count=example_count,
        accuracy=float(np.count_nonzero(truth == predicted)) / example_count,
        macro_f1=float(np.mean(f1)),
        weighted_f1=float(np.dot(f1, support)) / example_count,
        per_class=tuple(
            ClassMetrics(
                label_id=index,
                label_name=label_names[index],
                precision=float(precision[index]),
                recall=float(recall[index]),
                f1=float(f1[index]),
                support=int(support[index]),
            )
            for index in range(label_count)
        ),
    )


def compute_calibration_metrics(
    confidences: Sequence[float],
    correct: Sequence[bool],
    *,
    bin_count: int = CALIBRATION_BIN_COUNT,
) -> CalibrationMetrics:
    """Compute expected calibration error over fixed equal-width confidence bins.

    The binning is the decision recorded as D15, and each clause is load-bearing:

    * **Equal width**, not equal mass. Equal-mass edges are derived from the data,
      so two models would be scored against two different binnings and their ECEs
      would not be comparable — which is the only thing this metric is here to do.
    * **Left-closed, right-open** ``[lo, hi)``, except the final bin is closed at
      ``1.0`` so a confidence of exactly 1.0 is binned rather than dropped.
    * **Empty bins contribute nothing.** The sum runs over non-empty bins only.
      Averaging over all ``bin_count`` bins instead would scale ECE by
      ``non_empty / bin_count`` and flatter a badly calibrated model.

    ``ECE = sum_b (n_b / N) * |accuracy_b - mean_confidence_b|`` over non-empty bins.
    Because the weights of the non-empty bins sum to exactly one, ECE stays a
    weighted mean of per-bin gaps and remains bounded by 1.
    """

    if isinstance(bin_count, bool) or not isinstance(bin_count, (int, np.integer)):
        raise MetricError("bin_count must be an integer")
    if int(bin_count) < 1:
        raise MetricError("bin_count must be at least one")
    if len(confidences) != len(correct):
        raise MetricError("Confidence and correctness lengths differ")
    if len(confidences) == 0:
        raise MetricError("Calibration requires at least one example")

    for index, value in enumerate(confidences):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.floating)):
            raise MetricError(f"confidences[{index}] is not a real number")
        if not np.isfinite(float(value)):
            raise MetricError(f"confidences[{index}] is not finite")
        if not 0.0 <= float(value) <= 1.0:
            raise MetricError(f"confidences[{index}] is outside [0, 1]")
    for index, flag in enumerate(correct):
        if not isinstance(flag, (bool, np.bool_)):
            raise MetricError(f"correct[{index}] is not a boolean")

    values = np.asarray([float(value) for value in confidences], dtype=np.float64)
    hits = np.asarray([bool(flag) for flag in correct], dtype=np.bool_)
    total = int(values.size)
    bins_requested = int(bin_count)

    bins: list[CalibrationBin] = []
    error = 0.0
    for index in range(bins_requested):
        lower = index / bins_requested
        upper = (index + 1) / bins_requested
        if index + 1 == bins_requested:
            # Closed on the right for the final bin only, so confidence 1.0 is
            # counted somewhere. Every example must land in exactly one bin or the
            # weights would no longer sum to one.
            member = (values >= lower) & (values <= upper)
        else:
            member = (values >= lower) & (values < upper)
        count = int(np.count_nonzero(member))
        if count == 0:
            # Recorded for transparency but excluded from the sum. `gap` is 0.0
            # here because there is no observation to disagree with, not because
            # the model was perfectly calibrated in this range.
            bins.append(
                CalibrationBin(
                    lower=lower,
                    upper=upper,
                    count=0,
                    mean_confidence=0.0,
                    accuracy=0.0,
                    gap=0.0,
                )
            )
            continue
        bin_confidence = float(np.mean(values[member]))
        bin_accuracy = float(np.count_nonzero(hits & member)) / count
        gap = abs(bin_accuracy - bin_confidence)
        error += (count / total) * gap
        bins.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                count=count,
                mean_confidence=bin_confidence,
                accuracy=bin_accuracy,
                gap=gap,
            )
        )

    assigned = sum(entry.count for entry in bins)
    if assigned != total:
        # Unreachable while inputs are constrained to [0, 1] and the final bin is
        # closed. Kept so a future change to the edges fails loudly instead of
        # silently reporting an ECE whose weights do not sum to one.
        raise MetricError(f"Binning assigned {assigned} of {total} examples")

    return CalibrationMetrics(
        metric_version=METRIC_VERSION,
        example_count=total,
        bin_count=bins_requested,
        binning=CALIBRATION_BINNING,
        expected_calibration_error=error,
        mean_confidence=float(np.mean(values)),
        accuracy=float(np.count_nonzero(hits)) / total,
        non_empty_bin_count=sum(1 for entry in bins if entry.count > 0),
        bins=tuple(bins),
    )


def calibration_payload(metrics: CalibrationMetrics) -> dict[str, object]:
    """Render calibration metrics as a JSON-serialisable payload with stable keys."""

    return {
        "metric_version": metrics.metric_version,
        "example_count": metrics.example_count,
        "bin_count": metrics.bin_count,
        "binning": metrics.binning,
        "expected_calibration_error": metrics.expected_calibration_error,
        "mean_confidence": metrics.mean_confidence,
        "accuracy": metrics.accuracy,
        "non_empty_bin_count": metrics.non_empty_bin_count,
        "empty_bins_excluded": True,
        "bins": [
            {
                "lower": entry.lower,
                "upper": entry.upper,
                "count": entry.count,
                "mean_confidence": entry.mean_confidence,
                "accuracy": entry.accuracy,
                "gap": entry.gap,
            }
            for entry in metrics.bins
        ],
    }


def metrics_payload(metrics: ClassificationMetrics) -> dict[str, object]:
    """Render metrics as a JSON-serialisable payload with a stable key order."""

    return {
        "metric_version": metrics.metric_version,
        "example_count": metrics.example_count,
        "accuracy": metrics.accuracy,
        "macro_f1": metrics.macro_f1,
        "weighted_f1": metrics.weighted_f1,
        "per_class": [
            {
                "label_id": entry.label_id,
                "label_name": entry.label_name,
                "precision": entry.precision,
                "recall": entry.recall,
                "f1": entry.f1,
                "support": entry.support,
            }
            for entry in metrics.per_class
        ],
    }
