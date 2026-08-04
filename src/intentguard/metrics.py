"""Pure, versioned classification metrics shared by evaluation and reporting."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import precision_recall_fscore_support  # type: ignore[import-untyped]

METRIC_VERSION: Final = 1


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


def _label_array(values: Sequence[int], name: str, label_count: int) -> NDArray[np.int64]:
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
    truth = _label_array(y_true, "y_true", label_count)
    predicted = _label_array(y_pred, "y_pred", label_count)

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
