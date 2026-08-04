"""The latency measurement contract (NFR-006, D16, step 5 of the E05 plan).

Latency is the one reported quantity that does not reproduce, so what has to be
pinned is the *protocol* rather than any number. These tests fix the four choices
that decide whether a reported percentile means anything:

* warm-up requests are discarded rather than folded into p50,
* samples are a seeded permutation of real texts rather than the first N rows,
* percentiles are nearest-rank, so every reported value was actually observed,
* the environment is read from the runtime rather than assumed.

The timing assertions use a deliberately slow stub during warm-up and a fast one
afterwards, with a two-orders-of-magnitude margin, so they test the discard rule
rather than the host's scheduling jitter.
"""

from __future__ import annotations

import json
import time

import pytest

from intentguard.latency import (
    LATENCY_BATCH_SIZE,
    LATENCY_CAVEAT,
    LATENCY_CLOCK,
    MEASURED_REQUESTS,
    SAMPLE_SEED,
    WARM_UP_REQUESTS,
    LatencyError,
    _nearest_rank,  # a protocol detail worth pinning directly
    latency_environment,
    measure_latency,
    select_latency_samples,
)

TEXTS = tuple(f"request number {index}" for index in range(50))
LENGTHS = tuple(5 + (index % 11) for index in range(50))


def test_the_protocol_constants_are_the_recorded_decision() -> None:
    """D16 fixes these; a change to any of them changes what the report claims."""

    assert WARM_UP_REQUESTS == 20
    assert MEASURED_REQUESTS == 200
    assert LATENCY_BATCH_SIZE == 1
    assert LATENCY_CLOCK == "time.perf_counter"


def test_the_caveat_denies_a_service_level_reading_in_words() -> None:
    assert "not a service-level claim" in LATENCY_CAVEAT
    assert "does not generalize" in LATENCY_CAVEAT


def test_sampling_is_deterministic_for_a_seed() -> None:
    first = select_latency_samples(TEXTS, LENGTHS, count=10, sample_seed=SAMPLE_SEED)
    second = select_latency_samples(TEXTS, LENGTHS, count=10, sample_seed=SAMPLE_SEED)

    assert first.texts == second.texts
    assert first.sample_seed == SAMPLE_SEED


def test_a_different_seed_draws_a_different_sample() -> None:
    first = select_latency_samples(TEXTS, LENGTHS, count=10, sample_seed=1)
    second = select_latency_samples(TEXTS, LENGTHS, count=10, sample_seed=2)

    assert first.texts != second.texts


def test_sampling_permutes_rather_than_slicing_the_head() -> None:
    """The test split arrives grouped by label, so the first N rows are not a sample.

    Taking a slice would over-represent a handful of intents and their
    characteristic phrasing lengths, which is exactly what p95 is sensitive to.
    """

    samples = select_latency_samples(TEXTS, LENGTHS, count=10, sample_seed=SAMPLE_SEED)

    assert samples.texts != TEXTS[:10]
    assert set(samples.texts) <= set(TEXTS)
    assert len(set(samples.texts)) == 10, "A permutation must not repeat a row"


def test_token_length_spread_is_recorded_from_the_chosen_rows() -> None:
    samples = select_latency_samples(TEXTS, LENGTHS, count=10, sample_seed=SAMPLE_SEED)
    chosen = [LENGTHS[TEXTS.index(text)] for text in samples.texts]

    assert samples.token_length_min == min(chosen)
    assert samples.token_length_max == max(chosen)
    assert samples.token_length_min <= samples.token_length_median
    assert samples.token_length_median <= samples.token_length_max


def test_sample_payload_is_json_serialisable_and_names_the_seed() -> None:
    payload = select_latency_samples(TEXTS, LENGTHS, count=10).payload()

    assert payload["sample_count"] == 10
    assert payload["sample_seed"] == SAMPLE_SEED
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize(
    ("texts", "lengths", "count"),
    [
        (TEXTS, LENGTHS[:10], 5),
        ((), (), 1),
        (TEXTS, LENGTHS, 0),
        (TEXTS, LENGTHS, 51),
    ],
)
def test_sampling_rejects_an_impossible_request(
    texts: tuple[str, ...], lengths: tuple[int, ...], count: int
) -> None:
    with pytest.raises(LatencyError):
        select_latency_samples(texts, lengths, count=count)


def test_sampling_rejects_a_non_positive_or_non_integer_token_length() -> None:
    with pytest.raises(LatencyError):
        select_latency_samples(("a", "b"), (5, 0), count=2)
    with pytest.raises(LatencyError):
        select_latency_samples(("a", "b"), (5, 7.5), count=2)  # type: ignore[arg-type]
    with pytest.raises(LatencyError):
        select_latency_samples(("a", "b"), (5, True), count=2)


