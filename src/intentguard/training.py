"""DistilBERT fine-tuning primitives: loading, batching, optimisation, inference.

This module owns the transformer mechanics and nothing else. It performs no file
I/O, selects no threshold, and computes no metrics, so `scripts/train_transformer.py`
holds the orchestration and this module stays directly testable.

`transformers.Trainer` is deliberately not used. `TrainingArguments` requires
`accelerate>=1.1.0`, which is not in `uv.lock`, and adding a dependency is out of
scope for E04 (decision D9). A plain PyTorch loop over these primitives keeps the
locked dependency set byte-unchanged and makes every optimisation step explicit.

Everything here is CPU-only by decision D10. No GPU claim is made or implied.
"""

from __future__ import annotations

import os
import resource
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import numpy as np
import torch
import transformers
from numpy.typing import NDArray
from torch import nn
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    get_linear_schedule_with_warmup,
    set_seed,
)

from intentguard.config import FoundationConfig, TrainingConfig
from intentguard.metrics import MetricError, label_id_array

PROBABILITY_SUM_TOLERANCE: Final = 1e-6
KIBIBYTE: Final = 1024

# Platforms whose `getrusage` reports `ru_maxrss` in bytes rather than kibibytes.
_BYTE_RU_MAXRSS_PLATFORMS: Final = ("darwin", "freebsd", "openbsd", "netbsd", "dragonfly")


class TrainingError(ValueError):
    """Raised when transformer training violates its own contract."""


@dataclass(frozen=True, slots=True)
class RuntimeFacts:
    """Measured facts about the machine that produced a training run.

    Recorded rather than asserted. `NFR-001`'s GPU clause stays unevidenced on a
    CPU run, and these fields are what let a reader see that for themselves
    instead of inferring hardware from a wall-clock number.
    """

    device: str
    torch_version: str
    transformers_version: str
    thread_count: int
    cuda_available: bool
    peak_memory_bytes: int


def resolve_device() -> torch.device:
    """Return the CPU device.

    E04 is a CPU run by decision D10. Silently selecting CUDA when it happened to
    be present would make a recorded run unreproducible on the machine that
    validated it, so the device is fixed rather than detected.
    """

    return torch.device("cpu")


def ru_maxrss_scale(platform_name: str = sys.platform) -> int:
    """Return the multiplier that converts `ru_maxrss` to bytes on one platform.

    The unit is not portable: Linux reports kibibytes while macOS and the BSDs
    report bytes. Taking the argument rather than reading `sys.platform` directly
    keeps both branches testable on whichever machine runs the suite.
    """

    return 1 if platform_name.startswith(_BYTE_RU_MAXRSS_PLATFORMS) else KIBIBYTE


def peak_memory_bytes() -> int:
    """Return peak resident set size for this process in bytes.

    Scaling `ru_maxrss` unconditionally by a kibibyte would over-report by 1024x
    on macOS and the BSDs, where the field is already in bytes, so the unit is
    resolved from the platform rather than assumed.
    """

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * ru_maxrss_scale()


def runtime_facts(device: torch.device) -> RuntimeFacts:
    """Capture the runtime facts for a training run's provenance."""

    return RuntimeFacts(
        device=str(device),
        torch_version=str(torch.__version__),
        transformers_version=str(transformers.__version__),
        thread_count=int(torch.get_num_threads()),
        cuda_available=bool(torch.cuda.is_available()),
        peak_memory_bytes=peak_memory_bytes(),
    )


def runtime_payload(facts: RuntimeFacts) -> dict[str, object]:
    """Render runtime facts as a JSON-serialisable payload with stable keys."""

    return {
        "device": facts.device,
        "torch_version": facts.torch_version,
        "transformers_version": facts.transformers_version,
        "thread_count": facts.thread_count,
        "cuda_available": facts.cuda_available,
        "peak_memory_bytes": facts.peak_memory_bytes,
    }


def seed_training(seed: int) -> None:
    """Seed Python, NumPy, and torch through one call, then pin CPU determinism.

    `PYTHONHASHSEED` is set for completeness even though nothing here depends on
    dict ordering, so a future addition that does cannot introduce nondeterminism
    without an explicit change.
    """

    os.environ["PYTHONHASHSEED"] = str(seed)
    set_seed(seed)


