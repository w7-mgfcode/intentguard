"""The evaluation equivalence gate (FR-005, AC-004, step 2 of the E05 plan).

AC-004 requires both models to be compared on the same test set. These tests
prove the gate *rejects* every way that can fail, because a check that has never
been observed failing is not known to be a check.

Four mismatch classes are covered, each independently: dataset revision, label
map, split fingerprint, and test-row identity hash. They are exercised one at a
time from an otherwise-valid pair, so a test that passes tells you which specific
guard fired rather than merely that something did.

The structural guard at the bottom is the one worth reading twice. The test split
is exactly balanced (77 classes x 40 = 3,080), which makes macro-F1 and
weighted-F1 agree to reported precision there, so a swap between them cannot be
detected by any assertion about test numbers. Only the deliberately imbalanced
fixture in ``tests/fixtures/metric_regression.json`` can catch it, and it can only
do so while ``evaluation.py`` computes no metrics of its own.
"""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from intentguard import evaluation as evaluation_module
from intentguard.artifacts import ArtifactBundle, canonical_hash, label_map_hash
from intentguard.evaluation import (
    COMPARED_SPLIT_NAMES,
    TEST_EXAMPLE_ID_FIELD,
    EvaluationError,
    apply_threshold,
    assert_comparable_bundles,
    assert_prepared_dataset_matches,
    compare_metric,
    example_id_hash,
    read_recorded_test_example_id_hash,
    render_comparison_markdown,
    resolve_shared_identity,
)
from intentguard.schemas import CanonicalExample, PreparedDataset

DATASET_ID = "PolyAI/banking77"
DATASET_REVISION = "1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8"
LABEL_NAMES = ("card_arrival", "card_linking", "exchange_rate")
FINGERPRINTS = {
    "train": "a" * 64,
    "validation": "b" * 64,
    "test": "c" * 64,
}


def _examples(count: int = 3) -> tuple[CanonicalExample, ...]:
    return tuple(
        CanonicalExample(
            example_id=f"test-{index}",
            text=f"example text {index}",
            label_id=index % len(LABEL_NAMES),
            label_name=LABEL_NAMES[index % len(LABEL_NAMES)],
            split="test",
        )
        for index in range(count)
    )


def _bundle(
    *,
    artifact_name: str = "intentguard-baseline",
    run_id: str = "intentguard-baseline-1fb62b1bb463-059ee4b12214",
    dataset_revision: str = DATASET_REVISION,
    label_names: tuple[str, ...] = LABEL_NAMES,
    fingerprints: dict[str, str] | None = None,
    provenance_overrides: dict[str, object] | None = None,
) -> ArtifactBundle:
    provenance: dict[str, object] = {
        "artifact_name": artifact_name,
        "run_id": run_id,
        "dataset_id": DATASET_ID,
        "dataset_revision": dataset_revision,
        "label_map_hash": label_map_hash(label_names),
        "split_fingerprints": dict(fingerprints if fingerprints is not None else FINGERPRINTS),
        "seed": 42,
        "created_at": "2026-08-04T01:02:36.393948+00:00",
        "dependency_versions": {"numpy": "2.4.6"},
    }
    if provenance_overrides:
        provenance.update(provenance_overrides)
    return ArtifactBundle(
        artifact_name=artifact_name,
        run_id=run_id,
        directory=Path("artifacts") / artifact_name / run_id,
        config={},
        label_names=label_names,
        provenance=provenance,
        payload_files=("model.joblib",),
    )


def _transformer_bundle(**overrides: Any) -> ArtifactBundle:
    defaults: dict[str, Any] = {
        "artifact_name": "intentguard-distilbert",
        "run_id": "intentguard-distilbert-1fb62b1bb463-88e538757339",
    }
    defaults.update(overrides)
    return _bundle(**defaults)


def _prepared(
    *,
    examples: tuple[CanonicalExample, ...] | None = None,
    label_names: tuple[str, ...] = LABEL_NAMES,
    fingerprints: dict[str, str] | None = None,
) -> PreparedDataset:
    resolved = examples if examples is not None else _examples()
    return PreparedDataset(
        train=(),
        validation=(),
        test=resolved,
        label_names=label_names,
        provenance={
            "split_fingerprints": dict(
                fingerprints if fingerprints is not None else FINGERPRINTS
            ),
            "label_map_sha256": label_map_hash(label_names),
        },
    )


