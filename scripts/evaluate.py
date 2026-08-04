"""Compare both sealed artifacts on the untouched test split (AC-004, FR-005).

The order of operations here is the correctness control, not a convention:

1. both bundles are loaded from disk and every checksum re-verified;
2. the equivalence gate proves they describe the same data as each other *and* as
   the locally prepared splits, or the run fails;
3. the threshold is read from the transformer bundle, never selected here;
4. each model predicts over the test split through its reloaded artifact only;
5. every probability matrix is proven to be row-stochastic *before* any confidence
   derived from it is consumed;
6. metrics, selective prediction, calibration, and the risk/coverage curve all come
   from one pass over those probabilities, so the test split is read exactly once;
7. the curated unsupported-request fixture is proven disjoint from every split and
   then decided once per row at the same threshold, reported separately;
8. latency is measured last, from the same reloaded artifacts, and the report is
   written.

Nothing in this script fits, trains, or tunes. It calls neither `fit_pipeline` nor
`select_threshold`, so no test label can reach a modelling decision: the only
thing a test label is allowed to influence is a reported number. The risk/coverage
curve is a description of the trade-off, not a selection — no point on it is
chosen, and writing it down is not the same as tuning to it.

Per AC-004 the outcome is reported whichever way it falls. A transformer that
loses to the lexical baseline is a measured result, and this script writes it down
plainly rather than softening it.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Callable, Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final

import joblib  # type: ignore[import-untyped]
import numpy as np
import torch
from numpy.typing import NDArray

from intentguard.artifacts import (
    ArtifactBundle,
    ArtifactError,
    compute_run_id,
    dependency_versions,
    load_artifact,
)
from intentguard.baseline import BaselineError
from intentguard.baseline import predict_probabilities as baseline_probabilities
from intentguard.config import FoundationConfig, load_foundation_config
from intentguard.data import DataContractError, load_pinned_dataset, prepare_dataset
from intentguard.evaluation import (
    COMPARISON_METRIC,
    COMPARISON_TOLERANCE,
    REPORT_SCHEMA_VERSION,
    EvaluationError,
    SelectiveOutcome,
    SharedDataIdentity,
    apply_threshold,
    compare_metric,
    read_recorded_test_example_id_hash,
    render_comparison_markdown,
    resolve_shared_identity,
)
from intentguard.latency import (
    LATENCY_CAVEAT,
    MEASURED_REQUESTS,
    SAMPLE_SEED,
    WARM_UP_REQUESTS,
    LatencyError,
    LatencyMeasurement,
    latency_environment,
    measure_latency,
    select_latency_samples,
)
from intentguard.metrics import (
    CALIBRATION_BIN_COUNT,
    CALIBRATION_BINNING,
    METRIC_VERSION,
    CalibrationMetrics,
    ClassificationMetrics,
    calibration_payload,
    compute_calibration_metrics,
    compute_classification_metrics,
    metrics_payload,
)
from intentguard.schemas import CanonicalExample, PreparedDataset
from intentguard.threshold import CoveragePoint, coverage_curve
from intentguard.training import (
    TrainingError,
    confidences_from_probabilities,
    labels_from_probabilities,
    load_model_from_directory,
    load_tokenizer_from_directory,
    move_to_device,
    resolve_device,
)
from intentguard.training import predict_probabilities as transformer_probabilities
from intentguard.unsupported import (
    FIXTURE_SCHEMA_VERSION,
    UNSUPPORTED_FIXTURE_CAVEAT,
    UnsupportedFixtureError,
    UnsupportedOutcome,
    assert_disjoint_from_splits,
    evaluate_unsupported_requests,
    load_unsupported_fixture,
    render_unsupported_markdown,
)

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
EVALUATION_NAME: Final = "intentguard-evaluation"
BASELINE_ARTIFACT_NAME: Final = "intentguard-baseline"
TRANSFORMER_ARTIFACT_NAME: Final = "intentguard-distilbert"
BASELINE_MODEL_FILENAME: Final = "model.joblib"
TRANSFORMER_MODEL_DIRECTORY: Final = "model"
TRANSFORMER_TOKENIZER_DIRECTORY: Final = "tokenizer"
BASELINE_REPORT_FILENAME: Final = "metrics.json"
COMPARISON_JSON_FILENAME: Final = "comparison.json"
COMPARISON_MARKDOWN_FILENAME: Final = "comparison.md"
UNSUPPORTED_JSON_FILENAME: Final = "unsupported_fixture.json"
UNSUPPORTED_MARKDOWN_FILENAME: Final = "unsupported_fixture.md"
UNSUPPORTED_FIXTURE_PATH: Final = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "unsupported_requests.jsonl"
)
TRACKED_DEPENDENCIES: Final = (
    "joblib",
    "numpy",
    "scikit-learn",
    "torch",
    "transformers",
)
PROBABILITY_SUM_TOLERANCE: Final = 1e-9


def _write_text_atomically(path: Path, document: str) -> None:
    """Write a report so a reader never observes a partial file.

    Unlike an artifact bundle, a report is rewritten on every run rather than
    sealed. Atomic replacement is what keeps "rewritten" from ever meaning
    "briefly truncated".
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(document)
        temporary.replace(path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _write_json_atomically(path: Path, payload: object) -> None:
    document = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _write_text_atomically(path, document)


def _texts_and_labels(
    examples: tuple[CanonicalExample, ...],
) -> tuple[list[str], list[int]]:
    return [example.text for example in examples], [example.label_id for example in examples]


def _require_bundle(config: FoundationConfig, artifact_name: str) -> ArtifactBundle:
    """Load the single bundle for one artifact name, refusing an ambiguous choice.

    A stale sibling bundle from a superseded configuration must not be picked up
    silently. If more than one directory is present the run stops and names them,
    because guessing which one the recorded evidence refers to is exactly the kind
    of inference that produces a report attributing metrics to the wrong model.
    """

    parent = config.artifact_root / artifact_name
    if not parent.is_dir():
        raise EvaluationError(
            f"No {artifact_name} artifact directory exists at {parent}. "
            "Run `make baseline` and `make train` before `make evaluate`."
        )
    candidates = sorted(entry for entry in parent.iterdir() if entry.is_dir())
    if not candidates:
        raise EvaluationError(f"No {artifact_name} bundle exists under {parent}")
    if len(candidates) > 1:
        names = [entry.name for entry in candidates]
        raise EvaluationError(
            f"{parent} holds {len(candidates)} bundles and the one to evaluate is "
            f"ambiguous: {names}. Remove the superseded bundle or evaluate an "
            "explicit run."
        )
    return load_artifact(candidates[0])


def _assert_probability_rows(probabilities: NDArray[np.float64], model_name: str) -> None:
    """Require each row to be a distribution before it is used as a confidence.

    The maximum of a row is only a confidence if the row sums to one. Checking here
    means a softmax-axis or column-order mistake fails as an evaluation error rather
    than quietly becoming a plausible-looking abstention rate.
    """

    row_sums = probabilities.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=PROBABILITY_SUM_TOLERANCE, rtol=0.0):
        raise EvaluationError(
            f"{model_name} probability rows do not sum to one within tolerance"
        )


