"""Threshold-selection contract and regression lock (AC-005, S04.2).

The expected values live in ``tests/fixtures/threshold_regression.json`` as exact
rationals so a reviewer can verify the selection by hand without running this
code. The fixture is built so that three plausible wrong rules — maximise
coverage, take the lowest eligible coverage, ignore the coverage floor — each
select a different threshold from the correct one.

The leakage guard here is structural, not a convention: `select_threshold` has no
parameter that could carry a test label, so the tests assert the *shape of the
API* rather than merely asserting that the current caller happens to pass
validation data.
"""

from __future__ import annotations

import inspect
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from intentguard import threshold as threshold_module
from intentguard.threshold import (
    THRESHOLD_RULE,
    THRESHOLD_RULE_VERSION,
    THRESHOLD_SOURCE,
    ThresholdError,
    candidate_thresholds,
    coverage_curve,
    decide,
    select_threshold,
    selection_payload,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "threshold_regression.json"
TOLERANCE = 1e-12


def _fixture() -> dict[str, Any]:
    with FIXTURE_PATH.open("rb") as stream:
        document: dict[str, Any] = json.load(stream)
    return document


def _exact(rational: list[int]) -> float:
    numerator, denominator = rational
    return float(Fraction(numerator, denominator))


FIXTURE = _fixture()
CONFIDENCES: list[float] = FIXTURE["confidences"]
CORRECT: list[bool] = FIXTURE["correct"]
MINIMUM_COVERAGE: float = FIXTURE["minimum_coverage"]
EXPECTED = FIXTURE["expected_selection"]


def test_fixture_pins_the_current_threshold_rule() -> None:
    assert FIXTURE["threshold_rule"] == THRESHOLD_RULE, (
        "Threshold semantics changed: bump THRESHOLD_RULE_VERSION and re-derive "
        "the hand-checked fixture before updating this file."
    )
    assert FIXTURE["threshold_rule_version"] == THRESHOLD_RULE_VERSION


def test_hand_checked_selection() -> None:
    selection = select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)

    assert selection.threshold == pytest.approx(EXPECTED["threshold"], abs=TOLERANCE)
    assert selection.validation_example_count == EXPECTED["validation_example_count"]
    assert selection.candidate_count == EXPECTED["candidate_count"]
    assert selection.accepted_count == EXPECTED["accepted_count"]
    assert selection.coverage == pytest.approx(_exact(EXPECTED["coverage"]), abs=TOLERANCE)
    assert selection.accepted_accuracy == pytest.approx(
        _exact(EXPECTED["accepted_accuracy"]), abs=TOLERANCE
    )
    assert selection.selective_risk == pytest.approx(
        _exact(EXPECTED["selective_risk"]), abs=TOLERANCE
    )


def test_hand_checked_coverage_curve() -> None:
    curve = coverage_curve(CONFIDENCES, CORRECT)

    assert len(curve) == len(FIXTURE["expected_curve"])
    for actual, expected in zip(curve, FIXTURE["expected_curve"], strict=True):
        assert actual.threshold == pytest.approx(expected["threshold"], abs=TOLERANCE)
        assert actual.accepted_count == expected["accepted_count"]
        assert actual.coverage == pytest.approx(_exact(expected["coverage"]), abs=TOLERANCE)
        assert actual.accepted_accuracy == pytest.approx(
            _exact(expected["accepted_accuracy"]), abs=TOLERANCE
        )
        assert actual.selective_risk == pytest.approx(
            _exact(expected["selective_risk"]), abs=TOLERANCE
        )


def test_the_winner_is_not_reachable_by_three_plausible_wrong_rules() -> None:
    curve = coverage_curve(CONFIDENCES, CORRECT)
    eligible = [point for point in curve if point.coverage >= MINIMUM_COVERAGE]
    selected = select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)

    maximise_coverage = max(eligible, key=lambda point: point.coverage).threshold
    lowest_eligible_coverage = min(eligible, key=lambda point: point.coverage).threshold
    ignore_the_floor = min(curve, key=lambda point: (point.selective_risk, point.threshold))

    assert selected.threshold != maximise_coverage
    assert selected.threshold != lowest_eligible_coverage
    assert selected.threshold != ignore_the_floor.threshold
    # The floor is what rejects the zero-risk candidate, which covers only 60%.
    assert ignore_the_floor.selective_risk == 0.0
    assert ignore_the_floor.coverage < MINIMUM_COVERAGE


def test_selection_is_identical_when_run_twice() -> None:
    first = select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)
    second = select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)

    assert first == second
    assert selection_payload(first) == selection_payload(second)