def _recorded_hash(examples: tuple[CanonicalExample, ...] | None = None) -> str:
    return example_id_hash(examples if examples is not None else _examples())


def test_a_matching_pair_resolves_to_the_shared_identity() -> None:
    identity = resolve_shared_identity(
        baseline=_bundle(),
        transformer=_transformer_bundle(),
        prepared=_prepared(),
        recorded_test_example_id_sha256=_recorded_hash(),
    )

    assert identity.dataset_id == DATASET_ID
    assert identity.dataset_revision == DATASET_REVISION
    assert identity.label_names == LABEL_NAMES
    assert dict(identity.split_fingerprints) == FINGERPRINTS
    assert identity.test_example_id_sha256 == _recorded_hash()


def test_shared_identity_payload_is_json_serialisable_and_names_the_split() -> None:
    payload = resolve_shared_identity(
        baseline=_bundle(),
        transformer=_transformer_bundle(),
        prepared=_prepared(),
        recorded_test_example_id_sha256=_recorded_hash(),
    ).payload()

    assert payload["evaluated_split"] == "test"
    assert payload["label_count"] == len(LABEL_NAMES)
    assert payload[TEST_EXAMPLE_ID_FIELD] == _recorded_hash()
    assert json.loads(json.dumps(payload)) == payload


# --- Mismatch class 1: dataset revision ---------------------------------------


def test_mismatched_dataset_revision_raises() -> None:
    with pytest.raises(EvaluationError, match="dataset_revision"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(dataset_revision="0" * 40),
            prepared=_prepared(),
            recorded_test_example_id_sha256=_recorded_hash(),
        )


def test_mismatched_dataset_id_raises() -> None:
    with pytest.raises(EvaluationError, match="dataset_id"):
        assert_comparable_bundles(
            _bundle(),
            _transformer_bundle(provenance_overrides={"dataset_id": "someone-else/banking77"}),
        )


# --- Mismatch class 2: label map ----------------------------------------------


def test_mismatched_label_map_hash_raises() -> None:
    with pytest.raises(EvaluationError, match="label_map_hash"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(label_names=("card_arrival", "card_linking")),
            prepared=_prepared(),
            recorded_test_example_id_sha256=_recorded_hash(),
        )


def test_reordered_label_map_is_caught_by_the_order_sensitive_hash() -> None:
    """A permuted label map changes what every probability column means.

    ``label_map_hash`` hashes the label *list*, so it is already order-sensitive
    and this is the guard that fires. Asserting the specific message keeps that
    fact visible: if the hash were ever made order-insensitive, this test fails
    rather than silently delegating to the check below.
    """

    reordered = (LABEL_NAMES[1], LABEL_NAMES[0], LABEL_NAMES[2])
    with pytest.raises(EvaluationError, match="disagree on 'label_map_hash'"):
        assert_comparable_bundles(_bundle(), _transformer_bundle(label_names=reordered))


def test_ordered_label_comparison_catches_what_a_forged_hash_would_hide() -> None:
    """The defence-in-depth branch, exercised rather than merely asserted.

    Both bundles are forced to advertise the *same* ``label_map_hash`` while
    carrying different ordered label maps, so the hash check above passes and only
    the direct comparison of label names can fail. Real bundles cannot reach this
    state — ``load_artifact`` re-derives the hash from the saved label map — so
    this covers a hand-edited or corrupted ``provenance.json``.
    """

    reordered = (LABEL_NAMES[1], LABEL_NAMES[0], LABEL_NAMES[2])
    forged = label_map_hash(LABEL_NAMES)
    with pytest.raises(EvaluationError, match="different ordered label maps"):
        assert_comparable_bundles(
            _bundle(),
            _transformer_bundle(
                label_names=reordered,
                provenance_overrides={"label_map_hash": forged},
            ),
        )


def test_prepared_label_map_order_must_match_the_bundle() -> None:
    bundle = _bundle()
    reordered = (LABEL_NAMES[1], LABEL_NAMES[0], LABEL_NAMES[2])
    with pytest.raises(EvaluationError, match="label map"):
        assert_prepared_dataset_matches(bundle, _prepared(label_names=reordered))


# --- Mismatch class 3: split fingerprints -------------------------------------