def _baseline_predictions(
    bundle: ArtifactBundle, texts: list[str], label_count: int
) -> NDArray[np.float64]:
    """Predict from the reloaded baseline artifact, never from an in-memory model."""

    model = joblib.load(bundle.path(BASELINE_MODEL_FILENAME))
    probabilities = baseline_probabilities(model, texts, label_count=label_count)
    _assert_probability_rows(probabilities, "Baseline")
    return probabilities


def _transformer_predictions(
    bundle: ArtifactBundle,
    config: FoundationConfig,
    texts: list[str],
    label_names: tuple[str, ...],
) -> NDArray[np.float64]:
    """Predict from the reloaded transformer artifact on the resolved device."""

    device = resolve_device()
    tokenizer = load_tokenizer_from_directory(
        bundle.directory_path(TRANSFORMER_TOKENIZER_DIRECTORY)
    )
    model = move_to_device(
        load_model_from_directory(
            bundle.directory_path(TRANSFORMER_MODEL_DIRECTORY), label_names
        ),
        device,
    )
    probabilities = transformer_probabilities(
        model,
        tokenizer,
        texts,
        label_count=len(label_names),
        training=config.training,
        device=device,
    )
    _assert_probability_rows(probabilities, "Transformer")
    return probabilities


def _token_lengths(
    bundle: ArtifactBundle, texts: list[str], config: FoundationConfig
) -> list[int]:
    """Tokenise once to record what the latency samples actually represent.

    Reported so a reader can see the spread that produced p95. This runs outside
    the timed region and is not part of any measurement.
    """

    tokenizer = load_tokenizer_from_directory(
        bundle.directory_path(TRANSFORMER_TOKENIZER_DIRECTORY)
    )
    encoded = tokenizer(
        texts,
        truncation=True,
        max_length=config.training.max_sequence_length,
    )
    return [len(ids) for ids in encoded["input_ids"]]


