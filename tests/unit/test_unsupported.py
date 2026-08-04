"""Contract tests for the curated unsupported-request fixture (FR-009, AC-012).

Two of these are mandated by the plan and are the reason the fixture can be
trusted at all: no fixture text may collide with any BANKING77 split, and the
verbatim specification caveat must be present in the report. The rest guard the
ways a small behavioral check quietly turns into an overclaim — a missing caveat,
an invented accuracy, or a total abstention rate published without the
in-distribution rate that gives it meaning.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from intentguard.unsupported import (
    DECLARED_CATEGORIES,
    FIXTURE_SCHEMA_VERSION,
    REQUIRED_FIELDS,
    UNSUPPORTED_FIXTURE_CAVEAT,
    UnsupportedFixtureError,
    UnsupportedRequest,
    assert_disjoint_from_splits,
    evaluate_unsupported_requests,
    load_unsupported_fixture,
    render_unsupported_markdown,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "unsupported_requests.jsonl"
SPECIFICATION = (
    REPOSITORY_ROOT / "docs" / "specification" / "docs" / "ML_SYSTEM_DESIGN.md"
)


def _requests() -> tuple[UnsupportedRequest, ...]:
    return load_unsupported_fixture(FIXTURE_PATH)


def _predictor(
    confidence: float, label: str = "card_arrival"
) -> Callable[[Sequence[str]], tuple[Sequence[float], Sequence[str]]]:
    def predict(texts: Sequence[str]) -> tuple[Sequence[float], Sequence[str]]:
        return [confidence] * len(texts), [label] * len(texts)

    return predict


def test_the_committed_fixture_loads_and_declares_every_field() -> None:
    requests = _requests()

    assert len(requests) >= 10
    for request in requests:
        assert request.request_id.strip()
        assert request.category in DECLARED_CATEGORIES
        assert request.rationale.strip(), f"{request.request_id} has no rationale"


def test_the_caveat_matches_the_specification_verbatim() -> None:
    """The mandated sentence is copied from the spec, not paraphrased.

    `ML_SYSTEM_DESIGN.md` fixes this wording. Asserting against the specification
    file rather than against a second copy of the string means a spec edit surfaces
    here instead of leaving the report quoting a sentence nobody approved.
    """

    specification = SPECIFICATION.read_text(encoding="utf-8")
    blockquote = " ".join(
        line.lstrip("> ").strip()
        for line in specification.splitlines()
        if line.startswith("> This curated fixture")
        or line.startswith("> benchmark and not evidence")
    )
    assert blockquote, "The mandated caveat is no longer in ML_SYSTEM_DESIGN.md"
    assert blockquote == UNSUPPORTED_FIXTURE_CAVEAT


def test_no_fixture_text_appears_in_any_banking77_split() -> None:
    """The plan's first mandated assertion, run against the real prepared splits.

    A row that exists in training data is not an unsupported request, and its
    abstention would measure memorisation rather than the abstention interface.
    """

    pytest.importorskip("datasets")
    from intentguard.config import load_foundation_config
    from intentguard.data import load_pinned_dataset, prepare_dataset

    config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
    prepared = prepare_dataset(load_pinned_dataset(config), config)

    assert_disjoint_from_splits(
        _requests(),
        {
            "train": [example.text for example in prepared.train],
            "validation": [example.text for example in prepared.validation],
            "test": [example.text for example in prepared.test],
        },
    )


def test_a_collision_is_refused_rather_than_silently_dropped() -> None:
    requests = _requests()
    colliding = {"train": [requests[0].text]}

    with pytest.raises(UnsupportedFixtureError, match="must not appear in any"):
        assert_disjoint_from_splits(requests, colliding)


def test_collision_detection_ignores_case_and_whitespace() -> None:
    """A row differing only in capitalisation is the same request.

    Comparing raw strings would let a trivially reformatted duplicate of a training
    example into the fixture, which is exactly the collision this guard exists to
    stop.
    """

    request = UnsupportedRequest(
        request_id="x",
        text="What is the weather forecast for Lisbon this weekend?",
        category="other_domain",
        rationale="r",
    )
    noisy = {"train": ["  what IS the   weather forecast for LISBON this weekend?  "]}

    with pytest.raises(UnsupportedFixtureError, match="collides with the train split"):
        assert_disjoint_from_splits([request], noisy)


def test_empty_fixture_text_does_not_collide_with_anything() -> None:
    """The empty request must not be reported as colliding with every split.

    Normalising an empty string yields an empty string, so a naive membership test
    would flag it against any split containing whitespace-only text.
    """

    request = UnsupportedRequest(
        request_id="empty", text="", category="empty", rationale="r"
    )
    assert_disjoint_from_splits([request], {"train": ["", "   "]})


def test_every_row_is_decided_exactly_once() -> None:
    requests = _requests()
    outcome = evaluate_unsupported_requests(
        requests, predict=_predictor(0.01), threshold=0.5
    )

    assert outcome.example_count == len(requests)
    assert len(outcome.samples) == len(requests)
    assert {sample.request_id for sample in outcome.samples} == {
        request.request_id for request in requests
    }
    assert outcome.abstained_count + outcome.accepted_count == outcome.example_count


def test_confidence_below_the_threshold_abstains() -> None:
    outcome = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.01), threshold=0.5
    )

    assert outcome.abstention_rate == 1.0
    assert outcome.accepted_count == 0
    assert all(sample.decision == "abstain" for sample in outcome.samples)


def test_confidence_above_the_threshold_is_reported_as_false_acceptance() -> None:
    """A wrongly accepted request must appear by category, not be smoothed away."""

    outcome = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.99), threshold=0.5
    )

    assert outcome.abstention_rate == 0.0
    assert outcome.accepted_count == outcome.example_count
    payload = outcome.payload()
    false_acceptances = payload["false_acceptances_by_category"]
    assert isinstance(false_acceptances, list)
    assert false_acceptances, "Accepted rows must be reported by category"


def test_the_accept_boundary_is_the_shared_decide_contract() -> None:
    """Confidence exactly at the threshold accepts, as `decide` defines it."""

    outcome = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.5), threshold=0.5
    )

    assert outcome.accepted_count == outcome.example_count


def test_the_payload_carries_the_caveat_and_denies_being_a_benchmark() -> None:
    payload = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.01), threshold=0.5
    ).payload()

    assert payload["caveat"] == UNSUPPORTED_FIXTURE_CAVEAT
    assert payload["is_ood_benchmark"] is False
    assert payload["is_general_detection_evidence"] is False
    assert payload["fixture_origin"] == "curated_by_hand"
    assert payload["fixture_schema_version"] == FIXTURE_SCHEMA_VERSION
    assert json.loads(json.dumps(payload)) == payload


def test_no_accuracy_is_reported_for_the_fixture() -> None:
    """Accuracy is undefined here: no BANKING77 label is correct for any row.

    Reporting one would invent a ground truth, so the payload states its absence
    and the reason rather than leaving a reader to wonder why it is missing.
    """

    payload = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.01), threshold=0.5
    ).payload()

    assert payload["accuracy_reported"] is False
    assert "undefined" in str(payload["accuracy_omitted_because"])
    assert "accuracy" not in {
        key for key in payload if key not in ("accuracy_reported", "accuracy_omitted_because")
    }
    samples = payload["samples"]
    assert isinstance(samples, list)
    for sample in samples:
        assert "correct" not in sample


def test_the_threshold_is_recorded_as_validation_selected() -> None:
    payload = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.01), threshold=0.168
    ).payload()

    assert payload["threshold"] == 0.168
    assert payload["threshold_selected_from"] == "validation"
    assert payload["threshold_source"] == "transformer_artifact"


def test_the_rendered_report_states_the_caveat_before_any_number() -> None:
    outcome = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.01), threshold=0.5
    )
    document = render_unsupported_markdown(
        outcome,
        contrast={
            "test_abstention_rate": 0.32,
            "test_mean_confidence": 0.2258,
            "fixture_mean_confidence": 0.05,
        },
    )

    assert UNSUPPORTED_FIXTURE_CAVEAT in document
    assert document.index(UNSUPPORTED_FIXTURE_CAVEAT) < document.index("abstention rate")


def test_a_total_abstention_rate_without_its_contrast_is_refused() -> None:
    """100% abstention alone is indistinguishable from abstaining on everything.

    The renderer refuses rather than printing a figure that reads as detection
    evidence. This is the overclaim AC-012 forbids, so it fails loudly.
    """

    outcome = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.01), threshold=0.5
    )
    assert outcome.abstention_rate == 1.0

    with pytest.raises(UnsupportedFixtureError, match="in-distribution contrast"):
        render_unsupported_markdown(outcome)


def test_a_partial_rate_renders_without_a_contrast() -> None:
    """The refusal is targeted at the total-abstention overclaim, not general use."""

    requests = _requests()

    def mixed(texts: Sequence[str]) -> tuple[Sequence[float], Sequence[str]]:
        return [0.9 if index == 0 else 0.01 for index in range(len(texts))], [
            "card_arrival"
        ] * len(texts)

    outcome = evaluate_unsupported_requests(requests, predict=mixed, threshold=0.5)
    assert 0.0 < outcome.abstention_rate < 1.0
    assert UNSUPPORTED_FIXTURE_CAVEAT in render_unsupported_markdown(outcome)


def test_the_rendered_report_names_the_intent_that_absorbed_a_request() -> None:
    outcome = evaluate_unsupported_requests(
        _requests(), predict=_predictor(0.99, label="card_arrival"), threshold=0.5
    )
    document = render_unsupported_markdown(outcome)

    assert "card_arrival" in document
    assert "False acceptances" in document


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('{"request_id": "a", "text": "t", "category": "nonsense"}', "rationale must be"),
        (
            '{"request_id": "a", "text": "t", "category": "made_up", "rationale": "r"}',
            "is not declared",
        ),
        (
            '{"request_id": " ", "text": "t", "category": "nonsense", "rationale": "r"}',
            "request_id must not be empty",
        ),
        (
            '{"request_id": "a", "text": "t", "category": "nonsense", "rationale": "r",'
            ' "extra": 1}',
            "unknown fields",
        ),
        ("not json at all", "invalid JSON"),
        ("[1, 2, 3]", "must be a JSON object"),
    ],
)
def test_malformed_rows_are_refused(tmp_path: Path, line: str, expected: str) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(line + "\n", encoding="utf-8")

    with pytest.raises(UnsupportedFixtureError, match=expected):
        load_unsupported_fixture(path)


def test_a_duplicate_request_id_is_refused(tmp_path: Path) -> None:
    row = '{"request_id": "a", "text": "%s", "category": "nonsense", "rationale": "r"}'
    path = tmp_path / "dupe.jsonl"
    path.write_text((row % "one") + "\n" + (row % "two") + "\n", encoding="utf-8")

    with pytest.raises(UnsupportedFixtureError, match="duplicate request_id"):
        load_unsupported_fixture(path)


def test_a_duplicate_text_is_refused(tmp_path: Path) -> None:
    """A repeated request would be counted twice and shift the rate."""

    path = tmp_path / "dupe.jsonl"
    path.write_text(
        '{"request_id": "a", "text": "same", "category": "nonsense", "rationale": "r"}\n'
        '{"request_id": "b", "text": "same", "category": "nonsense", "rationale": "r"}\n',
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedFixtureError, match="duplicate text"):
        load_unsupported_fixture(path)


def test_empty_text_is_permitted_because_it_is_a_declared_case(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text(
        '{"request_id": "a", "text": "", "category": "empty", "rationale": "r"}\n',
        encoding="utf-8",
    )

    requests = load_unsupported_fixture(path)
    assert requests[0].text == ""


def test_an_empty_fixture_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "none.jsonl"
    path.write_text("\n\n", encoding="utf-8")

    with pytest.raises(UnsupportedFixtureError, match="declares no requests"):
        load_unsupported_fixture(path)


def test_a_missing_fixture_is_refused(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFixtureError, match="No curated fixture exists"):
        load_unsupported_fixture(tmp_path / "absent.jsonl")


def test_a_predictor_returning_the_wrong_row_count_is_refused() -> None:
    def short(texts: Sequence[str]) -> tuple[Sequence[float], Sequence[str]]:
        return [0.1], ["card_arrival"]

    with pytest.raises(UnsupportedFixtureError, match="different number of rows"):
        evaluate_unsupported_requests(_requests(), predict=short, threshold=0.5)


def test_evaluation_requires_at_least_one_request() -> None:
    with pytest.raises(UnsupportedFixtureError, match="at least one request"):
        evaluate_unsupported_requests([], predict=_predictor(0.1), threshold=0.5)


def test_every_declared_category_is_represented_in_the_committed_fixture() -> None:
    """An unused category would mean the breakdown claims coverage it lacks."""

    present = {request.category for request in _requests()}
    assert present == set(DECLARED_CATEGORIES)


def test_required_fields_are_exactly_what_the_fixture_carries() -> None:
    """No intent label is present, so no fixture label can reach any decision."""

    assert set(REQUIRED_FIELDS) == {"request_id", "text", "category", "rationale"}
    assert "label" not in REQUIRED_FIELDS
    assert "label_id" not in REQUIRED_FIELDS
    assert "expected_intent" not in REQUIRED_FIELDS
