"""Curated unsupported-request fixture and its separately labelled report (FR-009, AC-012).

This is a **behavioral check**, not a benchmark. Twelve hand-written requests
cannot estimate out-of-distribution performance, and the report is required to say
so in the words the specification fixes. The distinction is not modesty: an
abstention rate computed over a fixture the author chose is a statement about the
author's imagination, and presenting it as a detection rate would be the exact
overclaim AC-012 exists to forbid.

Two rules keep the fixture honest:

* **No fixture text may appear in any BANKING77 split.** A row that collides with
  training data is not an unsupported request, and its abstention would be
  measuring memorisation instead of the abstention interface.
* **No fixture label influences anything.** The fixture carries no intent labels
  at all — only a category and a rationale — so there is nothing here that could
  reach threshold selection even in principle. The threshold arrives already
  selected from validation data.

Accuracy is undefined on these rows: there is no correct BANKING77 intent for
"what is the weather in Lisbon". Only the accept/abstain decision is meaningful,
which is why this report records abstention and never a metric that would imply a
right answer existed.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from intentguard.threshold import decide

FIXTURE_SCHEMA_VERSION: Final = 1

#: Fixed verbatim from `docs/specification/docs/ML_SYSTEM_DESIGN.md:187-189`. The
#: specification mandates this exact sentence in the report, so it is stored as a
#: constant and asserted by a test rather than retyped at each call site.
UNSUPPORTED_FIXTURE_CAVEAT: Final = (
    "This curated fixture is a behavioral check, not a representative OOD "
    "benchmark and not evidence of general unsupported-query detection."
)

REQUIRED_FIELDS: Final = ("request_id", "text", "category", "rationale")

#: The declared categories. A row outside this set is rejected rather than counted
#: under an ad-hoc name, so the per-category breakdown cannot silently acquire a
#: typo'd category with a count of one.
DECLARED_CATEGORIES: Final = (
    "other_domain",
    "prompt_injection",
    "nonsense",
    "empty",
    "non_english",
    "adjacent_banking",
)


class UnsupportedFixtureError(ValueError):
    """Raised when the curated fixture or its evaluation violates its contract."""


@dataclass(frozen=True, slots=True)
class UnsupportedRequest:
    """One curated request that no BANKING77 intent can correctly satisfy."""

    request_id: str
    text: str
    category: str
    rationale: str


@dataclass(frozen=True, slots=True)
class UnsupportedSample:
    """The accept/abstain outcome for one curated request.

    ``predicted_label_name`` is recorded even when the decision is ``abstain``,
    because the interesting failure is *which* intent a wrongly accepted request
    was mapped onto. There is deliberately no ``correct`` field: no label here is
    right, so a boolean would invent a ground truth the fixture does not have.
    """

    request_id: str
    text: str
    category: str
    rationale: str
    confidence: float
    predicted_label_name: str
    decision: str

    def payload(self) -> dict[str, object]:
        """Render one sample-level row for the report."""

        return {
            "request_id": self.request_id,
            "text": self.text,
            "category": self.category,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "predicted_label_name": self.predicted_label_name,
            "decision": self.decision,
        }


@dataclass(frozen=True, slots=True)
class CategoryOutcome:
    """Accept/abstain counts within one declared category."""

    category: str
    example_count: int
    abstained_count: int
    accepted_count: int
    abstention_rate: float

    def payload(self) -> dict[str, object]:
        return {
            "category": self.category,
            "example_count": self.example_count,
            "abstained_count": self.abstained_count,
            "accepted_count": self.accepted_count,
            "abstention_rate": self.abstention_rate,
        }


@dataclass(frozen=True, slots=True)
class UnsupportedOutcome:
    """The whole fixture's abstention behaviour at the persisted threshold."""

    threshold: float
    example_count: int
    abstained_count: int
    accepted_count: int
    abstention_rate: float
    by_category: tuple[CategoryOutcome, ...]
    samples: tuple[UnsupportedSample, ...]

    def payload(self) -> dict[str, object]:
        """Render the report block, caveat included by construction.

        The caveat is part of this payload rather than something a caller appends,
        so a report cannot present these counts without the sentence that bounds
        what they mean.
        """

        return {
            "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
            "caveat": UNSUPPORTED_FIXTURE_CAVEAT,
            "is_ood_benchmark": False,
            "is_general_detection_evidence": False,
            "fixture_origin": "curated_by_hand",
            "threshold": self.threshold,
            "threshold_source": "transformer_artifact",
            "threshold_selected_from": "validation",
            "example_count": self.example_count,
            "abstained_count": self.abstained_count,
            "accepted_count": self.accepted_count,
            "abstention_rate": self.abstention_rate,
            # Accuracy is absent by design: no BANKING77 label is correct for any
            # row here, so reporting one would invent a ground truth.
            "accuracy_reported": False,
            "accuracy_omitted_because": (
                "No BANKING77 intent is correct for these requests, so accuracy is "
                "undefined and only the accept/abstain decision is meaningful."
            ),
            "false_acceptances_by_category": [
                entry.payload() for entry in self.by_category if entry.accepted_count > 0
            ],
            "by_category": [entry.payload() for entry in self.by_category],
            "samples": [sample.payload() for sample in self.samples],
        }


