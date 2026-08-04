"""The equivalence gate that makes a two-model comparison meaningful (FR-005, AC-004).

AC-004 requires the comparison to run on "the same test set". This module turns
that from an assumption into a runtime proof. Comparing two models is only
defensible when three things are established first:

* both bundles were built from the same dataset revision, so their labels refer
  to the same universe of intents;
* both bundles carry the same ordered label map, because that order is what fixes
  the column meaning of every probability vector;
* the test rows evaluated here are the same rows the recorded evidence describes.

The third point is the one an assumption cannot cover. Split fingerprints prove
two *bundles* agree with each other, but two bundles could agree and still both
disagree with the data the current process just prepared. So the locally prepared
test rows are re-fingerprinted and their example IDs re-hashed, and both must
match what is already recorded.

Every failure raises `EvaluationError`. Nothing here coerces, warns-and-continues,
or falls back to a subset intersection: a comparison across mismatched data is not
a degraded result, it is a meaningless one, and reporting it would be worse than
reporting nothing.

This module deliberately contains no metric arithmetic. Aggregate metrics come
from `intentguard.metrics`, whose semantics are pinned by a deliberately
imbalanced fixture. The test split here is exactly balanced (77 classes x 40), so
macro-F1 and weighted-F1 agree to reported precision on it and a swap between them
would be invisible; a second metric implementation living here would route around
the only guard that can catch that.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from intentguard.artifacts import ArtifactBundle, canonical_hash, label_map_hash
from intentguard.schemas import CanonicalExample, PreparedDataset
from intentguard.threshold import decide

COMPARED_PROVENANCE_FIELDS: Final = ("dataset_id", "dataset_revision", "label_map_hash")
COMPARED_SPLIT_NAMES: Final = ("train", "validation", "test")
TEST_EXAMPLE_ID_FIELD: Final = "test_example_id_sha256"
EVALUATED_SPLIT: Final = "test"
REPORT_SCHEMA_VERSION: Final = 1

# A macro-F1 gap narrower than this is reported as a tie rather than a win, because
# a difference at that scale is not evidence that one model is better. The value is
# declared in the report so the verdict is reproducible from recorded inputs rather
# than from a constant a reader has to go and find in the source.
COMPARISON_TOLERANCE: Final = 1e-6
COMPARISON_METRIC: Final = "macro_f1"
VERDICT_BASELINE_BETTER: Final = "baseline_better"
VERDICT_TRANSFORMER_BETTER: Final = "transformer_better"
VERDICT_EQUAL: Final = "equal_within_tolerance"


class EvaluationError(ValueError):
    """Raised when two artifacts cannot be compared on the same evaluation data."""


@dataclass(frozen=True, slots=True)
class SharedDataIdentity:
    """The data identity two bundles were proved to share.

    Carrying this as a value rather than re-deriving it downstream means the
    reported provenance is exactly what the gate checked, not a second lookup
    that could drift from it.
    """

    dataset_id: str
    dataset_revision: str
    label_map_hash: str
    label_names: tuple[str, ...]
    split_fingerprints: Mapping[str, str]
    test_example_id_sha256: str

    def payload(self) -> dict[str, object]:
        """Render the proved identity for inclusion in a report."""

        return {
            "dataset_id": self.dataset_id,
            "dataset_revision": self.dataset_revision,
            "label_map_hash": self.label_map_hash,
            "label_count": len(self.label_names),
            "split_fingerprints": dict(self.split_fingerprints),
            TEST_EXAMPLE_ID_FIELD: self.test_example_id_sha256,
            "evaluated_split": EVALUATED_SPLIT,
        }


def example_id_hash(examples: Sequence[CanonicalExample]) -> str:
    """Hash evaluated example IDs in order, identifying the exact rows scored.

    A split fingerprint covers text and labels; this covers row identity and
    order. `scripts/train_baseline.py` wrote the same hash into the baseline
    report from the same helper shape, and the gate below compares the two, so a
    divergence between them fails loudly at run time rather than silently
    producing two incomparable notions of "the test split".
    """

    if not examples:
        raise EvaluationError("Cannot hash an empty example sequence")
    return canonical_hash([example.example_id for example in examples])


def _provenance_string(bundle: ArtifactBundle, field: str) -> str:
    value = bundle.provenance.get(field)
    if not isinstance(value, str) or not value:
        raise EvaluationError(
            f"Bundle {bundle.run_id} has no usable {field!r} in its provenance"
        )
    return value


def _split_fingerprints(bundle: ArtifactBundle) -> dict[str, str]:
    raw = bundle.provenance.get("split_fingerprints")
    if not isinstance(raw, Mapping):
        raise EvaluationError(f"Bundle {bundle.run_id} has no split_fingerprints mapping")
    fingerprints: dict[str, str] = {}
    for name in COMPARED_SPLIT_NAMES:
        value = raw.get(name)
        if not isinstance(value, str) or not value:
            raise EvaluationError(
                f"Bundle {bundle.run_id} has no {name!r} split fingerprint"
            )
        fingerprints[name] = value
    return fingerprints


def assert_comparable_bundles(baseline: ArtifactBundle, transformer: ArtifactBundle) -> None:
    """Refuse to compare two bundles that were not built from the same data.

    All three split fingerprints are compared, not only the test one. A pair that
    agrees on test but disagrees on train or validation was produced by two
    different split derivations, which means the agreement on test is a
    coincidence of that particular seed rather than a shared contract.
    """

    for field in COMPARED_PROVENANCE_FIELDS:
        left = _provenance_string(baseline, field)
        right = _provenance_string(transformer, field)
        if left != right:
            raise EvaluationError(
                f"Artifacts disagree on {field!r} and cannot be compared: "
                f"{baseline.run_id} has {left!r}, {transformer.run_id} has {right!r}"
            )

    baseline_fingerprints = _split_fingerprints(baseline)
    transformer_fingerprints = _split_fingerprints(transformer)
    for name in COMPARED_SPLIT_NAMES:
        left = baseline_fingerprints[name]
        right = transformer_fingerprints[name]
        if left != right:
            raise EvaluationError(
                f"Artifacts disagree on the {name!r} split fingerprint and cannot be "
                f"compared: {baseline.run_id} has {left!r}, "
                f"{transformer.run_id} has {right!r}"
            )

    # The recorded hashes above already imply this, but the ordered label map is
    # what gives every probability column its meaning, so it is compared as data
    # rather than trusted through a hash of itself.
    if baseline.label_names != transformer.label_names:
        raise EvaluationError(
            f"Artifacts carry different ordered label maps and cannot be compared: "
            f"{baseline.run_id} has {len(baseline.label_names)} labels, "
            f"{transformer.run_id} has {len(transformer.label_names)} labels"
        )


def assert_prepared_dataset_matches(bundle: ArtifactBundle, prepared: PreparedDataset) -> None:
    """Require the locally prepared splits to be the ones the bundle was built on.

    Without this, two mutually consistent bundles could both be evaluated against
    a third, different dataset — every cross-bundle check would pass and every
    reported number would describe data no recorded evidence refers to.
    """

    recorded = _split_fingerprints(bundle)
    local = prepared.provenance.get("split_fingerprints")
    if not isinstance(local, Mapping):
        raise EvaluationError("Prepared dataset provenance has no split_fingerprints mapping")
    for name in COMPARED_SPLIT_NAMES:
        value = local.get(name)
        if not isinstance(value, str) or not value:
            raise EvaluationError(f"Prepared dataset has no {name!r} split fingerprint")
        if value != recorded[name]:
            raise EvaluationError(
                f"Locally prepared {name!r} split does not match bundle "
                f"{bundle.run_id}: prepared {value!r}, recorded {recorded[name]!r}"
            )

    local_label_hash = label_map_hash(prepared.label_names)
    recorded_label_hash = _provenance_string(bundle, "label_map_hash")
    if local_label_hash != recorded_label_hash:
        raise EvaluationError(
            f"Locally prepared label map does not match bundle {bundle.run_id}: "
            f"prepared {local_label_hash!r}, recorded {recorded_label_hash!r}"
        )
    if tuple(prepared.label_names) != bundle.label_names:
        raise EvaluationError(
            f"Locally prepared label map differs in order from bundle {bundle.run_id}"
        )


def read_recorded_test_example_id_hash(report_path: Path) -> str:
    """Read the test-row identity hash from an existing evaluation report.

    This value is evidence already published for the baseline. Reading it rather
    than recomputing a fresh expectation is the point: it is the fixed reference
    the current run has to reproduce.
    """

    if not report_path.is_file():
        raise EvaluationError(f"Recorded report does not exist: {report_path}")
    try:
        with report_path.open("rb") as stream:
            document = json.load(stream)
    except json.JSONDecodeError as error:
        raise EvaluationError(f"Recorded report is unreadable: {report_path}: {error}") from error
    if not isinstance(document, dict):
        raise EvaluationError(f"Recorded report is not a JSON object: {report_path}")

    value = cast(dict[str, object], document).get(TEST_EXAMPLE_ID_FIELD)
    if not isinstance(value, str) or not value:
        raise EvaluationError(
            f"Recorded report has no {TEST_EXAMPLE_ID_FIELD!r}: {report_path}"
        )
    return value


def resolve_shared_identity(
    *,
    baseline: ArtifactBundle,
    transformer: ArtifactBundle,
    prepared: PreparedDataset,
    recorded_test_example_id_sha256: str,
) -> SharedDataIdentity:
    """Run every equivalence check and return the identity both models are scored on.

    The ordering is deliberate: bundle-to-bundle first, then bundle-to-local-data,
    then row identity. Each step narrows what the next one can mean, so a failure
    message names the outermost thing that is actually wrong instead of a
    downstream symptom of it.
    """

    if not recorded_test_example_id_sha256:
        raise EvaluationError("A recorded test_example_id_sha256 is required to compare")

    assert_comparable_bundles(baseline, transformer)
    assert_prepared_dataset_matches(baseline, prepared)
    assert_prepared_dataset_matches(transformer, prepared)

    computed = example_id_hash(prepared.test)
    if computed != recorded_test_example_id_sha256:
        raise EvaluationError(
            "Locally prepared test rows are not the rows the recorded evidence "
            f"describes: computed {computed!r}, recorded "
            f"{recorded_test_example_id_sha256!r}"
        )

    return SharedDataIdentity(
        dataset_id=_provenance_string(baseline, "dataset_id"),
        dataset_revision=_provenance_string(baseline, "dataset_revision"),
        label_map_hash=_provenance_string(baseline, "label_map_hash"),
        label_names=baseline.label_names,
        split_fingerprints=_split_fingerprints(baseline),
        test_example_id_sha256=computed,
    )


@dataclass(frozen=True, slots=True)
class SelectiveOutcome:
    """Accept/abstain behaviour of one model at the persisted threshold.

    `accepted_accuracy` is accuracy *among accepted examples only* — the quantity
    selective prediction exists to improve. It is not comparable with the overall
    accuracy in the classification block, so both are reported with distinct names
    and `coverage` is always beside them to make the trade-off legible.
    """

    threshold: float
    example_count: int
    accepted_count: int
    abstained_count: int
    coverage: float
    accepted_accuracy: float
    selective_risk: float
    abstention_rate: float

    def payload(self) -> dict[str, object]:
        """Render the selective-prediction block for a report."""

        return {
            "threshold": self.threshold,
            "example_count": self.example_count,
            "accepted_count": self.accepted_count,
            "abstained_count": self.abstained_count,
            "coverage": self.coverage,
            "accepted_accuracy": self.accepted_accuracy,
            "selective_risk": self.selective_risk,
            "abstention_rate": self.abstention_rate,
        }


def apply_threshold(
    *,
    confidences: Sequence[float],
    correct: Sequence[bool],
    threshold: float,
) -> SelectiveOutcome:
    """Apply an already-selected threshold, deciding each example with `decide`.

    This function cannot select a threshold: the value arrives as a parameter and
    is used verbatim. Routing every decision through `threshold.decide` is what
    guarantees the accept boundary here is the same one training recorded and
    serving will use, including the exactly-at-threshold case.
    """

    if len(confidences) != len(correct):
        raise EvaluationError("Confidence and correctness lengths differ")
    if not confidences:
        raise EvaluationError("Selective evaluation requires at least one example")

    accepted_hits = 0
    accepted_count = 0
    for confidence, is_correct in zip(confidences, correct, strict=True):
        if decide(confidence, threshold) == "accept":
            accepted_count += 1
            if is_correct:
                accepted_hits += 1

    total = len(confidences)
    abstained = total - accepted_count
    # A run that accepts nothing has no accepted accuracy to report. Zero is used
    # rather than a division, matching `threshold.coverage_curve`'s convention for
    # the same degenerate point so the two cannot disagree.
    accepted_accuracy = (accepted_hits / accepted_count) if accepted_count else 0.0
    return SelectiveOutcome(
        threshold=float(threshold),
        example_count=total,
        accepted_count=accepted_count,
        abstained_count=abstained,
        coverage=accepted_count / total,
        accepted_accuracy=accepted_accuracy,
        selective_risk=1.0 - accepted_accuracy,
        abstention_rate=abstained / total,
    )


@dataclass(frozen=True, slots=True)
class ComparisonVerdict:
    """The signed outcome of comparing two models on one metric.

    `transformer_outperforms_baseline` is a literal boolean rather than a bare
    delta, because a reader cannot sign-flip a boolean by misreading which model
    was subtracted from which. AC-004 requires a negative result to be reported
    honestly; this is the field that makes "honestly" mechanical.
    """

    metric: str
    baseline_value: float
    transformer_value: float
    delta: float
    tolerance: float
    verdict: str
    transformer_outperforms_baseline: bool

    def payload(self) -> dict[str, object]:
        """Render the verdict block for a report."""

        return {
            "metric": self.metric,
            "baseline_value": self.baseline_value,
            "transformer_value": self.transformer_value,
            f"{self.metric}_delta": self.delta,
            "comparison_tolerance": self.tolerance,
            "verdict": self.verdict,
            "transformer_outperforms_baseline": self.transformer_outperforms_baseline,
        }


def compare_metric(
    *,
    baseline_value: float,
    transformer_value: float,
    metric: str = COMPARISON_METRIC,
    tolerance: float = COMPARISON_TOLERANCE,
) -> ComparisonVerdict:
    """Compare one metric and return a signed, named verdict.

    The delta is transformer minus baseline, so a negative delta means the
    transformer lost. A gap within `tolerance` is a tie, and a tie is *not* a win:
    `transformer_outperforms_baseline` is true only for a strict improvement beyond
    the tolerance.
    """

    if tolerance < 0.0:
        raise EvaluationError("Comparison tolerance must not be negative")

    delta = float(transformer_value) - float(baseline_value)
    if abs(delta) <= tolerance:
        verdict = VERDICT_EQUAL
        outperforms = False
    elif delta > 0.0:
        verdict = VERDICT_TRANSFORMER_BETTER
        outperforms = True
    else:
        verdict = VERDICT_BASELINE_BETTER
        outperforms = False

    return ComparisonVerdict(
        metric=metric,
        baseline_value=float(baseline_value),
        transformer_value=float(transformer_value),
        delta=delta,
        tolerance=float(tolerance),
        verdict=verdict,
        transformer_outperforms_baseline=outperforms,
    )


def _percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_comparison_markdown(
    *,
    run_id: str,
    identity: SharedDataIdentity,
    baseline_metrics: Mapping[str, object],
    transformer_metrics: Mapping[str, object],
    baseline_selective: SelectiveOutcome,
    transformer_selective: SelectiveOutcome,
    verdict: ComparisonVerdict,
    baseline_run_id: str,
    transformer_run_id: str,
) -> str:
    """Render the AC-004 comparison table plus the outcome stated in words.

    The prose sentence is not decoration. A table of numbers lets a reader who
    skims reach the wrong conclusion about which model won; AC-004 asks for the
    result to be *reported*, so the outcome is also written as a sentence that
    cannot be misread.
    """

    def _number(metrics: Mapping[str, object], key: str) -> float:
        value = metrics.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvaluationError(f"Metrics block has no numeric {key!r}")
        return float(value)

    if verdict.transformer_outperforms_baseline:
        sentence = (
            f"The fine-tuned DistilBERT outperformed the TF-IDF baseline on test "
            f"{verdict.metric} by {abs(verdict.delta):.4f}."
        )
    elif verdict.verdict == VERDICT_EQUAL:
        sentence = (
            f"The fine-tuned DistilBERT and the TF-IDF baseline are equal on test "
            f"{verdict.metric} within the declared tolerance of {verdict.tolerance:g}."
        )
    else:
        sentence = (
            f"The fine-tuned DistilBERT did not outperform the TF-IDF baseline on test "
            f"{verdict.metric}: it scored {verdict.transformer_value:.4f} against the "
            f"baseline's {verdict.baseline_value:.4f}, a shortfall of "
            f"{abs(verdict.delta):.4f}."
        )

    rows = [
        (
            "Accuracy",
            _number(baseline_metrics, "accuracy"),
            _number(transformer_metrics, "accuracy"),
        ),
        (
            "Macro-F1",
            _number(baseline_metrics, "macro_f1"),
            _number(transformer_metrics, "macro_f1"),
        ),
        (
            "Weighted-F1",
            _number(baseline_metrics, "weighted_f1"),
            _number(transformer_metrics, "weighted_f1"),
        ),
    ]

    lines = [
        "# IntentGuard comparative evaluation",
        "",
        f"Run ID: `{run_id}`",
        "",
        f"- Baseline artifact: `{baseline_run_id}`",
        f"- Transformer artifact: `{transformer_run_id}`",
        f"- Dataset: `{identity.dataset_id}` at revision `{identity.dataset_revision}`",
        f"- Evaluated split: `{identity.split_fingerprints['test'][:12]}…` "
        f"({baseline_selective.example_count} examples, "
        f"{len(identity.label_names)} labels)",
        "",
        "## Outcome",
        "",
        sentence,
        "",
        "## Classification metrics on the untouched test split",
        "",
        "| Metric | TF-IDF baseline | Fine-tuned DistilBERT | Delta |",
        "|---|---|---|---|",
    ]
    for name, left, right in rows:
        lines.append(f"| {name} | {left:.4f} | {right:.4f} | {right - left:+.4f} |")

    lines += [
        "",
        "Macro-F1 and weighted-F1 agree to the precision shown because every class "
        "has the same support on this split, which makes the weights uniform. They "
        "may still differ in the last floating-point digit, since the two averages "
        "sum in different orders. This report therefore cannot distinguish the two "
        "averaging modes; the imbalanced fixture in the test suite is what does.",
        "",
        "## Selective prediction at the persisted threshold",
        "",
        f"The threshold `{baseline_selective.threshold}` was selected from validation "
        "data during training and is applied here verbatim. It was never re-selected "
        "from test data.",
        "",
        "| Quantity | TF-IDF baseline | Fine-tuned DistilBERT |",
        "|---|---|---|",
        f"| Coverage | {_percentage(baseline_selective.coverage)} | "
        f"{_percentage(transformer_selective.coverage)} |",
        f"| Abstention rate | {_percentage(baseline_selective.abstention_rate)} | "
        f"{_percentage(transformer_selective.abstention_rate)} |",
        f"| Accepted accuracy | {baseline_selective.accepted_accuracy:.4f} | "
        f"{transformer_selective.accepted_accuracy:.4f} |",
        f"| Selective risk | {baseline_selective.selective_risk:.4f} | "
        f"{transformer_selective.selective_risk:.4f} |",
        "",
        "Accepted accuracy counts only accepted examples, so it is not comparable "
        "with the overall accuracy above.",
        "",
    ]
    return "\n".join(lines) + "\n"