@pytest.mark.parametrize("split_name", COMPARED_SPLIT_NAMES)
def test_any_mismatched_split_fingerprint_raises(split_name: str) -> None:
    """Train and validation are checked too, not only test.

    A pair agreeing on test while disagreeing on train came from two different
    split derivations, so its test agreement is a coincidence rather than a
    contract.
    """

    diverged = dict(FINGERPRINTS) | {split_name: "f" * 64}
    with pytest.raises(EvaluationError, match=f"{split_name!r} split fingerprint"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(fingerprints=diverged),
            prepared=_prepared(),
            recorded_test_example_id_sha256=_recorded_hash(),
        )


def test_locally_prepared_split_fingerprint_must_match_the_bundles() -> None:
    """Two mutually consistent bundles can still both disagree with local data."""

    diverged = dict(FINGERPRINTS) | {"test": "d" * 64}
    with pytest.raises(EvaluationError, match="Locally prepared 'test' split"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(),
            prepared=_prepared(fingerprints=diverged),
            recorded_test_example_id_sha256=_recorded_hash(),
        )


def test_absent_split_fingerprint_raises_rather_than_defaulting() -> None:
    incomplete = {"train": "a" * 64, "validation": "b" * 64}
    with pytest.raises(EvaluationError, match="'test' split fingerprint"):
        assert_comparable_bundles(_bundle(), _transformer_bundle(fingerprints=incomplete))


# --- Mismatch class 4: test-row identity --------------------------------------


def test_mismatched_test_example_id_hash_raises() -> None:
    with pytest.raises(EvaluationError, match="not the rows the recorded evidence"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(),
            prepared=_prepared(),
            recorded_test_example_id_sha256=canonical_hash(["not-these-rows"]),
        )


def test_reordered_test_rows_raise_even_though_the_set_is_identical() -> None:
    """Row order fixes the alignment between predictions and truth."""

    rows = _examples()
    shuffled = (rows[1], rows[0], rows[2])
    with pytest.raises(EvaluationError, match="not the rows the recorded evidence"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(),
            prepared=_prepared(examples=shuffled),
            recorded_test_example_id_sha256=_recorded_hash(rows),
        )


def test_a_dropped_test_row_raises() -> None:
    rows = _examples()
    with pytest.raises(EvaluationError, match="not the rows the recorded evidence"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(),
            prepared=_prepared(examples=rows[:-1]),
            recorded_test_example_id_sha256=_recorded_hash(rows),
        )


def test_an_empty_recorded_hash_raises_rather_than_being_skipped() -> None:
    with pytest.raises(EvaluationError, match="recorded test_example_id_sha256 is required"):
        resolve_shared_identity(
            baseline=_bundle(),
            transformer=_transformer_bundle(),
            prepared=_prepared(),
            recorded_test_example_id_sha256="",
        )


def test_example_id_hash_depends_only_on_ids_in_order() -> None:
    rows = _examples()
    retexted = tuple(replace(row, text=f"rewritten {row.example_id}") for row in rows)

    assert example_id_hash(retexted) == example_id_hash(rows)
    assert example_id_hash(rows) == canonical_hash([row.example_id for row in rows])


def test_example_id_hash_refuses_an_empty_sequence() -> None:
    with pytest.raises(EvaluationError, match="empty example sequence"):
        example_id_hash(())


# --- Reading the recorded reference ------------------------------------------


def test_recorded_hash_is_read_from_a_report(tmp_path: Path) -> None:
    report = tmp_path / "metrics.json"
    report.write_text(json.dumps({TEST_EXAMPLE_ID_FIELD: "e" * 64}), encoding="utf-8")

    assert read_recorded_test_example_id_hash(report) == "e" * 64


def test_absent_report_raises(tmp_path: Path) -> None:
    with pytest.raises(EvaluationError, match="does not exist"):
        read_recorded_test_example_id_hash(tmp_path / "missing.json")


def test_report_without_the_field_raises(tmp_path: Path) -> None:
    report = tmp_path / "metrics.json"
    report.write_text(json.dumps({"accuracy": 0.5}), encoding="utf-8")

    with pytest.raises(EvaluationError, match=TEST_EXAMPLE_ID_FIELD):
        read_recorded_test_example_id_hash(report)