def test_selection_records_validation_as_its_only_source() -> None:
    selection = select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)

    assert selection.source == THRESHOLD_SOURCE == "validation"
    assert selection.rule == THRESHOLD_RULE
    assert selection.rule_version == THRESHOLD_RULE_VERSION
    assert selection.minimum_coverage == MINIMUM_COVERAGE


def test_payload_is_json_serialisable_and_reproduces_the_selection() -> None:
    payload = selection_payload(
        select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)
    )

    assert json.loads(json.dumps(payload)) == payload
    assert payload["threshold"] == pytest.approx(EXPECTED["threshold"], abs=TOLERANCE)
    assert payload["source"] == "validation"


# --- Structural leakage control (AC-005) ------------------------------------


def test_selector_cannot_express_a_test_split_at_all() -> None:
    parameters = set(inspect.signature(select_threshold).parameters)

    # Making test selection unrepresentable is the guard. If a `split`,
    # `test_labels`, or dataset parameter is ever added here, leakage becomes
    # expressible and this test must fail rather than be updated.
    assert parameters == {"confidences", "correct", "minimum_coverage"}
    for forbidden in ("split", "test", "labels", "dataset", "y_true", "examples"):
        assert not any(forbidden in name for name in parameters)


def test_the_module_imports_no_data_or_model_boundary() -> None:
    source = Path(inspect.getfile(threshold_module)).read_text(encoding="utf-8")

    # A pure selector cannot reach a split on disk or a model, so it cannot read
    # test data even by mistake.
    for forbidden in ("intentguard.data", "load_dataset", "import torch", "transformers"):
        assert forbidden not in source
    for forbidden in ("open(", "Path(", "read_text", "json.load"):
        assert forbidden not in source


def test_selection_depends_only_on_confidence_and_correctness() -> None:
    # Permuting the input pairs cannot change the selection, because no per-example
    # identity, order, or text reaches the selector.
    reversed_selection = select_threshold(
        list(reversed(CONFIDENCES)),
        list(reversed(CORRECT)),
        minimum_coverage=MINIMUM_COVERAGE,
    )
    forward_selection = select_threshold(CONFIDENCES, CORRECT, minimum_coverage=MINIMUM_COVERAGE)

    assert reversed_selection == forward_selection


# --- Candidate enumeration --------------------------------------------------


def test_candidates_are_the_unique_confidences_plus_both_endpoints() -> None:
    candidates = candidate_thresholds([0.5, 0.5, 0.9])

    assert candidates == (0.0, 0.5, 0.9, 1.0)


def test_candidates_are_sorted_and_free_of_duplicates() -> None:
    candidates = candidate_thresholds(CONFIDENCES)

    assert list(candidates) == sorted(candidates)
    assert len(set(candidates)) == len(candidates)
    assert candidates[0] == 0.0
    assert candidates[-1] == 1.0


def test_an_observed_confidence_of_one_does_not_duplicate_the_endpoint() -> None:
    candidates = candidate_thresholds([1.0, 0.5])

    assert candidates == (0.0, 0.5, 1.0)


# --- Boundary behaviour -----------------------------------------------------


def test_a_confidence_exactly_at_the_threshold_is_accepted() -> None:
    # Acceptance is `>=`. An exactly-at-threshold confidence is the one case where
    # a `>` implementation and a `>=` implementation disagree, so it is pinned.
    assert decide(0.6, 0.6) == "accept"
    assert decide(0.5999999999999999, 0.6) == "abstain"
    assert decide(0.6000000000000001, 0.6) == "accept"


def test_the_curve_uses_the_same_inclusive_boundary_as_decide() -> None:
    curve = {point.threshold: point for point in coverage_curve(CONFIDENCES, CORRECT)}

    for candidate, point in curve.items():
        accepted = sum(
            1 for confidence in CONFIDENCES if decide(confidence, candidate) == "accept"
        )
        assert point.accepted_count == accepted