def _baseline_single_request(
    bundle: ArtifactBundle, label_count: int
) -> Callable[[str], None]:
    """Build a one-text baseline predictor for timing.

    The model is loaded once, before timing, because a request in service does not
    pay artifact load and re-hashing. Vectorisation stays inside the timed call,
    since a request genuinely pays it.
    """

    model = joblib.load(bundle.path(BASELINE_MODEL_FILENAME))

    def predict_one(text: str) -> None:
        baseline_probabilities(model, [text], label_count=label_count)

    return predict_one


def _transformer_single_request(
    bundle: ArtifactBundle, config: FoundationConfig, label_names: tuple[str, ...]
) -> Callable[[str], None]:
    """Build a one-text transformer predictor for timing, tokenisation included."""

    device = resolve_device()
    tokenizer = load_tokenizer_from_directory(
        bundle.directory_path(TRANSFORMER_TOKENIZER_DIRECTORY)
    )
    model = move_to_device(
        load_model_from_directory(
            bundle.directory_path(TRANSFORMER_MODEL_DIRECTORY), label_names
        ),
        device,
    )

    def predict_one(text: str) -> None:
        transformer_probabilities(
            model,
            tokenizer,
            [text],
            label_count=len(label_names),
            training=config.training,
            device=device,
        )

    return predict_one