def _require_string(row: Mapping[str, object], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise UnsupportedFixtureError(f"{where}: {field} must be a string")
    return value


def load_unsupported_fixture(path: Path) -> tuple[UnsupportedRequest, ...]:
    """Load the JSONL fixture, rejecting anything that would weaken the check.

    ``text`` is the one field allowed to be empty, because the empty and
    whitespace-only requests are themselves declared cases the classifier must
    handle. Every other field must be non-empty: a row without a rationale is a
    row nobody decided was unsupported, and a reviewer could not tell whether it
    belongs in the fixture at all.
    """

    if not path.is_file():
        raise UnsupportedFixtureError(f"No curated fixture exists at {path}")

    requests: list[UnsupportedRequest] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            where = f"{path.name}:{number}"
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as error:
                raise UnsupportedFixtureError(f"{where}: invalid JSON: {error}") from error
            if not isinstance(parsed, dict):
                raise UnsupportedFixtureError(f"{where}: each line must be a JSON object")
            unknown = set(parsed) - set(REQUIRED_FIELDS)
            if unknown:
                raise UnsupportedFixtureError(f"{where}: unknown fields {sorted(unknown)}")

            values = {field: _require_string(parsed, field, where) for field in REQUIRED_FIELDS}
            for field in ("request_id", "category", "rationale"):
                if not values[field].strip():
                    raise UnsupportedFixtureError(f"{where}: {field} must not be empty")
            if values["category"] not in DECLARED_CATEGORIES:
                raise UnsupportedFixtureError(
                    f"{where}: category {values['category']!r} is not declared"
                )
            if values["request_id"] in seen_ids:
                raise UnsupportedFixtureError(f"{where}: duplicate request_id")
            if values["text"] in seen_texts:
                raise UnsupportedFixtureError(
                    f"{where}: duplicate text; a repeated row would be counted twice"
                )
            seen_ids.add(values["request_id"])
            seen_texts.add(values["text"])
            requests.append(UnsupportedRequest(**values))

    if not requests:
        raise UnsupportedFixtureError(f"{path} declares no requests")
    return tuple(requests)


def assert_disjoint_from_splits(
    requests: Sequence[UnsupportedRequest],
    split_texts: Mapping[str, Sequence[str]],
) -> None:
    """Require no fixture text to appear in any BANKING77 split.

    Compared on text after case-folding and whitespace normalisation, because a
    collision that differs only in capitalisation is still the same request and
    would still make an abstention a measure of memorisation rather than of the
    abstention interface. Raises rather than filtering: a colliding row is an
    authoring error to fix, not something to drop silently and report a smaller
    fixture for.
    """

    def normalise(text: str) -> str:
        return " ".join(text.split()).casefold()

    known: dict[str, str] = {}
    for split_name, texts in split_texts.items():
        for text in texts:
            known.setdefault(normalise(text), split_name)

    collisions = [
        f"{request.request_id} collides with the {known[normalise(request.text)]} split"
        for request in requests
        if normalise(request.text) and normalise(request.text) in known
    ]
    if collisions:
        raise UnsupportedFixtureError(
            "Curated requests must not appear in any BANKING77 split: "
            + "; ".join(collisions)
        )


def evaluate_unsupported_requests(
    requests: Sequence[UnsupportedRequest],
    *,
    predict: Callable[[Sequence[str]], tuple[Sequence[float], Sequence[str]]],
    threshold: float,
) -> UnsupportedOutcome:
    """Decide each curated request once at the already-selected threshold.

    ``predict`` returns a confidence and a predicted label name per request; this
    function never fits, tunes, or selects. The threshold arrives as a parameter
    and every decision routes through :func:`intentguard.threshold.decide`, so the
    accept boundary here is the same one training recorded and serving will use.
    """

    if not requests:
        raise UnsupportedFixtureError("Unsupported evaluation requires at least one request")

    confidences, predicted_names = predict([request.text for request in requests])
    if len(confidences) != len(requests) or len(predicted_names) != len(requests):
        raise UnsupportedFixtureError(
            "The predictor returned a different number of rows than were requested"
        )

    samples = tuple(
        UnsupportedSample(
            request_id=request.request_id,
            text=request.text,
            category=request.category,
            rationale=request.rationale,
            confidence=float(confidence),
            predicted_label_name=str(name),
            decision=decide(float(confidence), threshold),
        )
        for request, confidence, name in zip(requests, confidences, predicted_names, strict=True)
    )

    total = len(samples)
    abstained = sum(1 for sample in samples if sample.decision == "abstain")

    by_category: list[CategoryOutcome] = []
    for category in DECLARED_CATEGORIES:
        members = [sample for sample in samples if sample.category == category]
        if not members:
            continue
        category_abstained = sum(1 for sample in members if sample.decision == "abstain")
        by_category.append(
            CategoryOutcome(
                category=category,
                example_count=len(members),
                abstained_count=category_abstained,
                accepted_count=len(members) - category_abstained,
                abstention_rate=category_abstained / len(members),
            )
        )

    return UnsupportedOutcome(
        threshold=threshold,
        example_count=total,
        abstained_count=abstained,
        accepted_count=total - abstained,
        abstention_rate=abstained / total,
        by_category=tuple(by_category),
        samples=samples,
    )


def render_unsupported_markdown(
    outcome: UnsupportedOutcome,
    *,
    contrast: Mapping[str, object] | None = None,
) -> str:
    """Render the separately labelled fixture report.

    The caveat is emitted before any number, so a reader who stops after the first
    paragraph has already been told what these counts are not.

    ``contrast`` carries the model's in-distribution abstention rate. It is optional
    only so the renderer stays usable in isolation; when the abstention rate is
    total, omitting it is refused, because "abstained on all 12" without "and did
    not abstain on the other data" is the sentence a reader would mistake for
    detection evidence.
    """

    if outcome.abstention_rate >= 1.0 and contrast is None:
        raise UnsupportedFixtureError(
            "A total abstention rate must be rendered with its in-distribution "
            "contrast: on its own it is indistinguishable from a model that "
            "abstains on everything"
        )

    lines = [
        "# Curated unsupported-request check",
        "",
        f"> {UNSUPPORTED_FIXTURE_CAVEAT}",
        "",
        (
            f"{outcome.example_count} hand-written requests were decided once each at "
            f"the persisted validation threshold {outcome.threshold:.6f}. "
            f"{outcome.abstained_count} abstained and {outcome.accepted_count} were "
            f"accepted, an abstention rate of {outcome.abstention_rate:.4f}."
        ),
        "",
        (
            "No accuracy is reported. No BANKING77 intent is correct for any of these "
            "requests, so only the accept/abstain decision carries meaning; a metric "
            "implying a right answer would invent one."
        ),
        "",
    ]

    if contrast is not None:
        test_rate = contrast.get("test_abstention_rate")
        test_mean = contrast.get("test_mean_confidence")
        fixture_mean = contrast.get("fixture_mean_confidence")
        if isinstance(test_rate, float) and isinstance(test_mean, float):
            lines.extend(
                [
                    "## Read against the in-distribution rate",
                    "",
                    (
                        f"The same model abstains on {test_rate:.4f} of the BANKING77 "
                        f"test split, so this fixture's "
                        f"{outcome.abstention_rate:.4f} is a contrast rather than a "
                        "model that abstains on everything."
                    ),
                    "",
                ]
            )
            if isinstance(fixture_mean, float):
                lines.extend(
                    [
                        (
                            f"Mean confidence is {fixture_mean:.4f} on these requests "
                            f"against {test_mean:.4f} on test. The separation, not the "
                            "rate, is what this check demonstrates."
                        ),
                        "",
                    ]
                )

    lines.extend(
        [
            "## By declared category",
            "",
            "| Category | Requests | Abstained | Accepted | Abstention rate |",
            "|---|---|---|---|---|",
        ]
    )
    for entry in outcome.by_category:
        lines.append(
            f"| {entry.category} | {entry.example_count} | {entry.abstained_count} "
            f"| {entry.accepted_count} | {entry.abstention_rate:.4f} |"
        )

    accepted = [sample for sample in outcome.samples if sample.decision == "accept"]
    lines.extend(["", "## False acceptances", ""])
    if accepted:
        lines.append(
            "Each row below was accepted with a confidence at or above the threshold "
            "despite having no correct intent. The predicted label is recorded because "
            "*which* intent absorbed the request is the diagnostic detail."
        )
        lines.extend(
            [
                "",
                "| Request | Category | Predicted intent | Confidence |",
                "|---|---|---|---|",
            ]
        )
        for sample in accepted:
            shown = sample.text if sample.text.strip() else "(empty)"
            lines.append(
                f"| {sample.request_id} | {sample.category} | "
                f"{sample.predicted_label_name} | {sample.confidence:.4f} |"
            )
            lines.append(f"| | | _{shown}_ | |")
    else:
        lines.append(
            "Every curated request abstained. On a fixture of this size that is a "
            "passed behavioral check, not a detection rate."
        )

    return "\n".join(lines) + "\n"
