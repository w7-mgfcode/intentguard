"""Metric regression lock (AC-011, S03.3 criterion 17).

The expected values live in ``tests/fixtures/metric_regression.json`` as exact
rationals so a reviewer can verify them by hand without running this code. The
fixture is small and deliberately imbalanced: accuracy (5/7), macro-F1 (85/126),
and weighted-F1 (107/147) are three distinct numbers, so a silent swap of macro
and weighted averaging fails here instead of passing unnoticed.

Every per-class precision, recall, F1, and support value is asserted, so any
change in metric semantics must be an explicit decision that bumps
``METRIC_VERSION`` and updates this fixture.

The calibration half pins ECE the same way. Its six confidences exercise each
D15 clause at once: one bin is empty, one is perfectly calibrated, and one
confidence is exactly 1.0. Since every bin is weighted by its own mass, the empty
bin adds exactly zero to ECE; the dilution this fixture pins down is therefore the
unweighted one, where averaging the per-bin gaps over all 5 bins gives 9/100
instead of 9/80 over the 4 occupied ones — scaled by exactly non_empty/bin_count.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from intentguard.metrics import (
    METRIC_VERSION,
    calibration_payload,
    compute_calibration_metrics,
    compute_classification_metrics,
    metrics_payload,
)

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


CALIBRATION = FIXTURE["calibration"]
CALIBRATION_EXPECTED = CALIBRATION["expected"]


def _calibration() -> Any:
    return compute_calibration_metrics(
        CALIBRATION["confidences"],
        CALIBRATION["correct"],
        bin_count=CALIBRATION["bin_count"],
    )


def test_hand_checked_expected_calibration_error() -> None:
    metrics = _calibration()

    assert metrics.example_count == CALIBRATION_EXPECTED["example_count"]
    assert metrics.bin_count == CALIBRATION["bin_count"]
    assert metrics.non_empty_bin_count == CALIBRATION_EXPECTED["non_empty_bin_count"]
    assert metrics.expected_calibration_error == pytest.approx(
        _exact(CALIBRATION_EXPECTED["expected_calibration_error"]), abs=TOLERANCE
    )
    assert metrics.mean_confidence == pytest.approx(
        _exact(CALIBRATION_EXPECTED["mean_confidence"]), abs=TOLERANCE
    )
    assert metrics.accuracy == pytest.approx(
        _exact(CALIBRATION_EXPECTED["accuracy"]), abs=TOLERANCE
    )


def test_empty_bins_are_excluded_rather_than_counted_as_zero_error() -> None:
    """The dilution trap, stated as the arithmetic it actually is.

    An empty bin has no observation to disagree with, so its gap of 0.0 records
    absence of evidence rather than perfect calibration. Averaging the per-bin gaps
    over ``bin_count`` instead of over the occupied bins scales that mean by exactly
    ``non_empty / bin_count``, flattering whichever model leaves more bins empty.

    The scaling factor is asserted rather than a mere inequality: a test that only
    checks "the diluted value differs" would pass for any wrong number, including a
    formula that does not match the one the docstrings and ``reports/README.md``
    describe.
    """

    metrics = _calibration()
    over_non_empty = _exact(CALIBRATION_EXPECTED["unweighted_gap_mean_over_non_empty_bins"])
    over_all = _exact(CALIBRATION_EXPECTED["unweighted_gap_mean_over_all_bins"])

    assert metrics.non_empty_bin_count < metrics.bin_count, (
        "This fixture must contain an empty bin or it cannot detect the dilution"
    )

    gaps = [entry.gap for entry in metrics.bins]
    assert sum(gaps) / metrics.non_empty_bin_count == pytest.approx(
        over_non_empty, abs=TOLERANCE
    )
    assert sum(gaps) / metrics.bin_count == pytest.approx(over_all, abs=TOLERANCE)

    # The documented factor, verified rather than asserted by inequality alone.
    assert over_all == pytest.approx(
        over_non_empty * metrics.non_empty_bin_count / metrics.bin_count, abs=TOLERANCE
    )
    assert over_all < over_non_empty, "Dilution must understate, or it is not a trap"

    # ECE itself is a mass-weighted sum, so it is immune to this dilution entirely —
    # which is why the fixture pins the unweighted means instead of claiming ECE moves.
    assert metrics.expected_calibration_error == pytest.approx(
        _exact(CALIBRATION_EXPECTED["expected_calibration_error"]), abs=TOLERANCE
    )


def test_an_empty_bin_changes_the_expected_calibration_error_by_exactly_zero() -> None:
    """The contribution of an empty bin is 0, not merely small.

    Asserted as an exact equality rather than an approximation: the reported ECE
    must equal the weighted sum over the non-empty bins alone, with nothing added
    for the empty ones. This is the complement of the dilution test above — that
    one proves the wrong value is not reported, this one proves the right value is
    unaffected by how many bins happen to be empty.
    """

    metrics = _calibration()
    empty = [entry for entry in metrics.bins if entry.count == 0]
    assert empty, "This fixture must contain an empty bin for the assertion to mean anything"

    non_empty_only = sum(
        (entry.count / metrics.example_count) * entry.gap
        for entry in metrics.bins
        if entry.count > 0
    )
    including_empty = sum(
        (entry.count / metrics.example_count) * entry.gap for entry in metrics.bins
    )

    assert non_empty_only == including_empty
    assert metrics.expected_calibration_error == pytest.approx(
        non_empty_only, abs=TOLERANCE
    )
    for entry in empty:
        assert entry.count == 0
        assert (entry.count / metrics.example_count) * entry.gap == 0.0


def test_widening_the_binning_only_adds_empty_bins_and_preserves_the_error() -> None:
    """Bins beyond the occupied range must not move the number.

    Confidences confined to [0, 0.5) are scored under 2 and then 4 bins whose edges
    coincide on that range: the extra bins are empty, so an implementation that
    averaged over ``bin_count`` would report two different ECEs for one model.
    """

    confidences = [0.1, 0.2, 0.3, 0.4]
    correct = [False, True, True, True]

    narrow = compute_calibration_metrics(confidences, correct, bin_count=5)
    wide = compute_calibration_metrics(confidences, correct, bin_count=10)

    # [0.0,0.2), [0.2,0.4), [0.4,0.6) under 5 bins split into pairs under 10, but
    # each of 0.1/0.2/0.3/0.4 stays alone in its own bin either way.
    assert narrow.non_empty_bin_count == 3
    assert wide.non_empty_bin_count == 4
    assert wide.example_count == narrow.example_count == 4
    # Every example is alone in its bin under 10 bins, so each gap is |acc - conf|.
    expected = (
        sum(abs(hit - value) for value, hit in zip(confidences, correct, strict=True)) / 4
    )
    assert wide.expected_calibration_error == pytest.approx(expected, abs=TOLERANCE)


def test_hand_checked_per_bin_values() -> None:
    metrics = _calibration()
    expected_bins = CALIBRATION_EXPECTED["bins"]

    assert len(metrics.bins) == len(expected_bins) == CALIBRATION["bin_count"]
    for actual, expected in zip(metrics.bins, expected_bins, strict=True):
        assert actual.count == expected["count"]
        assert actual.lower == pytest.approx(_exact(expected["lower"]), abs=TOLERANCE)
        assert actual.upper == pytest.approx(_exact(expected["upper"]), abs=TOLERANCE)
        assert actual.mean_confidence == pytest.approx(
            _exact(expected["mean_confidence"]), abs=TOLERANCE
        )
        assert actual.accuracy == pytest.approx(_exact(expected["accuracy"]), abs=TOLERANCE)
        assert actual.gap == pytest.approx(_exact(expected["gap"]), abs=TOLERANCE)


def test_every_example_lands_in_exactly_one_bin() -> None:
    """Weights must sum to one, or ECE is not a weighted mean of the gaps."""

    metrics = _calibration()

    assert sum(entry.count for entry in metrics.bins) == metrics.example_count
    weights = sum(entry.count / metrics.example_count for entry in metrics.bins)
    assert weights == pytest.approx(1.0, abs=TOLERANCE)


def test_confidence_of_exactly_one_is_binned_rather_than_dropped() -> None:
    """The final bin is closed on the right, so 1.0 has somewhere to go."""

    metrics = compute_calibration_metrics([1.0], [True], bin_count=CALIBRATION["bin_count"])

    assert metrics.example_count == 1
    assert metrics.bins[-1].count == 1
    assert sum(entry.count for entry in metrics.bins) == 1


def test_bin_edges_are_left_closed_and_right_open() -> None:
    """A confidence on an interior edge belongs to the bin it opens, not the one it closes."""

    metrics = compute_calibration_metrics([0.2], [True], bin_count=5)

    assert metrics.bins[0].count == 0, "0.2 must not fall in [0.0, 0.2)"
    assert metrics.bins[1].count == 1, "0.2 must fall in [0.2, 0.4)"


def test_calibration_payload_round_trips_and_records_the_binning_decision() -> None:
    payload = calibration_payload(_calibration())

    assert payload["metric_version"] == METRIC_VERSION
    assert payload["bin_count"] == CALIBRATION["bin_count"]
    assert payload["binning"] == "equal_width_left_closed"
    assert payload["empty_bins_excluded"] is True
    assert payload["expected_calibration_error"] == pytest.approx(
        _exact(CALIBRATION_EXPECTED["expected_calibration_error"]), abs=TOLERANCE
    )
    assert json.loads(json.dumps(payload)) == payload


def test_perfect_calibration_scores_zero() -> None:
    """A model whose confidence equals its accuracy in every bin has no gap."""

    # Two exactly-calibrated groups: 1 of 2 correct at confidence 0.5, and 9 of 10
    # correct at confidence 0.9. Note that "all correct at 0.9" is *not* perfect
    # calibration — it is underconfidence with a real 0.1 gap.
    metrics = compute_calibration_metrics(
        [0.5, 0.5] + [0.9] * 10,
        [True, False] + [True] * 9 + [False],
        bin_count=10,
    )

    assert metrics.expected_calibration_error == pytest.approx(0.0, abs=TOLERANCE)


def test_maximally_overconfident_model_scores_one() -> None:
    """Certainty on every example while being wrong on every example is ECE 1.0."""

    metrics = compute_calibration_metrics([1.0, 1.0, 1.0], [False, False, False])

    assert metrics.expected_calibration_error == pytest.approx(1.0, abs=TOLERANCE)
