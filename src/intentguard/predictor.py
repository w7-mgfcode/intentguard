"""The real serving predictor: one sealed artifact, loaded once (FR-006, FR-007).

S06.1 left a `Predictor` protocol in `api.py` and answered every prediction with
``MODEL_NOT_READY``. This module fills that seam with the artifact itself. It loads,
verifies, and predicts; it does not fit, tune, or select anything, and it imports no
training loop — only the shared preprocessing and decision functions that training
and evaluation already use.

Four properties are enforced here rather than assumed:

**Preprocessing comes from the artifact, not from `configs/default.toml`.** The
bundle's own `config.json` records the `training` block the weights were fitted
under. Reading `max_sequence_length` from the live TOML file instead would let a
later edit silently change how a sealed bundle tokenises, so the persisted block is
what serving obeys — routed through the same validators, so a hand-edited
`threshold_source = "test"` is refused at load.

**The threshold is read, never chosen.** `load_artifact` already refuses a bundle
whose threshold was not selected from validation data; this module asserts the same
property again at the serving boundary, because that is where a leaked threshold
would become a published decision.

**Truncation needs a second tokenizer pass.** `input_truncated` cannot be derived
from a truncating encode: the result is exactly `max_sequence_length` tokens whether
one token was dropped or four hundred. The text is therefore tokenised once without
truncation purely to compare lengths, and that pass is not what the model sees.

**Startup fails loudly.** The predictor is constructed eagerly, so an invalid
artifact raises before the application can accept traffic — which is what
`INTERFACE_CONTRACT.md:88-90` asks for. A lifespan hook that loaded lazily would let
the process bind a port and then serve 503s for a defect that was knowable at start.

`api.py` is deliberately left untouched: it must not import a concrete predictor, so
the wiring lives here in :func:`create_serving_app` instead.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import torch
from fastapi import FastAPI
from transformers import PreTrainedModel, PreTrainedTokenizerBase

from intentguard.api import create_app, set_predictor
from intentguard.artifacts import ArtifactBundle, load_artifact
from intentguard.config import FoundationConfig, TrainingConfig, training_config_from_payload
from intentguard.data import CANONICAL_LABEL_NAMES, LABEL_COUNT
from intentguard.threshold import THRESHOLD_SOURCE, decide
from intentguard.training import (
    confidences_from_probabilities,
    labels_from_probabilities,
    load_model_from_directory,
    load_tokenizer_from_directory,
    move_to_device,
    predict_probabilities,
    resolve_device,
)

#: Serving reaches its artifacts through the environment because the sealed bundle
#: does not live inside the worktree that serves it. Copying a bundle to make a
#: relative path work would duplicate an immutable artifact and put its provenance
#: at risk; hardcoding a sibling path breaks the moment a worktree moves.
ARTIFACT_ROOT_VARIABLE: Final = "INTENTGUARD_ARTIFACT_ROOT"

TRANSFORMER_ARTIFACT_NAME: Final = "intentguard-distilbert"
TRANSFORMER_MODEL_DIRECTORY: Final = "model"
TRANSFORMER_TOKENIZER_DIRECTORY: Final = "tokenizer"
TRAINING_CONFIG_KEY: Final = "training"


class PredictorError(ValueError):
    """Raised when a bundle cannot be served.

    A `ValueError` subclass, like `ArtifactError` and `TrainingError`, so an entry
    point can catch one type for every reason startup might legitimately refuse to
    serve an artifact.
    """


def resolve_artifact_root(
    config: FoundationConfig, environ: Mapping[str, str] | None = None
) -> Path:
    """Return the artifact root, letting the environment override the configured path.

    `environ` is a parameter rather than a direct `os.environ` read so the override
    is testable without mutating process state. An empty or whitespace-only value is
    treated as unset: a shell that exports the variable without a value must not
    resolve the root to the current directory.
    """

    source = os.environ if environ is None else environ
    override = source.get(ARTIFACT_ROOT_VARIABLE, "").strip()
    if override:
        return Path(override).expanduser()
    return config.artifact_root


def locate_transformer_bundle(artifact_root: Path) -> Path:
    """Return the single transformer bundle directory, refusing an ambiguous choice.

    A stale sibling bundle from a superseded configuration must not be picked up
    silently. Serving the wrong one would publish predictions attributed to an
    artifact that did not produce them, so more than one candidate stops startup and
    names them instead of guessing.
    """

    parent = artifact_root / TRANSFORMER_ARTIFACT_NAME
    if not parent.is_dir():
        raise PredictorError(
            f"No {TRANSFORMER_ARTIFACT_NAME} artifact directory exists at {parent}. "
            f"Set {ARTIFACT_ROOT_VARIABLE} to a root holding a trained bundle."
        )
    candidates = sorted(entry for entry in parent.iterdir() if entry.is_dir())
    if not candidates:
        raise PredictorError(f"No {TRANSFORMER_ARTIFACT_NAME} bundle exists under {parent}")
    if len(candidates) > 1:
        names = [entry.name for entry in candidates]
        raise PredictorError(
            f"{parent} holds {len(candidates)} bundles and the one to serve is "
            f"ambiguous: {names}. Remove the superseded bundle or serve an explicit run."
        )
    return candidates[0]


def _persisted_training_config(bundle: ArtifactBundle) -> TrainingConfig:
    """Rebuild the training configuration the bundle was fitted under."""

    block = bundle.config.get(TRAINING_CONFIG_KEY)
    if not isinstance(block, Mapping):
        raise PredictorError(
            f"Bundle {bundle.run_id} records no {TRAINING_CONFIG_KEY!r} configuration, "
            "so the preprocessing it was trained with is unknown"
        )
    try:
        return training_config_from_payload(cast(Mapping[str, object], block))
    except ValueError as error:
        raise PredictorError(
            f"Bundle {bundle.run_id} has an unusable training configuration: {error}"
        ) from error


def _validated_label_names(bundle: ArtifactBundle) -> tuple[str, ...]:
    """Check the bundle's label map against the canonical 77-label contract.

    Both halves matter. The count is what `AC-009` names, but a bundle could carry 77
    names in a different order and produce confidently mislabelled predictions, so the
    ordered map is compared as well — it is the map that fixes the probability column
    order.
    """

    names = bundle.label_names
    if len(names) != LABEL_COUNT:
        raise PredictorError(
            f"Bundle {bundle.run_id} maps {len(names)} labels, not {LABEL_COUNT}"
        )
    if names != CANONICAL_LABEL_NAMES:
        raise PredictorError(
            f"Bundle {bundle.run_id} does not carry the canonical BANKING77 label map"
        )
    return names


def _validated_threshold(bundle: ArtifactBundle) -> float:
    """Return the persisted threshold, refusing one that validation did not select.

    `load_artifact` enforces this too. Repeating it here is deliberate: this is the
    boundary where a threshold becomes a published accept/abstain decision, and
    `AC-005` forbids a test-derived value ever reaching it.
    """

    record = bundle.threshold
    if record is None:
        raise PredictorError(
            f"Bundle {bundle.run_id} carries no selected threshold, so it cannot decide"
        )
    source = record.get("source")
    if source != THRESHOLD_SOURCE:
        raise PredictorError(
            f"Bundle {bundle.run_id} threshold source is {source!r}, not {THRESHOLD_SOURCE!r}"
        )
    return bundle.selected_threshold()


@dataclass(frozen=True, slots=True)
class ArtifactPrediction:
    """One prediction from the loaded artifact, satisfying the API's `Prediction`.

    Frozen because the API reads these fields to build a response that has already
    been validated against the published contract; a mutable prediction would let a
    later caller change what was decided after the decision was made.
    """

    intent: str | None
    confidence: float
    threshold: float
    decision: str
    input_truncated: bool


class ArtifactPredictor:
    """Serve one verified transformer bundle.

    Holds the loaded model, tokenizer, ordered label map, persisted threshold, and
    the training configuration the bundle was fitted under. Nothing is re-derived per
    request except the prediction itself.
    """

    def __init__(
        self,
        *,
        bundle: ArtifactBundle,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizerBase,
        label_names: Sequence[str],
        threshold: float,
        training: TrainingConfig,
        device: torch.device,
    ) -> None:
        self._bundle = bundle
        self._model = model
        self._tokenizer = tokenizer
        self._label_names = tuple(label_names)
        self._threshold = threshold
        self._training = training
        self._device = device

    @property
    def model_version(self) -> str:
        """Identify the loaded artifact by its content-derived run ID.

        The run ID is derived from the dataset revision and configuration, so it
        names the artifact that produced a response without depending on a
        wall-clock value that two identical runs would not share.
        """

        return self._bundle.run_id

    @property
    def label_count(self) -> int:
        return len(self._label_names)

    @property
    def device(self) -> str:
        return str(self._device)

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def bundle(self) -> ArtifactBundle:
        return self._bundle

    def is_ready(self) -> bool:
        """Report readiness as a checked property rather than a constant.

        Loading is eager and raises on any violation, so a constructed predictor
        starts ready — but `/health` must not answer ready for a state that has since
        drifted. The eval-mode check is the one that could realistically change after
        construction: a model left in training mode has dropout active, which makes
        repeated predictions for the same text disagree, and reporting ready then
        would be false.
        """

        return (
            len(self._label_names) == LABEL_COUNT
            and self._bundle.threshold is not None
            and 0.0 <= self._threshold <= 1.0
            and not self._model.training
        )

    def input_truncated(self, text: str) -> bool:
        """Report whether tokenisation dropped tokens beyond the configured maximum.

        Determined by a second, non-truncating pass. The encode the model actually
        sees returns exactly `max_sequence_length` tokens whether it discarded one
        token or four hundred, so its output cannot answer this question. `verbose`
        is disabled because this pass intentionally exceeds the tokenizer's own
        maximum and its warning would describe a sequence no model ever receives.
        """

        encoded = self._tokenizer([text], truncation=False, verbose=False)
        token_ids = cast(Sequence[Sequence[int]], encoded["input_ids"])
        return len(token_ids[0]) > self._training.max_sequence_length

    def predict(self, text: str) -> ArtifactPrediction:
        """Predict one request through the shared preprocessing and decision rule.

        `predict_probabilities` supplies `model.eval()`, `torch.no_grad()`, the shared
        `encode`, the softmax, and a row-sum check, so the confidence here is only a
        maximum of a verified distribution. `decide` is the same function training and
        evaluation call, so an exactly-at-threshold confidence cannot be resolved one
        way at serving and another way in a report.
        """

        probabilities = predict_probabilities(
            self._model,
            self._tokenizer,
            [text],
            label_count=len(self._label_names),
            training=self._training,
            device=self._device,
        )
        index = labels_from_probabilities(probabilities)[0]
        confidence = confidences_from_probabilities(probabilities)[0]
        decision = decide(confidence, self._threshold)
        return ArtifactPrediction(
            # An abstention names no intent. The argmax label is deliberately dropped
            # rather than reported alongside `abstain`, because the published contract
            # states `intent` is null when abstaining.
            intent=self._label_names[index] if decision == "accept" else None,
            confidence=confidence,
            threshold=self._threshold,
            decision=decision,
            input_truncated=self.input_truncated(text),
        )


def load_artifact_predictor(
    config: FoundationConfig,
    *,
    artifact_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ArtifactPredictor:
    """Verify and load the single sealed transformer bundle for serving.

    Every checksum in the bundle is re-verified by `load_artifact`, the label map and
    threshold are checked against their contracts, and the model is placed in eval
    mode on the resolved device before this returns. `local_files_only` loading means
    a bundle missing a tokenizer file fails here rather than being quietly completed
    from the Hugging Face Hub.
    """

    root = resolve_artifact_root(config, environ) if artifact_root is None else artifact_root
    bundle = load_artifact(locate_transformer_bundle(root))

    label_names = _validated_label_names(bundle)
    threshold = _validated_threshold(bundle)
    training = _persisted_training_config(bundle)

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
    model.eval()  # type: ignore[no-untyped-call]

    return ArtifactPredictor(
        bundle=bundle,
        model=model,
        tokenizer=tokenizer,
        label_names=label_names,
        threshold=threshold,
        training=training,
        device=device,
    )


def create_serving_app(
    config: FoundationConfig,
    *,
    artifact_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> FastAPI:
    """Build the application with a real loaded artifact installed.

    Separate from `create_app` so `api.py` keeps importing no concrete predictor, and
    so the contract suite can still build an application with a deterministic double.
    The artifact is loaded before the application is returned, so a caller that gets
    an app has an app that can serve.
    """

    predictor = load_artifact_predictor(config, artifact_root=artifact_root, environ=environ)
    app = create_app()
    set_predictor(app, predictor)
    return app