def test_unreadable_report_raises(tmp_path: Path) -> None:
    report = tmp_path / "metrics.json"
    report.write_text("{not json", encoding="utf-8")

    with pytest.raises(EvaluationError, match="unreadable"):
        read_recorded_test_example_id_hash(report)


# --- Structural guards -------------------------------------------------------


def test_selective_outcome_counts_and_rates_are_consistent() -> None:
    outcome = apply_threshold(
        confidences=[0.9, 0.8, 0.4, 0.2],
        correct=[True, False, True, True],
        threshold=0.5,
    )

    assert outcome.accepted_count == 2
    assert outcome.abstained_count == 2
    assert outcome.coverage == pytest.approx(0.5)
    assert outcome.abstention_rate == pytest.approx(0.5)
    assert outcome.accepted_accuracy == pytest.approx(0.5)
    assert outcome.selective_risk == pytest.approx(0.5)
    assert outcome.coverage + outcome.abstention_rate == pytest.approx(1.0)
    assert outcome.accepted_accuracy + outcome.selective_risk == pytest.approx(1.0)


def test_a_confidence_exactly_at_the_threshold_is_accepted() -> None:
    """The boundary is `confidence >= threshold`, shared with training and serving."""

    outcome = apply_threshold(confidences=[0.5], correct=[True], threshold=0.5)

    assert outcome.accepted_count == 1
    assert outcome.coverage == pytest.approx(1.0)


def test_accepting_nothing_reports_zero_accuracy_rather_than_dividing() -> None:
    outcome = apply_threshold(confidences=[0.1, 0.2], correct=[True, True], threshold=0.9)

    assert outcome.accepted_count == 0
    assert outcome.coverage == pytest.approx(0.0)
    assert outcome.accepted_accuracy == pytest.approx(0.0)
    assert outcome.selective_risk == pytest.approx(1.0)


def test_apply_threshold_rejects_mismatched_lengths_and_empty_input() -> None:
    with pytest.raises(EvaluationError, match="lengths differ"):
        apply_threshold(confidences=[0.9], correct=[True, False], threshold=0.5)
    with pytest.raises(EvaluationError, match="at least one example"):
        apply_threshold(confidences=[], correct=[], threshold=0.5)


def test_a_transformer_loss_is_reported_as_a_loss() -> None:
    """AC-004's negative-result path, which is the outcome this project expects."""

    verdict = compare_metric(baseline_value=0.8654, transformer_value=0.6541)

    assert verdict.verdict == "baseline_better"
    assert verdict.transformer_outperforms_baseline is False
    assert verdict.delta < 0.0
    assert verdict.payload()["macro_f1_delta"] == pytest.approx(0.6541 - 0.8654)


def test_a_transformer_win_is_reported_as_a_win() -> None:
    verdict = compare_metric(baseline_value=0.6541, transformer_value=0.8654)

    assert verdict.verdict == "transformer_better"
    assert verdict.transformer_outperforms_baseline is True
    assert verdict.delta > 0.0


def test_a_gap_within_tolerance_is_a_tie_and_not_a_win() -> None:
    verdict = compare_metric(
        baseline_value=0.5, transformer_value=0.5 + 1e-9, tolerance=1e-6
    )

    assert verdict.verdict == "equal_within_tolerance"
    assert verdict.transformer_outperforms_baseline is False


def test_outperforms_flag_is_a_literal_boolean() -> None:
    """A boolean cannot be sign-flipped by a reader who misreads the subtraction."""

    payload = compare_metric(baseline_value=0.9, transformer_value=0.1).payload()

    assert payload["transformer_outperforms_baseline"] is False
    assert isinstance(payload["transformer_outperforms_baseline"], bool)


def test_negative_tolerance_is_rejected() -> None:
    with pytest.raises(EvaluationError, match="tolerance must not be negative"):
        compare_metric(baseline_value=0.5, transformer_value=0.6, tolerance=-1e-9)


