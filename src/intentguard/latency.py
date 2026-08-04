"""Single-request latency measurement for the evaluation report (NFR-006).

This module is descriptive, not an SLA. `ML_SYSTEM_DESIGN.md:171-175` requires the
warm-up count, the measured count, and the environment; the protocol itself is
decision D16.

Two properties make the reported percentiles mean something:

**Samples come from the real test split, by a seeded deterministic shuffle.** With
`padding="longest"` a single-item batch is padded to its own length, so timing one
repeated literal measures one token length and makes p95 an artifact of that
choice rather than a property of the model. Sampling real rows of differing length
is what gives the spread its meaning, and the sampled token-length min, median,
and max are recorded so a reader knows what was actually timed.

**Warm-up is discarded.** The first requests through a freshly loaded model pay
lazy kernel initialisation and allocator growth, so including them would inflate
p50 with a cost no subsequent request pays.

Latency is the one section of the evaluation report that is *not* reproducible:
wall-clock timing differs between two runs of the same configuration. The run ID
therefore covers the sampling protocol — counts, seed, batch and sequence
conditions — and never the measured durations. See D14.
"""

from __future__ import annotations

import platform
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

WARM_UP_REQUESTS: Final = 20
MEASURED_REQUESTS: Final = 200
LATENCY_BATCH_SIZE: Final = 1
SAMPLE_SEED: Final = 42
LATENCY_CLOCK: Final = "time.perf_counter"

#: Mandated verbatim by D16 in both `comparison.json` and `comparison.md`. A
#: latency number without this sentence invites exactly the service-level reading
#: that `ML_SYSTEM_DESIGN.md` forbids.
LATENCY_CAVEAT: Final = (
    "Latency is descriptive for this measured machine under the stated batch and "
    "sequence conditions. It is not a service-level claim and does not generalize "
    "to other hardware."
)


class LatencyError(ValueError):
    """Raised when a latency measurement request violates the measurement contract."""


@dataclass(frozen=True, slots=True)
class LatencySamples:
    """The texts chosen for timing, with the token lengths they represent."""

    texts: tuple[str, ...]
    sample_seed: int
    token_length_min: int
    token_length_median: float
    token_length_max: int

    def payload(self) -> dict[str, object]:
        return {
            "sample_count": len(self.texts),
            "sample_seed": self.sample_seed,
            "token_length_min": self.token_length_min,
            "token_length_median": self.token_length_median,
            "token_length_max": self.token_length_max,
        }


@dataclass(frozen=True, slots=True)
class LatencyMeasurement:
    """Measured single-request latency for one model under a declared protocol."""

    model_name: str
    warm_up_requests: int
    measured_requests: int
    batch_size: int
    max_sequence_length: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float

    def payload(self) -> dict[str, object]:
        return {
            "model": self.model_name,
            "warm_up_requests": self.warm_up_requests,
            "measured_requests": self.measured_requests,
            "batch_size": self.batch_size,
            "max_sequence_length": self.max_sequence_length,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "mean_ms": self.mean_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "clock": LATENCY_CLOCK,
            "is_service_level_claim": False,
        }


def select_latency_samples(
    texts: Sequence[str],
    token_lengths: Sequence[int],
    *,
    count: int = MEASURED_REQUESTS,
    sample_seed: int = SAMPLE_SEED,
) -> LatencySamples:
    """Draw a deterministic sample of real texts and record their token lengths.

    A seeded permutation rather than a slice: the test split arrives grouped by
    label, so the first `count` rows would over-represent a handful of intents and
    their characteristic phrasing lengths.
    """

    if len(texts) != len(token_lengths):
        raise LatencyError("Text and token-length counts differ")
    if len(texts) == 0:
        raise LatencyError("Latency sampling requires at least one text")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise LatencyError("count must be a positive integer")
    if count > len(texts):
        raise LatencyError(f"Cannot sample {count} texts from {len(texts)} available")
    for index, length in enumerate(token_lengths):
        if isinstance(length, bool) or not isinstance(length, (int, np.integer)):
            raise LatencyError(f"token_lengths[{index}] is not an integer")
        if int(length) < 1:
            raise LatencyError(f"token_lengths[{index}] is not positive")

    order = np.random.default_rng(sample_seed).permutation(len(texts))[:count]
    chosen_texts = tuple(texts[int(index)] for index in order)
    chosen_lengths = [int(token_lengths[int(index)]) for index in order]

    return LatencySamples(
        texts=chosen_texts,
        sample_seed=sample_seed,
        token_length_min=min(chosen_lengths),
        token_length_median=float(statistics.median(chosen_lengths)),
        token_length_max=max(chosen_lengths),
    )


def measure_latency(
    predict_one: Callable[[str], None],
    samples: LatencySamples,
    *,
    model_name: str,
    max_sequence_length: int,
    warm_up_requests: int = WARM_UP_REQUESTS,
    measured_requests: int = MEASURED_REQUESTS,
) -> LatencyMeasurement:
    """Time `measured_requests` single-item predictions after discarding warm-up.

    `predict_one` must perform one complete single-item prediction, tokenisation
    included, because a caller that pre-tokenised outside the timed region would
    report only the forward pass and understate what a request costs.

    Percentiles use nearest-rank on the sorted durations, so every reported value
    is a duration that was actually observed rather than an interpolation between
    two of them.
    """

    if len(samples.texts) < measured_requests:
        raise LatencyError(
            f"{measured_requests} measured requests need at least that many samples, "
            f"but {len(samples.texts)} were provided"
        )
    if warm_up_requests < 0:
        raise LatencyError("warm_up_requests must not be negative")
    if measured_requests < 1:
        raise LatencyError("measured_requests must be at least one")

    for index in range(warm_up_requests):
        predict_one(samples.texts[index % len(samples.texts)])

    durations: list[float] = []
    for index in range(measured_requests):
        started = time.perf_counter()
        predict_one(samples.texts[index])
        durations.append((time.perf_counter() - started) * 1000.0)

    ordered = sorted(durations)
    return LatencyMeasurement(
        model_name=model_name,
        warm_up_requests=warm_up_requests,
        measured_requests=measured_requests,
        batch_size=LATENCY_BATCH_SIZE,
        max_sequence_length=int(max_sequence_length),
        p50_ms=_nearest_rank(ordered, 50.0),
        p95_ms=_nearest_rank(ordered, 95.0),
        mean_ms=float(statistics.fmean(ordered)),
        min_ms=ordered[0],
        max_ms=ordered[-1],
    )


def _nearest_rank(ordered: Sequence[float], percentile: float) -> float:
    """Return the nearest-rank percentile of an already-sorted sequence."""

    if not ordered:
        raise LatencyError("Percentiles require at least one measured duration")
    rank = int(np.ceil(percentile / 100.0 * len(ordered)))
    return float(ordered[max(0, min(rank, len(ordered)) - 1)])


def latency_environment(
    *, device: str, thread_count: int, cuda_available: bool
) -> dict[str, object]:
    """Record the machine facts that make a latency number interpretable.

    `cuda_available` is a parameter rather than a constant. Hard-coding it would
    state a fact about the measuring machine that this module never observed, and
    a recorded environment that was assumed rather than read is worse than one
    that is absent. The caller passes what `torch` actually reports; note that
    CUDA being available is not a claim that it was used — the device field says
    that, and D10 fixes it to CPU.
    """

    if not isinstance(cuda_available, bool):
        raise LatencyError("cuda_available must be a boolean read from the runtime")

    return {
        "device": device,
        "cuda_available": cuda_available,
        "thread_count": int(thread_count),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