def model_is_cached(config: FoundationConfig) -> bool:
    """Report whether the pinned base model is already in the local Hugging Face cache.

    Used to gate the smoke test. CI must never download 265 MB of weights as a
    side effect of running the suite, so an uncached machine skips rather than
    fetches.
    """

    try:
        AutoTokenizer.from_pretrained(
            config.base_model_id,
            revision=config.base_model_revision,
            local_files_only=True,
        )
        AutoModelForSequenceClassification.from_pretrained(
            config.base_model_id,
            revision=config.base_model_revision,
            local_files_only=True,
        )
    except Exception:
        return False
    return True


def load_tokenizer(config: FoundationConfig) -> PreTrainedTokenizerBase:
    """Load the tokenizer at the pinned immutable revision."""

    try:
        return cast(
            PreTrainedTokenizerBase,
            AutoTokenizer.from_pretrained(
                config.base_model_id,
                revision=config.base_model_revision,
            ),
        )
    except Exception as error:
        raise TrainingError(
            f"Unable to load tokenizer {config.base_model_id}@{config.base_model_revision}"
        ) from error


def load_model(config: FoundationConfig, label_names: Sequence[str]) -> PreTrainedModel:
    """Load the pinned base model with a freshly initialised head over the label map.

    The head size, `id2label`, and `label2id` all come from the canonical label
    map, and the resulting output width is asserted rather than trusted. A head
    that silently kept the checkpoint's own `num_labels` would produce logits that
    do not correspond to IntentGuard's labels at all.
    """

    if not label_names:
        raise TrainingError("Model loading requires a non-empty label map")
    if len(set(label_names)) != len(label_names):
        raise TrainingError("Model loading requires unique label names")

    id2label = {index: name for index, name in enumerate(label_names)}
    label2id = {name: index for index, name in enumerate(label_names)}
    try:
        model = cast(
            PreTrainedModel,
            AutoModelForSequenceClassification.from_pretrained(
                config.base_model_id,
                revision=config.base_model_revision,
                num_labels=len(label_names),
                id2label=id2label,
                label2id=label2id,
            ),
        )
    except Exception as error:
        raise TrainingError(
            f"Unable to load model {config.base_model_id}@{config.base_model_revision}"
        ) from error

    if int(model.config.num_labels) != len(label_names):
        raise TrainingError(
            f"Loaded head exposes {model.config.num_labels} outputs, not {len(label_names)}"
        )
    if model.config.id2label != id2label:
        raise TrainingError("Loaded model label mapping does not match the canonical label map")
    return model


def move_to_device(model: PreTrainedModel, device: torch.device) -> PreTrainedModel:
    """Place a model on the training device and return it.

    Wrapped here because `PreTrainedModel.to` is re-exported through a decorator
    whose published signature does not describe the device overload. Keeping the
    one narrow suppression in this module means callers stay free of type
    escape hatches.
    """

    model.to(device)  # type: ignore[arg-type]
    return model


def load_tokenizer_from_directory(directory: Path) -> PreTrainedTokenizerBase:
    """Load a tokenizer from a verified bundle directory rather than from the Hub.

    `local_files_only=True` is the point: a reload-parity check that silently fell
    back to a network fetch would compare the bundle against the Hub instead of
    against itself.
    """

    try:
        return cast(
            PreTrainedTokenizerBase,
            AutoTokenizer.from_pretrained(str(directory), local_files_only=True),
        )
    except Exception as error:
        raise TrainingError(f"Unable to load tokenizer from {directory}") from error


def load_model_from_directory(
    directory: Path, label_names: Sequence[str]
) -> PreTrainedModel:
    """Load a fine-tuned model from a verified bundle directory, checking its label map.

    The saved `id2label` is compared against the canonical label map, so a bundle
    whose column order no longer matches the map fails here rather than producing
    confidently mislabelled predictions.
    """

    if not label_names:
        raise TrainingError("Model loading requires a non-empty label map")

    try:
        model = cast(
            PreTrainedModel,
            AutoModelForSequenceClassification.from_pretrained(
                str(directory), local_files_only=True
            ),
        )
    except Exception as error:
        raise TrainingError(f"Unable to load model from {directory}") from error

    if output_width(model) != len(label_names):
        raise TrainingError(
            f"Saved head exposes {output_width(model)} outputs, not {len(label_names)}"
        )
    if model.config.id2label != {index: name for index, name in enumerate(label_names)}:
        raise TrainingError(f"Saved model label mapping in {directory} is not the canonical map")
    return model


