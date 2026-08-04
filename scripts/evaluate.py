"""Compare both sealed artifacts on the untouched test split (AC-004, FR-005).

The order of operations here is the correctness control, not a convention:

1. both bundles are loaded from disk and every checksum re-verified;
2. the equivalence gate proves they describe the same data as each other *and* as
   the locally prepared splits, or the run fails;
3. the threshold is read from the transformer bundle, never selected here;
4. each model predicts over the test split through its reloaded artifact only;
5. metrics come from the shared metric function, and the report is written.

Nothing in this script fits, trains, or tunes. It calls neither `fit_pipeline` nor
`select_threshold`, so no test label can reach a modelling decision: the only
thing a test label is allowed to influence is a reported number.

Per AC-004 the outcome is reported whichever way it falls. A transformer that
loses to the lexical baseline is a measured result, and this script writes it down
plainly rather than softening it.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final

import joblib  # type: ignore[import-untyped]
import numpy as np
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
from intentguard.metrics import (
    METRIC_VERSION,
    ClassificationMetrics,
    compute_classification_metrics,
    metrics_payload,
)
from intentguard.schemas import CanonicalExample, PreparedDataset
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


def _run_identity_payload(
    *,
    identity: SharedDataIdentity,
    baseline_run_id: str,
    transformer_run_id: str,
    threshold: float,
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
    }


def _model_block(
    *,
    bundle: ArtifactBundle,
    metrics: ClassificationMetrics,
    selective: SelectiveOutcome,
) -> dict[str, object]:
    return {
        "artifact_name": bundle.artifact_name,
        "run_id": bundle.run_id,
        "artifact_directory": str(bundle.directory),
        "evaluated_from": "reloaded_artifact",
        "metrics": metrics_payload(metrics),
        "selective_prediction": selective.payload(),
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

    results: dict[str, tuple[ClassificationMetrics, SelectiveOutcome]] = {}
    for name, probabilities in (
        ("baseline", baseline_probability_matrix),
        ("transformer", transformer_probability_matrix),
    ):
        predicted = labels_from_probabilities(probabilities)
        # Every aggregate comes from the shared metric function. A second F1
        # implementation here would bypass the imbalanced regression fixture, which
        # is the only guard that can catch a macro/weighted swap on this balanced
        # split.
        metrics = compute_classification_metrics(test_labels, predicted, label_names)
        selective = apply_threshold(
            confidences=confidences_from_probabilities(probabilities),
            correct=[
                predicted_label == true_label
                for predicted_label, true_label in zip(predicted, test_labels, strict=True)
            ],
            threshold=threshold,
        )
        results[name] = (metrics, selective)

    baseline_metrics, baseline_selective = results["baseline"]
    transformer_metrics, transformer_selective = results["transformer"]

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
                bundle=baseline, metrics=baseline_metrics, selective=baseline_selective
            ),
            "transformer": _model_block(
                bundle=transformer,
                metrics=transformer_metrics,
                selective=transformer_selective,
            ),
        },
        "comparison": verdict.payload(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "dependency_versions": dependency_versions(TRACKED_DEPENDENCIES),
            "device": str(resolve_device()),
        },
        "limitations": [
            "Calibration error, risk/coverage curves, latency, and the curated "
            "unsupported-request fixture are not part of this report yet; they are "
            "tracked by S05.2 and S05.3.",
            "No GPU throughput claim is evidenced. Evaluation ran on the device "
            "recorded in the environment block.",
        ],
    }

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
        ),
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
        TrainingError,
        ValueError,
    ) as error:
        raise SystemExit(f"Evaluation failed: {error}") from error
