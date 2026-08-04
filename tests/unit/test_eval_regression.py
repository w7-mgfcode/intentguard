"""Metric regression lock (AC-011, S03.3 criterion 17).

The expected values live in ``tests/fixtures/metric_regression.json`` as exact
rationals so a reviewer can verify them by hand without running this code. The
fixture is small and deliberately imbalanced: accuracy (5/7), macro-F1 (85/126),
and weighted-F1 (107/147) are three distinct numbers, so a silent swap of macro
and weighted averaging fails here instead of passing unnoticed.

Every per-class precision, recall, F1, and support value is asserted, so any
change in metric semantics must be an explicit decision that bumps
``METRIC_VERSION`` and updates this fixture.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from intentguard.metrics import METRIC_VERSION, compute_classification_metrics, metrics_payload

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "metric_regression.json"
TOLERANCE = 1e-12


def _fixture() -> dict[str, Any]:
    with FIXTURE_PATH.open("rb") as stream:
        document: dict[str, Any] = json.load(stream)
    return document


def _exact(rational: list[int]) -> float:
    numerator, denominator = rational
    return float(Fraction(numerator, denominator))


FIXTURE = _fixture()
EXPECTED = FIXTURE["expected"]


def test_fixture_pins_the_current_metric_version() -> None:
    assert FIXTURE["metric_version"] == METRIC_VERSION, (
        "Metric semantics changed: bump METRIC_VERSION and re-derive the "
        "hand-checked fixture values before updating this file."
    )


def test_hand_checked_aggregate_metrics() -> None:
    metrics = compute_classification_metrics(
        FIXTURE["y_true"], FIXTURE["y_pred"], FIXTURE["label_names"]
    )

    assert metrics.example_count == EXPECTED["example_count"]
    assert metrics.accuracy == pytest.approx(_exact(EXPECTED["accuracy"]), abs=TOLERANCE)
    assert metrics.macro_f1 == pytest.approx(_exact(EXPECTED["macro_f1"]), abs=TOLERANCE)
    assert metrics.weighted_f1 == pytest.approx(_exact(EXPECTED["weighted_f1"]), abs=TOLERANCE)


def test_aggregate_metrics_are_three_distinct_values() -> None:
    values = {
        _exact(EXPECTED["accuracy"]),
        _exact(EXPECTED["macro_f1"]),
        _exact(EXPECTED["weighted_f1"]),
    }
    assert len(values) == 3, "The fixture must distinguish accuracy, macro-F1, and weighted-F1"


def test_hand_checked_per_class_metrics() -> None:
    metrics = compute_classification_metrics(
        FIXTURE["y_true"], FIXTURE["y_pred"], FIXTURE["label_names"]
    )

    assert len(metrics.per_class) == len(EXPECTED["per_class"])
    for actual, expected in zip(metrics.per_class, EXPECTED["per_class"], strict=True):
        assert actual.label_id == expected["label_id"]
        assert actual.label_name == expected["label_name"]
        assert actual.support == expected["support"]
        assert actual.precision == pytest.approx(_exact(expected["precision"]), abs=TOLERANCE)
        assert actual.recall == pytest.approx(_exact(expected["recall"]), abs=TOLERANCE)
        assert actual.f1 == pytest.approx(_exact(expected["f1"]), abs=TOLERANCE)


def test_payload_reproduces_the_hand_checked_values() -> None:
    payload = metrics_payload(
        compute_classification_metrics(
            FIXTURE["y_true"], FIXTURE["y_pred"], FIXTURE["label_names"]
        )
    )

    assert payload["metric_version"] == METRIC_VERSION
    assert payload["accuracy"] == pytest.approx(_exact(EXPECTED["accuracy"]), abs=TOLERANCE)
    assert payload["macro_f1"] == pytest.approx(_exact(EXPECTED["macro_f1"]), abs=TOLERANCE)
    assert payload["weighted_f1"] == pytest.approx(_exact(EXPECTED["weighted_f1"]), abs=TOLERANCE)
    assert json.loads(json.dumps(payload)) == payload