def classification_head(model: PreTrainedModel) -> nn.Linear:
    """Return the final linear layer, the head whose weights fine-tuning must move.

    Located by walking the module tree rather than by attribute name, so this does
    not depend on the checkpoint calling it `classifier`.
    """

    linear_layers = [module for module in model.modules() if isinstance(module, nn.Linear)]
    if not linear_layers:
        raise TrainingError("Loaded model exposes no linear classification head")
    return linear_layers[-1]


def output_width(model: PreTrainedModel) -> int:
    """Return the classification head's output width from the module itself.

    Read from the final `Linear` layer rather than from `config.num_labels`, so a
    configuration value that disagrees with the actual parameter shape is
    detectable instead of self-confirming.
    """

    return int(classification_head(model).out_features)


def encode(
    tokenizer: PreTrainedTokenizerBase,
    texts: Sequence[str],
    *,
    max_sequence_length: int,
) -> dict[str, torch.Tensor]:
    """Tokenise a batch with the one preprocessing definition used everywhere.

    Training, evaluation, and serving all call this, so a truncation length or
    padding change cannot apply to one path and not another.
    """

    if not texts:
        raise TrainingError("Encoding requires at least one example")
    if max_sequence_length < 1:
        raise TrainingError("max_sequence_length must be positive")

    encoded = tokenizer(
        list(texts),
        padding="longest",
        truncation=True,
        max_length=max_sequence_length,
        return_tensors="pt",
    )
    return {key: value for key, value in encoded.items() if isinstance(value, torch.Tensor)}


def batch_slices(count: int, batch_size: int) -> tuple[tuple[int, int], ...]:
    """Split `count` items into contiguous half-open ranges of at most `batch_size`.

    The final range is short rather than dropped, so every example is seen exactly
    once per epoch and the validation pass covers all 1501 items.
    """

    if count < 1:
        raise TrainingError("Batching requires at least one example")
    if batch_size < 1:
        raise TrainingError("batch_size must be positive")
    return tuple(
        (start, min(start + batch_size, count)) for start in range(0, count, batch_size)
    )


def shuffled_epoch_order(count: int, seed: int, epoch: int) -> list[int]:
    """Return a deterministic per-epoch permutation of example positions.

    Derived from `seed` and `epoch` through an explicit generator rather than from
    global RNG state, so the shuffle for epoch two is identical whether or not
    anything else consumed randomness during epoch one.
    """

    if count < 1:
        raise TrainingError("Shuffling requires at least one example")
    generator = torch.Generator()
    generator.manual_seed(int(seed) * 1_000_003 + int(epoch))
    return [int(index) for index in torch.randperm(count, generator=generator)]


def build_optimizer(model: PreTrainedModel, training: TrainingConfig) -> torch.optim.Optimizer:
    """Build AdamW with decay disabled for biases and LayerNorm weights.

    Applying weight decay to those parameters is a known way to degrade
    transformer fine-tuning, so the split is explicit rather than left to a single
    global decay value.
    """

    decayed: list[nn.Parameter] = []
    undecayed: list[nn.Parameter] = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.endswith("bias") or "LayerNorm" in name or "layer_norm" in name:
            undecayed.append(parameter)
        else:
            decayed.append(parameter)
    if not decayed:
        raise TrainingError("Model exposes no trainable weight-decayed parameters")

    return torch.optim.AdamW(
        [
            {"params": decayed, "weight_decay": training.weight_decay},
            {"params": undecayed, "weight_decay": 0.0},
        ],
        lr=training.learning_rate,
    )


def build_schedule(
    optimizer: torch.optim.Optimizer, training: TrainingConfig, *, total_steps: int
) -> torch.optim.lr_scheduler.LRScheduler:
    """Build the linear warmup-then-decay schedule over the full step count."""

    if total_steps < 1:
        raise TrainingError("Scheduling requires at least one optimisation step")
    warmup_steps = int(total_steps * training.warmup_ratio)
    return cast(
        torch.optim.lr_scheduler.LRScheduler,
        get_linear_schedule_with_warmup(  # type: ignore[no-untyped-call]
            optimizer,
            num_warmup_steps=warmup_steps,
            num_training_steps=total_steps,
        ),
    )


