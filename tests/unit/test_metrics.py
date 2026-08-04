"""Contract tests for the pure classification metric functions."""

from __future__ import annotations

import warnings

import pytest

from intentguard.metrics import (
    METRIC_VERSION,
    MetricError,
    compute_classification_metrics,
    metrics_payload,
)

LABELS = ("alpha", "beta", "gamma")


def test_metric_version_is_pinned() -> None:
    assert METRIC_VERSION == 1
    metrics = compute_classification_metrics([0], [0], LABELS)
    assert metrics.metric_version == METRIC_VERSION


def test_perfect_predictions_score_one() -> None:
    metrics = compute_classification_metrics([0, 1, 2], [0, 1, 2], LABELS)
    assert metrics.accuracy == 1.0
    assert metrics.macro_f1 == 1.0
    assert metrics.weighted_f1 == 1.0
    assert metrics.example_count == 3


def test_every_label_appears_even_without_support() -> None:
    metrics = compute_classification_metrics([0, 0], [0, 0], LABELS)
    assert len(metrics.per_class) == len(LABELS)
    assert [entry.label_id for entry in metrics.per_class] == [0, 1, 2]
    assert [entry.label_name for entry in metrics.per_class] == list(LABELS)


def test_zero_support_class_reports_zero_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        metrics = compute_classification_metrics([0, 0], [0, 0], LABELS)

    absent = metrics.per_class[2]
    assert absent.support == 0
    assert absent.precision == 0.0
    assert absent.recall == 0.0
    assert absent.f1 == 0.0


def test_support_sums_to_example_count() -> None:
    metrics = compute_classification_metrics([0, 0, 1, 2], [0, 1, 1, 2], LABELS)
    assert sum(entry.support for entry in metrics.per_class) == metrics.example_count


def test_macro_and_weighted_differ_under_imbalance() -> None:
    metrics = compute_classification_metrics([0, 0, 0, 0, 1, 1, 2], [0, 0, 0, 1, 1, 2, 2], LABELS)
    assert metrics.macro_f1 != metrics.weighted_f1
    assert metrics.accuracy != metrics.macro_f1


def test_aggregates_are_derived_from_per_class_values() -> None:
    metrics = compute_classification_metrics([0, 0, 0, 1, 1, 2], [0, 1, 2, 1, 2, 2], LABELS)
    per_class_f1 = [entry.f1 for entry in metrics.per_class]
    expected_macro = sum(per_class_f1) / len(per_class_f1)
    expected_weighted = (
        sum(entry.f1 * entry.support for entry in metrics.per_class) / metrics.example_count
    )
    assert metrics.macro_f1 == pytest.approx(expected_macro, abs=1e-12)
    assert metrics.weighted_f1 == pytest.approx(expected_weighted, abs=1e-12)


def test_metrics_are_deterministic_across_calls() -> None:
    arguments = ([0, 0, 1, 2, 2], [0, 1, 1, 2, 0], LABELS)
    assert compute_classification_metrics(*arguments) == compute_classification_metrics(*arguments)


def test_payload_key_order_is_stable() -> None:
    payload = metrics_payload(compute_classification_metrics([0, 1], [0, 1], LABELS))
    assert list(payload) == [
        "metric_version",
        "example_count",
        "accuracy",
        "macro_f1",
        "weighted_f1",
        "per_class",
    ]
    per_class = payload["per_class"]
    assert isinstance(per_class, list)
    assert list(per_class[0]) == [
        "label_id",
        "label_name",
        "precision",
        "recall",
        "f1",
        "support",
    ]


def test_payload_matches_the_computed_metrics() -> None:
    metrics = compute_classification_metrics([0, 0, 1], [0, 1, 1], LABELS)
    payload = metrics_payload(metrics)
    assert payload["accuracy"] == metrics.accuracy
    assert payload["macro_f1"] == metrics.macro_f1
    assert payload["weighted_f1"] == metrics.weighted_f1
    assert payload["example_count"] == metrics.example_count
    per_class = payload["per_class"]
    assert isinstance(per_class, list)
    assert len(per_class) == len(metrics.per_class)


def test_empty_input_is_rejected() -> None:
    with pytest.raises(MetricError, match="at least one example"):
        compute_classification_metrics([], [], LABELS)


def test_length_mismatch_is_rejected() -> None:
    with pytest.raises(MetricError, match="lengths differ"):
        compute_classification_metrics([0, 1], [0], LABELS)


def test_empty_label_names_are_rejected() -> None:
    with pytest.raises(MetricError, match="must not be empty"):
        compute_classification_metrics([0], [0], ())


def test_blank_label_name_is_rejected() -> None:
    with pytest.raises(MetricError, match="empty name"):
        compute_classification_metrics([0], [0], ("alpha", ""))


def test_duplicate_label_names_are_rejected() -> None:
    with pytest.raises(MetricError, match="must be unique"):
        compute_classification_metrics([0], [0], ("alpha", "alpha"))


@pytest.mark.parametrize("label_id", [-1, 3])
def test_out_of_range_truth_label_is_rejected(label_id: int) -> None:
    with pytest.raises(MetricError, match=r"y_true\[0\] is outside the label map"):
        compute_classification_metrics([label_id], [0], LABELS)


@pytest.mark.parametrize("label_id", [-1, 3])
def test_out_of_range_prediction_label_is_rejected(label_id: int) -> None:
    with pytest.raises(MetricError, match=r"y_pred\[0\] is outside the label map"):
        compute_classification_metrics([0], [label_id], LABELS)


def test_non_integer_label_is_rejected() -> None:
    with pytest.raises(MetricError, match="not an integer label ID"):
        compute_classification_metrics([0.0], [0], LABELS)  # type: ignore[list-item]


def test_boolean_label_is_rejected() -> None:
    with pytest.raises(MetricError, match="not an integer label ID"):
        compute_classification_metrics([True], [0], LABELS)