def test_every_measured_request_is_timed_and_warm_up_is_additional() -> None:
    calls: list[str] = []
    samples = select_latency_samples(TEXTS, LENGTHS, count=10)

    measurement = measure_latency(
        calls.append,
        samples,
        model_name="stub",
        max_sequence_length=64,
        warm_up_requests=3,
        measured_requests=7,
    )

    assert len(calls) == 3 + 7
    assert measurement.warm_up_requests == 3
    assert measurement.measured_requests == 7


def test_warm_up_cost_is_excluded_from_every_reported_percentile() -> None:
    """Lazy kernel initialisation is paid once; including it would inflate p50.

    The stub sleeps 50 ms for each of its first three calls and returns instantly
    afterwards. If warm-up were timed, ``max_ms`` would exceed 50; the assertion
    allows 25 ms, so it cannot pass by scheduling luck.
    """

    remaining_slow = [3]

    def predict_one(_: str) -> None:
        if remaining_slow[0] > 0:
            remaining_slow[0] -= 1
            time.sleep(0.05)

    samples = select_latency_samples(TEXTS, LENGTHS, count=10)
    measurement = measure_latency(
        predict_one,
        samples,
        model_name="stub",
        max_sequence_length=64,
        warm_up_requests=3,
        measured_requests=7,
    )

    assert remaining_slow[0] == 0, "The warm-up phase must have consumed the slow calls"
    assert measurement.max_ms < 25.0
    assert measurement.p50_ms < 25.0


def test_measurement_refuses_to_reuse_a_text_across_measured_requests() -> None:
    """Timing one repeated literal measures one token length, not the model."""

    samples = select_latency_samples(TEXTS, LENGTHS, count=5)

    with pytest.raises(LatencyError):
        measure_latency(
            lambda _: None,
            samples,
            model_name="stub",
            max_sequence_length=64,
            warm_up_requests=0,
            measured_requests=6,
        )


def test_measurement_rejects_a_negative_warm_up_or_empty_measurement() -> None:
    samples = select_latency_samples(TEXTS, LENGTHS, count=10)

    with pytest.raises(LatencyError):
        measure_latency(
            lambda _: None,
            samples,
            model_name="stub",
            max_sequence_length=64,
            warm_up_requests=-1,
            measured_requests=5,
        )
    with pytest.raises(LatencyError):
        measure_latency(
            lambda _: None,
            samples,
            model_name="stub",
            max_sequence_length=64,
            warm_up_requests=0,
            measured_requests=0,
        )


def test_reported_percentiles_are_ordered_and_bracketed_by_the_extremes() -> None:
    samples = select_latency_samples(TEXTS, LENGTHS, count=10)
    measurement = measure_latency(
        lambda _: None,
        samples,
        model_name="stub",
        max_sequence_length=64,
        warm_up_requests=0,
        measured_requests=10,
    )

    assert measurement.min_ms <= measurement.p50_ms <= measurement.p95_ms
    assert measurement.p95_ms <= measurement.max_ms
    assert measurement.min_ms <= measurement.mean_ms <= measurement.max_ms


def test_percentiles_are_nearest_rank_rather_than_interpolated() -> None:
    """Every reported value must be a duration that was actually observed."""

    ordered = [float(value) for value in range(1, 201)]

    assert _nearest_rank(ordered, 50.0) == 100.0
    assert _nearest_rank(ordered, 95.0) == 190.0
    assert _nearest_rank(ordered, 100.0) == 200.0
    assert _nearest_rank([4.0], 50.0) == 4.0
    for percentile in (50.0, 95.0):
        assert _nearest_rank(ordered, percentile) in ordered


def test_nearest_rank_refuses_an_empty_sequence_rather_than_returning_zero() -> None:
    with pytest.raises(LatencyError):
        _nearest_rank([], 50.0)


def test_measurement_payload_denies_the_service_level_reading() -> None:
    samples = select_latency_samples(TEXTS, LENGTHS, count=10)
    payload = measure_latency(
        lambda _: None,
        samples,
        model_name="stub",
        max_sequence_length=64,
        warm_up_requests=0,
        measured_requests=5,
    ).payload()

    assert payload["is_service_level_claim"] is False
    assert payload["clock"] == LATENCY_CLOCK
    assert payload["batch_size"] == LATENCY_BATCH_SIZE
    assert payload["measured_requests"] == 5
    assert json.loads(json.dumps(payload)) == payload


def test_environment_records_what_the_runtime_reported() -> None:
    environment = latency_environment(device="cpu", thread_count=4, cuda_available=False)

    assert environment["device"] == "cpu"
    assert environment["cuda_available"] is False
    assert environment["thread_count"] == 4
    assert json.loads(json.dumps(environment)) == environment


def test_environment_refuses_an_assumed_cuda_flag() -> None:
    """A recorded hardware fact that was never observed is worse than an absent one."""

    with pytest.raises(LatencyError):
        latency_environment(
            device="cpu",
            thread_count=4,
            cuda_available="false",  # type: ignore[arg-type]
        )