def test_a_candidate_whose_coverage_equals_the_floor_is_eligible() -> None:
    # Coverage exactly 7/10 against a floor of 0.70 must not be discarded; the
    # comparison is inclusive. Asserted by making the at-floor candidate the
    # unique winner, so an exclusive `>` floor selects something else and fails
    # here rather than agreeing by coincidence.
    curve = {point.threshold: point for point in coverage_curve(CONFIDENCES, CORRECT)}
    at_floor = curve[0.65]
    assert at_floor.coverage == pytest.approx(0.70, abs=TOLERANCE)

    # Four items, one wrong at the lowest confidence. Candidate 0.4 covers
    # exactly 3/4 against a 0.75 floor and is the only zero-risk eligible point.
    selection = select_threshold(
        [0.2, 0.4, 0.6, 0.8], [False, True, True, True], minimum_coverage=0.75
    )

    assert selection.threshold == pytest.approx(0.4, abs=TOLERANCE)
    assert selection.coverage == pytest.approx(0.75, abs=TOLERANCE)
    assert selection.selective_risk == 0.0


def test_full_coverage_and_total_abstention_are_both_representable() -> None:
    curve = {point.threshold: point for point in coverage_curve(CONFIDENCES, CORRECT)}

    assert curve[0.0].coverage == 1.0
    assert curve[0.0].accepted_count == len(CONFIDENCES)
    assert curve[1.0].coverage == 0.0
    assert curve[1.0].accepted_count == 0
    assert curve[1.0].selective_risk == 1.0


# --- Tie breaking -----------------------------------------------------------


def test_a_selective_risk_tie_is_broken_by_higher_coverage() -> None:
    # 0.4 and 0.8 both yield a perfect accepted set; 0.4 covers more.
    selection = select_threshold(
        [0.4, 0.8, 0.9], [True, True, True], minimum_coverage=0.5
    )

    assert selection.threshold == pytest.approx(0.0, abs=TOLERANCE)
    assert selection.coverage == 1.0


def test_a_remaining_tie_is_broken_by_the_lower_threshold() -> None:
    # 0.0 and 0.3 accept exactly the same examples, so risk and coverage tie and
    # only the threshold itself separates them.
    selection = select_threshold([0.3, 0.7], [True, False], minimum_coverage=0.5)

    assert selection.threshold == pytest.approx(0.0, abs=TOLERANCE)


def test_tie_breaking_is_order_independent() -> None:
    first = select_threshold([0.9, 0.6, 0.3], [True, True, True], minimum_coverage=0.5)
    second = select_threshold([0.3, 0.9, 0.6], [True, True, True], minimum_coverage=0.5)

    assert first.threshold == second.threshold


# --- Rejected input ---------------------------------------------------------


def test_empty_validation_input_is_rejected() -> None:
    with pytest.raises(ThresholdError, match="at least one"):
        select_threshold([], [], minimum_coverage=0.7)


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(ThresholdError, match="lengths differ"):
        select_threshold([0.9, 0.8], [True], minimum_coverage=0.7)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_out_of_range_confidence_is_rejected(value: float) -> None:
    with pytest.raises(ThresholdError):
        select_threshold([0.9, value], [True, True], minimum_coverage=0.7)


def test_a_boolean_confidence_is_rejected() -> None:
    # `bool` is a subclass of `int`, so `True` would otherwise pass as 1.0.
    with pytest.raises(ThresholdError, match="not a real number"):
        select_threshold([True, 0.5], [True, True], minimum_coverage=0.7)


def test_a_non_boolean_correctness_flag_is_rejected() -> None:
    with pytest.raises(ThresholdError, match="not a boolean"):
        select_threshold([0.9, 0.5], [1, 0], minimum_coverage=0.7)  # type: ignore[list-item]


@pytest.mark.parametrize("value", [0.0, 1.0, -0.1, 1.5, float("nan"), float("inf")])
def test_an_out_of_range_minimum_coverage_is_rejected(value: float) -> None:
    with pytest.raises(ThresholdError, match="minimum_coverage"):
        select_threshold(CONFIDENCES, CORRECT, minimum_coverage=value)


def test_some_candidate_is_always_eligible() -> None:
    # The `0.0` candidate accepts every example, so its coverage is exactly 1.0
    # and any floor strictly below 1.0 has at least one eligible candidate. This
    # is why selection cannot fail for want of coverage, and why the guard in
    # `select_threshold` is a defence against a future enumeration change rather
    # than a reachable path today.
    for floor in (0.01, 0.5, 0.7, 0.999999):
        selection = select_threshold([0.9], [True], minimum_coverage=floor)
        assert selection.coverage >= floor


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_a_non_finite_decision_input_is_rejected(value: float) -> None:
    with pytest.raises(ThresholdError, match="not finite"):
        decide(value, 0.5)
    with pytest.raises(ThresholdError, match="not finite"):
        decide(0.5, value)


def test_a_boolean_decision_input_is_rejected() -> None:
    with pytest.raises(ThresholdError, match="not a real number"):
        decide(True, 0.5)
