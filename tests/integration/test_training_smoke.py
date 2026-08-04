"""CPU-only smoke evidence that the pinned DistilBERT trains at all (S04.1).

Every test here is gated on the base model already being in the local Hugging
Face cache. CI must never download 265 MB of weights as a side effect of running
the suite, so an uncached machine skips with a message that says how to populate
the cache rather than fetching silently.

This file proves the mechanics — load, forward, backward, decode — not accuracy.
Fine-tuning quality is measured by `make train`, whose evidence lives in the
artifact bundle.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest
import torch

from intentguard.config import load_foundation_config
from intentguard.data import CANONICAL_LABEL_NAMES
from intentguard.training import (
    TrainingError,
    batch_slices,
    build_optimizer,
    build_schedule,
    classification_head,
    confidences_from_probabilities,
    encode,
    forward_loss,
    labels_from_probabilities,
    load_model,
    load_tokenizer,
    model_is_cached,
    output_width,
    predict_probabilities,
    resolve_device,
    runtime_facts,
    runtime_payload,
    seed_training,
    total_optimisation_steps,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
LABEL_COUNT = len(CANONICAL_LABEL_NAMES)

pytestmark = pytest.mark.skipif(
    not model_is_cached(CONFIG),
    reason=(
        f"{CONFIG.base_model_id}@{CONFIG.base_model_revision} is not in the local "
        "Hugging Face cache; run `make train` once on a connected machine to populate it"
    ),
)

SAMPLE_TEXTS = (
    "My card has not arrived yet",
    "How do I change my PIN?",
    "Why was I charged an extra fee?",
)


@pytest.fixture(scope="module")
def tokenizer() -> object:
    return load_tokenizer(CONFIG)


@pytest.fixture(scope="module")
def model() -> object:
    seed_training(CONFIG.seed)
    return load_model(CONFIG, CANONICAL_LABEL_NAMES)


def test_device_is_cpu_and_no_gpu_is_claimed() -> None:
    facts = runtime_facts(resolve_device())

    # Decision D10 fixes this run to CPU. `cuda_available` is recorded as an
    # observed fact, but the device must not follow it.
    assert facts.device == "cpu"
    assert facts.thread_count >= 1
    assert facts.peak_memory_bytes > 0
    assert facts.torch_version
    assert facts.transformers_version


def test_runtime_payload_is_json_serialisable() -> None:
    import json

    payload = runtime_payload(runtime_facts(resolve_device()))

    assert json.loads(json.dumps(payload)) == payload
    assert set(payload) == {
        "device",
        "torch_version",
        "transformers_version",
        "thread_count",
        "cuda_available",
        "peak_memory_bytes",
    }


def test_tokenizer_loads_at_the_pinned_revision(tokenizer: object) -> None:
    encoded = encode(tokenizer, SAMPLE_TEXTS, max_sequence_length=96)  # type: ignore[arg-type]

    assert "input_ids" in encoded
    assert "attention_mask" in encoded
    assert encoded["input_ids"].shape[0] == len(SAMPLE_TEXTS)
    assert encoded["input_ids"].shape[1] <= 96


def test_truncation_respects_the_configured_length(tokenizer: object) -> None:
    long_text = "overdraft " * 500

    encoded = encode(tokenizer, [long_text], max_sequence_length=96)  # type: ignore[arg-type]

    assert encoded["input_ids"].shape == (1, 96)


def test_classification_head_has_exactly_one_output_per_label(model: object) -> None:
    # Read from the linear layer itself, not from config, so a config value that
    # disagrees with the parameter shape cannot confirm itself.
    assert output_width(model) == LABEL_COUNT  # type: ignore[arg-type]
    assert int(model.config.num_labels) == LABEL_COUNT  # type: ignore[attr-defined]


def test_loaded_model_carries_the_canonical_label_mapping(model: object) -> None:
    id2label = model.config.id2label  # type: ignore[attr-defined]

    assert len(id2label) == LABEL_COUNT
    assert id2label[0] == CANONICAL_LABEL_NAMES[0]
    assert id2label[LABEL_COUNT - 1] == CANONICAL_LABEL_NAMES[-1]


def test_one_batch_yields_a_finite_loss_and_correct_logit_shape(
    model: object, tokenizer: object
) -> None:
    batch = encode(tokenizer, SAMPLE_TEXTS, max_sequence_length=96)  # type: ignore[arg-type]
    labels = torch.tensor([0, 21, 15], dtype=torch.long)

    loss, logits = forward_loss(model, batch, labels)  # type: ignore[arg-type]

    assert torch.isfinite(loss)
    assert loss.item() > 0.0
    assert tuple(logits.shape) == (len(SAMPLE_TEXTS), LABEL_COUNT)
    assert bool(torch.isfinite(logits).all())


def test_backward_pass_populates_finite_gradients(model: object, tokenizer: object) -> None:
    seed_training(CONFIG.seed)
    fresh = load_model(CONFIG, CANONICAL_LABEL_NAMES)
    fresh.train()
    batch = encode(tokenizer, SAMPLE_TEXTS, max_sequence_length=96)  # type: ignore[arg-type]
    labels = torch.tensor([0, 21, 15], dtype=torch.long)

    loss, _ = forward_loss(fresh, batch, labels)
    loss.backward()  # type: ignore[no-untyped-call]

    gradients = [
        parameter.grad
        for parameter in fresh.parameters()
        if parameter.requires_grad and parameter.grad is not None
    ]
    assert gradients, "Backward produced no gradients at all"
    assert all(bool(torch.isfinite(gradient).all()) for gradient in gradients)


def test_one_optimisation_step_changes_the_head_weights(tokenizer: object) -> None:
    seed_training(CONFIG.seed)
    fresh = load_model(CONFIG, CANONICAL_LABEL_NAMES)
    fresh.train()
    optimizer = build_optimizer(fresh, CONFIG.training)
    schedule = build_schedule(optimizer, CONFIG.training, total_steps=4)
    head = classification_head(fresh)
    before = head.weight.detach().clone()

    batch = encode(tokenizer, SAMPLE_TEXTS, max_sequence_length=96)  # type: ignore[arg-type]
    loss, _ = forward_loss(fresh, batch, torch.tensor([0, 21, 15], dtype=torch.long))
    loss.backward()  # type: ignore[no-untyped-call]
    torch.nn.utils.clip_grad_norm_(fresh.parameters(), CONFIG.training.max_grad_norm)
    optimizer.step()
    schedule.step()

    assert not torch.equal(before, head.weight.detach())


def test_optimizer_exempts_bias_and_layernorm_from_weight_decay(model: object) -> None:
    optimizer = build_optimizer(model, CONFIG.training)  # type: ignore[arg-type]

    decays = [group["weight_decay"] for group in optimizer.param_groups]
    assert decays == [CONFIG.training.weight_decay, 0.0]
    assert all(group["params"] for group in optimizer.param_groups)


def test_schedule_warms_up_then_decays_to_zero(model: object) -> None:
    optimizer = build_optimizer(model, CONFIG.training)  # type: ignore[arg-type]
    total_steps = 100
    schedule = build_schedule(optimizer, CONFIG.training, total_steps=total_steps)

    rates: list[float] = []
    for _ in range(total_steps):
        rates.append(optimizer.param_groups[0]["lr"])
        # This test reads the LR curve rather than training, so `optimizer.step()`
        # is deliberately absent. Suppressing PyTorch's step-order heuristic keeps
        # the suite warning-free without hiding a real ordering mistake, which the
        # real loop in `scripts/train_transformer.py` is where it would matter.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Detected call of")
            schedule.step()

    warmup_steps = int(total_steps * CONFIG.training.warmup_ratio)
    assert rates[0] < rates[warmup_steps]
    assert rates[warmup_steps] == pytest.approx(CONFIG.training.learning_rate, rel=1e-9)
    assert rates[-1] < rates[warmup_steps]
    assert optimizer.param_groups[0]["lr"] == pytest.approx(0.0, abs=1e-12)


def test_predicted_probabilities_are_a_valid_distribution_per_example(
    model: object, tokenizer: object
) -> None:
    probabilities = predict_probabilities(
        model,  # type: ignore[arg-type]
        tokenizer,  # type: ignore[arg-type]
        SAMPLE_TEXTS,
        label_count=LABEL_COUNT,
        training=CONFIG.training,
        device=resolve_device(),
    )

    assert probabilities.shape == (len(SAMPLE_TEXTS), LABEL_COUNT)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)
    assert np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-6, rtol=0.0)


def test_predictions_are_independent_of_batch_size(model: object, tokenizer: object) -> None:
    from dataclasses import replace

    device = resolve_device()
    one_at_a_time = predict_probabilities(
        model,  # type: ignore[arg-type]
        tokenizer,  # type: ignore[arg-type]
        SAMPLE_TEXTS,
        label_count=LABEL_COUNT,
        training=replace(CONFIG.training, eval_batch_size=1),
        device=device,
    )
    all_at_once = predict_probabilities(
        model,  # type: ignore[arg-type]
        tokenizer,  # type: ignore[arg-type]
        SAMPLE_TEXTS,
        label_count=LABEL_COUNT,
        training=replace(CONFIG.training, eval_batch_size=len(SAMPLE_TEXTS)),
        device=device,
    )

    # Padding to the longest member of a batch must not change a row's own
    # prediction, and batching must not reorder output rows.
    assert labels_from_probabilities(one_at_a_time) == labels_from_probabilities(all_at_once)
    assert np.allclose(one_at_a_time, all_at_once, atol=1e-5, rtol=0.0)


def test_labels_and_confidences_come_from_the_same_matrix(
    model: object, tokenizer: object
) -> None:
    probabilities = predict_probabilities(
        model,  # type: ignore[arg-type]
        tokenizer,  # type: ignore[arg-type]
        SAMPLE_TEXTS,
        label_count=LABEL_COUNT,
        training=CONFIG.training,
        device=resolve_device(),
    )
    labels = labels_from_probabilities(probabilities)
    confidences = confidences_from_probabilities(probabilities)

    for row, (label, confidence) in enumerate(zip(labels, confidences, strict=True)):
        assert 0 <= label < LABEL_COUNT
        assert confidence == pytest.approx(float(probabilities[row, label]))


def test_prediction_restores_training_mode(model: object, tokenizer: object) -> None:
    model.train()  # type: ignore[attr-defined]

    predict_probabilities(
        model,  # type: ignore[arg-type]
        tokenizer,  # type: ignore[arg-type]
        SAMPLE_TEXTS,
        label_count=LABEL_COUNT,
        training=CONFIG.training,
        device=resolve_device(),
    )

    # A prediction call that left the model in eval mode would silently disable
    # dropout for the rest of training.
    assert model.training is True  # type: ignore[attr-defined]


def test_step_count_covers_every_example_in_every_epoch() -> None:
    slices = batch_slices(8_502, CONFIG.training.train_batch_size)

    assert len(slices) == 532
    assert total_optimisation_steps(8_502, CONFIG.training) == 532 * CONFIG.training.epochs
    # The final batch is short rather than dropped, so no example is skipped.
    assert sum(end - start for start, end in slices) == 8_502


def test_mismatched_head_width_is_rejected(model: object) -> None:
    with pytest.raises(TrainingError, match="label map"):
        load_model(CONFIG, ())