def _fixture_content_hash(path: Path) -> str:
    """Hash the fixture bytes so the run ID tracks the fixture that was evaluated."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unsupported_outcome(
    bundle: ArtifactBundle,
    config: FoundationConfig,
    label_names: tuple[str, ...],
    prepared: PreparedDataset,
    threshold: float,
) -> UnsupportedOutcome:
    """Run the curated fixture through the transformer artifact serving will load.

    Measured on the transformer rather than the baseline because the transformer is
    the artifact the API loads, so this is the abstention behaviour a caller would
    actually encounter. The disjointness proof runs *before* prediction: if a row
    turns out to collide with a split, the honest response is to fix the fixture,
    not to publish an abstention rate that partly measures memorisation.
    """

    requests = load_unsupported_fixture(UNSUPPORTED_FIXTURE_PATH)
    assert_disjoint_from_splits(
        requests,
        {
            "train": [example.text for example in prepared.train],
            "validation": [example.text for example in prepared.validation],
            "test": [example.text for example in prepared.test],
        },
    )

    def predict(texts: Sequence[str]) -> tuple[Sequence[float], Sequence[str]]:
        probabilities = _transformer_predictions(bundle, config, list(texts), label_names)
        confidences = confidences_from_probabilities(probabilities)
        predicted = labels_from_probabilities(probabilities)
        return confidences, [label_names[index] for index in predicted]

    return evaluate_unsupported_requests(
        requests,
        predict=predict,
        threshold=threshold,
    )


def _in_distribution_contrast(
    unsupported: UnsupportedOutcome,
    *,
    transformer_selective: SelectiveOutcome,
    transformer_calibration: CalibrationMetrics,
) -> dict[str, object]:
    """Add the in-distribution contrast that decides whether the result means anything.

    A 100% abstention rate on this fixture is only evidence of discrimination if the
    same model does *not* abstain on everything. Since this transformer is
    underconfident overall, that objection is live and has to be answered with
    numbers rather than assumed away — so the block carries the model's test-split
    abstention rate and mean confidence beside the fixture's own.

    The interpretation is derived, not asserted: if a future run abstains on the
    fixture while also abstaining on nearly all test data, `discriminates` becomes
    false and the recorded conclusion changes with it.
    """

    fixture_confidences = [sample.confidence for sample in unsupported.samples]
    fixture_mean = sum(fixture_confidences) / len(fixture_confidences)
    separation = transformer_calibration.mean_confidence - fixture_mean
    return {
        "test_abstention_rate": transformer_selective.abstention_rate,
        "test_mean_confidence": transformer_calibration.mean_confidence,
        "fixture_mean_confidence": fixture_mean,
        "fixture_max_confidence": max(fixture_confidences),
        "mean_confidence_separation": separation,
        "discriminates": (
            unsupported.abstention_rate > transformer_selective.abstention_rate
            and separation > 0.0
        ),
        "why_this_matters": (
            "An abstention rate on this fixture means nothing on its own: a model "
            "that abstained on everything would score the same. It is evidence of "
            "discrimination only in contrast with the test-split rate beside it."
        ),
    }


def _run_identity_payload(
    *,
    identity: SharedDataIdentity,
    baseline_run_id: str,
    transformer_run_id: str,
    threshold: float,
    unsupported_fixture_sha256: str,
) -> dict[str, object]:
    """Render every input that changes a reported number, so the run ID tracks it.

    Timings are deliberately absent. Wall-clock latency differs between two runs
    of the same configuration, so including it would give the same evaluation two
    different identities. The latency *protocol* is recorded instead when that
    section exists; this is why `comparison.json` is rewritten on each run rather
    than sealed like an artifact bundle.
    """

    return {
        "baseline_run_id": baseline_run_id,
        "transformer_run_id": transformer_run_id,
        "split_fingerprints": dict(identity.split_fingerprints),
        "label_map_hash": identity.label_map_hash,
        "test_example_id_sha256": identity.test_example_id_sha256,
        "threshold": threshold,
        "metric_version": METRIC_VERSION,
        "comparison_metric": COMPARISON_METRIC,
        "comparison_tolerance": COMPARISON_TOLERANCE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "calibration_bin_count": CALIBRATION_BIN_COUNT,
        "calibration_binning": CALIBRATION_BINNING,
        # The latency *protocol* is part of the identity; the measured durations are
        # not. Including a duration would give two runs of one configuration two
        # different run IDs, which is what D14 exists to prevent.
        "latency_warm_up_requests": WARM_UP_REQUESTS,
        "latency_measured_requests": MEASURED_REQUESTS,
        "latency_sample_seed": SAMPLE_SEED,
        # Editing the curated fixture changes a reported number, so its content is
        # part of the identity. Hashing the rows rather than counting them means a
        # reworded request produces a new run ID instead of silently reusing one.
        "unsupported_fixture_sha256": unsupported_fixture_sha256,
        "unsupported_fixture_schema_version": FIXTURE_SCHEMA_VERSION,
    }


def _risk_coverage_payload(curve: tuple[CoveragePoint, ...]) -> list[dict[str, object]]:
    """Render the full risk/coverage curve over the test split.

    Computed with the same `coverage_curve` used during validation-only threshold
    selection, so the curve a reader plots here has identical semantics to the one
    the threshold was chosen from. This is a description of the trade-off, not a
    selection: no point on it is chosen, and `select_threshold` is never called.
    """

    return [
        {
            "threshold": point.threshold,
            "coverage": point.coverage,
            "accepted_count": point.accepted_count,
            "accepted_accuracy": point.accepted_accuracy,
            "selective_risk": point.selective_risk,
        }
        for point in curve
    ]


def _append_calibration_limitations(
    report: dict[str, object],
    *,
    baseline: CalibrationMetrics,
    transformer: CalibrationMetrics,
) -> None:
    """Record what the measured calibration means, derived from the numbers.

    Stated in the JSON as well as the Markdown, because a consumer that reads only
    `comparison.json` would otherwise see a low threshold and a confidence field
    with nothing to warn it that neither is a probability of correctness.

    Every sentence here is computed from this run's values. Hard-coding the
    direction would let a later run that happens to be overconfident publish a
    limitation asserting the opposite.
    """

    limitations = report["limitations"]
    if not isinstance(limitations, list):
        raise EvaluationError("The limitations block must be a list")

    for name, calibration in (("baseline", baseline), ("transformer", transformer)):
        gap = calibration.mean_confidence - calibration.accuracy
        if gap < 0.0:
            direction = (
                f"underconfident: mean confidence {calibration.mean_confidence:.4f} "
                f"below accuracy {calibration.accuracy:.4f}"
            )
        elif gap > 0.0:
            direction = (
                f"overconfident: mean confidence {calibration.mean_confidence:.4f} "
                f"above accuracy {calibration.accuracy:.4f}"
            )
        else:
            direction = (
                f"aggregate-equal at {calibration.accuracy:.4f}, which is not per-bin "
                "calibration"
            )
        limitations.append(
            f"The {name} model is {direction} "
            f"(ECE {calibration.expected_calibration_error:.4f})."
        )

    occupied = [entry for entry in transformer.bins if entry.count > 0]
    if occupied and occupied[-1].upper < 1.0:
        limitations.append(
            f"No test example received a transformer confidence above "
            f"{occupied[-1].upper:.4f}. The persisted threshold must be read relative "
            "to that range rather than as an absolute probability."
        )


def _model_block(
    *,
    bundle: ArtifactBundle,
    metrics: ClassificationMetrics,
    selective: SelectiveOutcome,
    calibration: CalibrationMetrics,
    curve: tuple[CoveragePoint, ...],
    latency: LatencyMeasurement,
) -> dict[str, object]:
    return {
        "artifact_name": bundle.artifact_name,
        "run_id": bundle.run_id,
        "artifact_directory": str(bundle.directory),
        "evaluated_from": "reloaded_artifact",
        "metrics": metrics_payload(metrics),
        "selective_prediction": selective.payload(),
        "calibration": calibration_payload(calibration),
        "risk_coverage_curve": _risk_coverage_payload(curve),
        "latency": latency.payload(),
    }


def main() -> None:
    """Evaluate both artifacts on the untouched test split and write the comparison."""

    config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
    prepared: PreparedDataset = prepare_dataset(load_pinned_dataset(config), config)

    baseline = _require_bundle(config, BASELINE_ARTIFACT_NAME)
    transformer = _require_bundle(config, TRANSFORMER_ARTIFACT_NAME)

    recorded_hash = read_recorded_test_example_id_hash(
        config.report_root / "baseline" / baseline.run_id / BASELINE_REPORT_FILENAME
    )
    identity = resolve_shared_identity(
        baseline=baseline,
        transformer=transformer,
        prepared=prepared,
        recorded_test_example_id_sha256=recorded_hash,
    )

    # The threshold is read from the sealed bundle and used verbatim. `select_threshold`
    # is not imported by this script, so re-deriving it from test data is not something
    # this code path can express.
    threshold = transformer.selected_threshold()

    test_texts, test_labels = _texts_and_labels(prepared.test)
    label_names = identity.label_names
    label_count = len(label_names)

    baseline_probability_matrix = _baseline_predictions(baseline, test_texts, label_count)
    transformer_probability_matrix = _transformer_predictions(
        transformer, config, test_texts, label_names
    )

    results: dict[
        str,
        tuple[
            ClassificationMetrics,
            SelectiveOutcome,
            CalibrationMetrics,
            tuple[CoveragePoint, ...],
        ],
    ] = {}
    for name, probabilities in (
        ("baseline", baseline_probability_matrix),
        ("transformer", transformer_probability_matrix),
    ):
        predicted = labels_from_probabilities(probabilities)
        confidences = confidences_from_probabilities(probabilities)
        correct = [
            predicted_label == true_label
            for predicted_label, true_label in zip(predicted, test_labels, strict=True)
        ]
        # Every aggregate comes from the shared metric function. A second F1
        # implementation here would bypass the imbalanced regression fixture, which
        # is the only guard that can catch a macro/weighted swap on this balanced
        # split.
        metrics = compute_classification_metrics(test_labels, predicted, label_names)
        selective = apply_threshold(
            confidences=confidences,
            correct=correct,
            threshold=threshold,
        )
        # Calibration and the risk/coverage curve reuse the confidences already
        # derived above, so the test split is still read exactly once per run.
        calibration = compute_calibration_metrics(confidences, correct)
        curve = coverage_curve(confidences, correct)
        results[name] = (metrics, selective, calibration, curve)

    (
        baseline_metrics,
        baseline_selective,
        baseline_calibration,
        baseline_curve,
    ) = results["baseline"]
    (
        transformer_metrics,
        transformer_selective,
        transformer_calibration,
        transformer_curve,
    ) = results["transformer"]

    latency_samples = select_latency_samples(
        test_texts,
        _token_lengths(transformer, test_texts, config),
    )
    baseline_latency = measure_latency(
        _baseline_single_request(baseline, label_count),
        latency_samples,
        model_name="baseline",
        max_sequence_length=config.training.max_sequence_length,
    )
    transformer_latency = measure_latency(
        _transformer_single_request(transformer, config, label_names),
        latency_samples,
        model_name="transformer",
        max_sequence_length=config.training.max_sequence_length,
    )

    unsupported = _unsupported_outcome(
        transformer, config, label_names, prepared, threshold
    )
    contrast = _in_distribution_contrast(
        unsupported,
        transformer_selective=transformer_selective,
        transformer_calibration=transformer_calibration,
    )
    unsupported_block = {**unsupported.payload(), "in_distribution_contrast": contrast}

    verdict = compare_metric(
        baseline_value=baseline_metrics.macro_f1,
        transformer_value=transformer_metrics.macro_f1,
    )

    run_id = compute_run_id(
        EVALUATION_NAME,
        config.dataset_revision,
        _run_identity_payload(
            identity=identity,
            baseline_run_id=baseline.run_id,
            transformer_run_id=transformer.run_id,
            threshold=threshold,
            unsupported_fixture_sha256=_fixture_content_hash(UNSUPPORTED_FIXTURE_PATH),
        ),
    )

    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "evaluation_name": EVALUATION_NAME,
        "run_id": run_id,
        "data_identity": identity.payload(),
        "threshold": {
            "value": threshold,
            "source": "transformer_artifact",
            "selected_from": "validation",
            "reselected_during_evaluation": False,
        },
        "models": {
            "baseline": _model_block(
                bundle=baseline,
                metrics=baseline_metrics,
                selective=baseline_selective,
                calibration=baseline_calibration,
                curve=baseline_curve,
                latency=baseline_latency,
            ),
            "transformer": _model_block(
                bundle=transformer,
                metrics=transformer_metrics,
                selective=transformer_selective,
                calibration=transformer_calibration,
                curve=transformer_curve,
                latency=transformer_latency,
            ),
        },
        "comparison": verdict.payload(),
        # Kept out of the `models` block and given its own file as well: FR-009
        # requires this reported *separately* from BANKING77 benchmark metrics, and
        # nesting it beside accuracy is how the two would come to be quoted together.
        "unsupported_fixture": unsupported_block,
        "latency_protocol": {
            "samples": latency_samples.payload(),
            "sampled_from": "test",
            "environment": latency_environment(
                device=str(resolve_device()),
                thread_count=torch.get_num_threads(),
                cuda_available=torch.cuda.is_available(),
            ),
            "caveat": LATENCY_CAVEAT,
            "is_service_level_claim": False,
            "reproducible": False,
            "reproducibility_note": (
                "Latency is the one section of this report that does not reproduce "
                "between runs of the same configuration. The run ID covers the "
                "sampling protocol, never the measured durations."
            ),
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "dependency_versions": dependency_versions(TRACKED_DEPENDENCIES),
            "device": str(resolve_device()),
        },
        "limitations": [
            UNSUPPORTED_FIXTURE_CAVEAT,
            LATENCY_CAVEAT,
            "No GPU throughput claim is evidenced. Evaluation ran on the device "
            "recorded in the environment block.",
            "Expected calibration error depends on the recorded binning. It is "
            "comparable between these two models because both were scored against "
            "the same fixed equal-width bins, and is not comparable with an ECE "
            "computed under a different binning.",
            "No recalibration was applied. A confidence score from either model is a "
            "ranking signal for abstention, not a probability of correctness; read "
            "the calibration block before treating one as the latter.",
        ],
    }
    # Derived from the measured values rather than written as prose, so a future run
    # whose calibration differs cannot inherit a stale claim about it.
    _append_calibration_limitations(
        report,
        baseline=baseline_calibration,
        transformer=transformer_calibration,
    )

    report_directory = config.report_root / "evaluate" / run_id
    _write_json_atomically(report_directory / COMPARISON_JSON_FILENAME, report)
    _write_text_atomically(
        report_directory / COMPARISON_MARKDOWN_FILENAME,
        render_comparison_markdown(
            run_id=run_id,
            identity=identity,
            baseline_metrics=metrics_payload(baseline_metrics),
            transformer_metrics=metrics_payload(transformer_metrics),
            baseline_selective=baseline_selective,
            transformer_selective=transformer_selective,
            verdict=verdict,
            baseline_run_id=baseline.run_id,
            transformer_run_id=transformer.run_id,
            baseline_calibration=calibration_payload(baseline_calibration),
            transformer_calibration=calibration_payload(transformer_calibration),
            baseline_latency=baseline_latency.payload(),
            transformer_latency=transformer_latency.payload(),
            latency_caveat=LATENCY_CAVEAT,
        ),
    )
    _write_json_atomically(report_directory / UNSUPPORTED_JSON_FILENAME, unsupported_block)
    _write_text_atomically(
        report_directory / UNSUPPORTED_MARKDOWN_FILENAME,
        render_unsupported_markdown(unsupported, contrast=contrast),
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "report_directory": str(report_directory),
                "baseline_macro_f1": baseline_metrics.macro_f1,
                "transformer_macro_f1": transformer_metrics.macro_f1,
                "macro_f1_delta": verdict.delta,
                "verdict": verdict.verdict,
                "transformer_outperforms_baseline": (
                    verdict.transformer_outperforms_baseline
                ),
                "threshold": threshold,
                "example_count": baseline_metrics.example_count,
                "unsupported_fixture_count": unsupported.example_count,
                "unsupported_abstention_rate": unsupported.abstention_rate,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ArtifactError,
        BaselineError,
        DataContractError,
        EvaluationError,
        LatencyError,
        TrainingError,
        UnsupportedFixtureError,
        ValueError,
    ) as error:
        raise SystemExit(f"Evaluation failed: {error}") from error