def _rendered(baseline_macro: float, transformer_macro: float) -> str:
    identity = resolve_shared_identity(
        baseline=_bundle(),
        transformer=_transformer_bundle(),
        prepared=_prepared(),
        recorded_test_example_id_sha256=_recorded_hash(),
    )
    baseline_metrics = {
        "accuracy": 0.87,
        "macro_f1": baseline_macro,
        "weighted_f1": baseline_macro,
    }
    transformer_metrics = {
        "accuracy": 0.72,
        "macro_f1": transformer_macro,
        "weighted_f1": transformer_macro,
    }
    selective = apply_threshold(
        confidences=[0.9, 0.4, 0.8], correct=[True, False, True], threshold=0.5
    )
    return render_comparison_markdown(
        run_id="intentguard-evaluation-1fb62b1bb463-abcdef123456",
        identity=identity,
        baseline_metrics=baseline_metrics,
        transformer_metrics=transformer_metrics,
        baseline_selective=selective,
        transformer_selective=selective,
        verdict=compare_metric(
            baseline_value=baseline_macro, transformer_value=transformer_macro
        ),
        baseline_run_id="intentguard-baseline-1fb62b1bb463-059ee4b12214",
        transformer_run_id="intentguard-distilbert-1fb62b1bb463-88e538757339",
    )


def test_markdown_states_a_loss_in_words_that_cannot_read_as_a_win() -> None:
    document = _rendered(0.8654, 0.6541)

    assert "did not outperform" in document
    assert "outperformed the TF-IDF baseline" not in document


def test_markdown_states_a_win_in_words_when_the_transformer_wins() -> None:
    document = _rendered(0.6541, 0.8654)

    assert "outperformed the TF-IDF baseline" in document
    assert "did not outperform" not in document


def test_markdown_explains_why_macro_and_weighted_coincide() -> None:
    """A reader must not mistake the matching columns for a copy-paste error."""

    document = _rendered(0.8654, 0.6541)

    assert "same support" in document
    assert "| Macro-F1 |" in document
    assert "| Weighted-F1 |" in document


def test_markdown_records_that_the_threshold_was_not_reselected() -> None:
    document = _rendered(0.8654, 0.6541)

    assert "selected from validation" in document
    assert "never re-selected" in document


def test_markdown_distinguishes_accepted_accuracy_from_overall_accuracy() -> None:
    document = _rendered(0.8654, 0.6541)

    assert "not comparable" in document


def test_evaluation_never_imports_threshold_selection() -> None:
    """Selecting a threshold during evaluation would read test labels (AC-005).

    The threshold is chosen from validation data at training time and persisted.
    Evaluation applies it; it must never re-derive it.
    """

    source = Path(evaluation_module.__file__).read_text(encoding="utf-8")

    assert "select_threshold" not in source
    assert not hasattr(evaluation_module, "select_threshold")


def test_the_evaluate_script_cannot_select_a_threshold_or_fit_a_model() -> None:
    """AC-005 at the script boundary, enforced by parsing rather than by reading.

    ``evaluation.py`` is guarded above, but the orchestration script is where an
    "just re-tune it quickly" edit would actually land. Only real import
    statements and calls are inspected, so the prose in the module docstring that
    *names* these functions does not satisfy or defeat the check.
    """

    script = Path(__file__).resolve().parents[2] / "scripts" / "evaluate.py"
    tree = ast.parse(script.read_text(encoding="utf-8"))

    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                called.add(target.id)
            elif isinstance(target, ast.Attribute):
                called.add(target.attr)

    for forbidden in ("select_threshold", "fit_pipeline", "train_batches", "save_artifact"):
        assert forbidden not in imported, f"{forbidden} must not be imported by evaluate.py"
        assert forbidden not in called, f"{forbidden} must not be called by evaluate.py"

    # Evaluation reads artifacts; it must never publish one.
    assert "load_artifact" in imported


def test_evaluation_computes_no_metrics_of_its_own() -> None:
    """The macro/weighted trap: a second F1 here would bypass the only guard.

    Test support is uniform, so macro-F1 and weighted-F1 agree to reported
    precision on it and a swap is invisible.
    ``tests/fixtures/metric_regression.json`` is deliberately
    imbalanced and is the only thing that can catch such a change — which it can
    only do while every metric flows through ``intentguard.metrics``.
    """

    source = Path(evaluation_module.__file__).read_text(encoding="utf-8")

    for forbidden in ("f1_score", "precision_recall_fscore_support", "accuracy_score"):
        assert forbidden not in source, (
            f"{forbidden} must not be reimplemented in evaluation.py; call "
            "intentguard.metrics so the imbalanced regression fixture stays "
            "load-bearing"
        )
    assert "import sklearn" not in source
    assert "from sklearn" not in source