def total_optimisation_steps(example_count: int, training: TrainingConfig) -> int:
    """Count the optimisation steps a full run will take, for the LR schedule."""

    return len(batch_slices(example_count, training.train_batch_size)) * training.epochs


def forward_loss(
    model: PreTrainedModel,
    batch: dict[str, torch.Tensor],
    labels: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Run one forward pass and return `(loss, logits)`, rejecting a non-finite loss.

    A NaN loss propagates into every weight on the next backward pass and yields a
    model that predicts one class for all inputs. Failing at the step that
    produced it makes that a visible error rather than a mysteriously flat metric
    an hour later.
    """

    outputs = model(**batch, labels=labels)
    loss = cast(torch.Tensor, outputs.loss)
    logits = cast(torch.Tensor, outputs.logits)
    if not bool(torch.isfinite(loss)):
        raise TrainingError(f"Training loss is not finite: {loss.item()}")
    return loss, logits


def train_batches(
    texts: Sequence[str],
    label_ids: Sequence[int],
    *,
    label_count: int,
    training: TrainingConfig,
    seed: int,
    epoch: int,
) -> Iterator[tuple[list[str], list[int]]]:
    """Yield one epoch of shuffled training batches, validated against the label map.

    Labels pass through `metrics.label_id_array`, the single definition of the
    label-ID contract, so a value that a report would reject cannot be trained on.
    """

    if len(texts) != len(label_ids):
        raise TrainingError("Training text and label counts differ")
    try:
        label_id_array(label_ids, "label_ids", label_count)
    except MetricError as error:
        raise TrainingError(f"Training labels are invalid: {error}") from error

    order = shuffled_epoch_order(len(texts), seed, epoch)
    for start, end in batch_slices(len(order), training.train_batch_size):
        positions = order[start:end]
        yield [texts[position] for position in positions], [
            int(label_ids[position]) for position in positions
        ]


def predict_probabilities(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    texts: Sequence[str],
    *,
    label_count: int,
    training: TrainingConfig,
    device: torch.device,
) -> NDArray[np.float64]:
    """Predict a validated probability matrix in the caller's example order.

    Batching must not reorder output: rows are written back at their input
    positions, so a probability row always belongs to the example at the same
    index. The row-sum check then catches a shape or softmax-axis mistake here
    rather than in a metric downstream.
    """

    if not texts:
        raise TrainingError("Prediction requires at least one example")

    was_training = model.training
    model.eval()  # type: ignore[no-untyped-call]
    probabilities = np.empty((len(texts), label_count), dtype=np.float64)
    try:
        with torch.no_grad():
            for start, end in batch_slices(len(texts), training.eval_batch_size):
                batch = encode(
                    tokenizer,
                    texts[start:end],
                    max_sequence_length=training.max_sequence_length,
                )
                logits = model(**{key: value.to(device) for key, value in batch.items()}).logits
                if tuple(logits.shape) != (end - start, label_count):
                    raise TrainingError(
                        f"Logit shape {tuple(logits.shape)} is not {(end - start, label_count)}"
                    )
                probabilities[start:end] = (
                    torch.softmax(logits.to(torch.float64), dim=-1).cpu().numpy()
                )
    finally:
        model.train(was_training)

    row_sums = probabilities.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=PROBABILITY_SUM_TOLERANCE, rtol=0.0):
        raise TrainingError("Probability rows do not sum to one within tolerance")
    return probabilities


def labels_from_probabilities(probabilities: NDArray[np.float64]) -> list[int]:
    """Take the argmax label per row, so labels and probabilities can never disagree."""

    return [int(index) for index in probabilities.argmax(axis=1)]


def confidences_from_probabilities(probabilities: NDArray[np.float64]) -> list[float]:
    """Take the maximum probability per row as that example's confidence.

    This is the quantity the abstention threshold is compared against, taken from
    the same matrix as the predicted label so the two can never diverge.
    """

    return [float(value) for value in probabilities.max(axis=1)]
