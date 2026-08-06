"""Real-artifact API evidence: accept, abstain, truncation, readiness (AC-006, AC-007, AC-009).

Every test in this file runs against the **actual sealed DistilBERT bundle** through
the actual FastAPI application. That is the whole point: the S06.1 contract suite
already proves the boundary with a deterministic double, and a double can never
satisfy AC-006, AC-007, or AC-009, which are about a loaded artifact.

The bundle does not live inside this worktree, so the suite is gated on
``INTENTGUARD_ARTIFACT_ROOT`` naming a root that holds one. An unset variable skips
with a message saying what to set, rather than passing vacuously — a green run that
loaded nothing would be worse than a skip, because it would look like evidence.

**No test here asserts a specific confidence, label, or latency.** Those are
properties of the trained weights, and pinning one would turn a model measurement
into a test fixture. What is asserted is the contract: that accept and abstain are
both reachable through the real model, that the decision agrees with the persisted
threshold, that truncation is reported from a second tokenizer pass, and that
readiness is checked rather than assumed. The one artifact fact that *is* pinned is
the threshold's provenance — it must come from validation.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from intentguard.api import MODEL_NOT_READY, REQUEST_ID_HEADER, create_app, set_predictor
from intentguard.artifacts import ArtifactError
from intentguard.config import load_foundation_config
from intentguard.data import CANONICAL_LABEL_NAMES, LABEL_COUNT
from intentguard.predictor import (
    ARTIFACT_ROOT_VARIABLE,
    ArtifactPredictor,
    PredictorError,
    create_serving_app,
    load_artifact_predictor,
    locate_transformer_bundle,
    resolve_artifact_root,
)
from intentguard.threshold import decide

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")


def _configured_root() -> Path | None:
    """Return the artifact root only when it actually holds a transformer bundle."""

    override = os.environ.get(ARTIFACT_ROOT_VARIABLE, "").strip()
    if not override:
        return None
    root = Path(override).expanduser()
    try:
        locate_transformer_bundle(root)
    except PredictorError:
        return None
    return root


ARTIFACT_ROOT = _configured_root()

pytestmark = pytest.mark.skipif(
    ARTIFACT_ROOT is None,
    reason=(
        f"{ARTIFACT_ROOT_VARIABLE} is not set to a root holding an "
        "`intentguard-distilbert` bundle; run `make train` once, then set the "
        "variable to that artifacts directory"
    ),
)

# A short, plainly in-domain request. Chosen for being unambiguous BANKING77
# vocabulary, not for a confidence it is known to produce.
IN_DOMAIN_TEXT = "How do I activate my new card?"

# Out-of-domain text taken from the same six declared categories as the E05
# unsupported fixture. No BANKING77 intent is correct for either, so a low
# confidence is the expected behaviour rather than a tuned outcome.
OUT_OF_DOMAIN_TEXTS = (
    "What is the weather forecast for Lisbon this weekend?",
    "Please recommend a good science fiction novel for a long flight.",
    "Book me a table for four at an Italian restaurant tonight.",
)


@pytest.fixture(scope="module")
def predictor() -> ArtifactPredictor:
    """Load the real bundle once. Loading re-hashes every file, so it is not cheap."""

    assert ARTIFACT_ROOT is not None
    return load_artifact_predictor(CONFIG, artifact_root=ARTIFACT_ROOT)


@pytest.fixture
def client(predictor: ArtifactPredictor) -> TestClient:
    app = create_app()
    set_predictor(app, predictor)
    return TestClient(app)


def _predict(client: TestClient, text: str) -> dict[str, Any]:
    response = client.post("/v1/predict", json={"text": text})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# --------------------------------------------------------------------------------
# The artifact itself
# --------------------------------------------------------------------------------


def test_served_threshold_was_selected_from_validation_data(
    predictor: ArtifactPredictor,
) -> None:
    """AC-005 at the serving boundary: a test-selected threshold must never be served."""

    record = predictor.bundle.threshold
    assert record is not None
    assert record["source"] == "validation"
    assert record["rule"] == "min_selective_risk_at_min_coverage"
    # The value is read from the bundle rather than written here, so this test does
    # not become a second place that has to be updated when a new bundle is trained.
    assert predictor.threshold == pytest.approx(float(record["threshold"]))  # type: ignore[arg-type]
    assert 0.0 <= predictor.threshold <= 1.0


def test_served_artifact_carries_the_canonical_77_label_map(
    predictor: ArtifactPredictor,
) -> None:
    assert predictor.label_count == LABEL_COUNT
    assert predictor.bundle.label_names == CANONICAL_LABEL_NAMES


def test_model_version_is_the_content_derived_run_id(predictor: ArtifactPredictor) -> None:
    assert predictor.model_version == predictor.bundle.run_id
    assert predictor.model_version.startswith("intentguard-distilbert-")


def test_model_is_loaded_in_eval_mode_and_reports_ready(
    predictor: ArtifactPredictor,
) -> None:
    # Dropout still active at serving would make two predictions for the same text
    # disagree, so eval mode is part of readiness rather than an implementation detail.
    assert predictor.is_ready() is True


# --------------------------------------------------------------------------------
# AC-009 — readiness
# --------------------------------------------------------------------------------


def test_health_reports_ready_with_the_real_artifact_metadata(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ready",
        "model_version": body["model_version"],
        "label_count": LABEL_COUNT,
        "device": "cpu",
    }
    assert body["model_version"].startswith("intentguard-distilbert-")
    assert response.headers[REQUEST_ID_HEADER]


@contextmanager
def _left_in_training_mode(predictor: ArtifactPredictor) -> Iterator[None]:
    """Put the loaded model back into training mode, then restore it.

    Reaching into the private attribute is the point: no public API should let a caller
    un-ready a loaded predictor, so simulating that drift has to be done from inside.
    Restoration is unconditional because the `predictor` fixture is module-scoped —
    leaking training mode would make every later test in this file run against a model
    with dropout active.
    """

    model = predictor._model
    model.train()
    try:
        yield
    finally:
        model.eval()  # type: ignore[no-untyped-call]


def test_health_reports_not_ready_when_the_model_is_left_in_training_mode(
    predictor: ArtifactPredictor,
) -> None:
    """Readiness must be a checked property, not a constant returned by a loaded object."""

    app = create_app()
    set_predictor(app, predictor)
    with _left_in_training_mode(predictor):
        response = TestClient(app).get("/health")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == MODEL_NOT_READY
    assert predictor.is_ready() is True


def test_prediction_is_refused_while_the_model_is_not_ready(
    predictor: ArtifactPredictor,
) -> None:
    app = create_app()
    set_predictor(app, predictor)
    with _left_in_training_mode(predictor):
        response = TestClient(app).post("/v1/predict", json={"text": IN_DOMAIN_TEXT})

        assert response.status_code == 503
        assert response.json()["error"]["code"] == MODEL_NOT_READY


# --------------------------------------------------------------------------------
# AC-006 / AC-007 — accept and abstain through the real model
# --------------------------------------------------------------------------------


def test_in_domain_request_satisfies_the_response_contract(client: TestClient) -> None:
    body = _predict(client, IN_DOMAIN_TEXT)

    assert set(body) == {
        "request_id",
        "decision",
        "intent",
        "confidence",
        "threshold",
        "input_truncated",
        "model_version",
        "latency_ms",
    }
    assert body["decision"] in ("accept", "abstain")
    assert 0.0 <= body["confidence"] <= 1.0
    assert 0.0 <= body["threshold"] <= 1.0
    assert body["input_truncated"] is False
    assert body["latency_ms"] >= 0.0
    assert body["model_version"].startswith("intentguard-distilbert-")


def test_an_accept_is_reachable_and_names_a_real_banking77_intent(
    client: TestClient, predictor: ArtifactPredictor
) -> None:
    """AC-006 through the loaded artifact, not a double.

    The text is in-domain, so an accept is expected — but the assertion is written to
    fail loudly rather than skip if the model abstains, because a model that cannot
    accept anything would satisfy an `if accepted:` guard vacuously.
    """

    body = _predict(client, IN_DOMAIN_TEXT)

    assert body["decision"] == "accept", (
        "the real artifact abstained on plainly in-domain text; "
        f"confidence {body['confidence']} against threshold {body['threshold']}"
    )
    assert body["intent"] in CANONICAL_LABEL_NAMES
    assert body["confidence"] >= body["threshold"]
    assert body["threshold"] == pytest.approx(predictor.threshold)


def test_an_abstention_is_reachable_and_names_no_intent(client: TestClient) -> None:
    """AC-007 through the loaded artifact.

    All three out-of-domain texts are tried and at least one must abstain. A single
    fixed text would make this test depend on one model's behaviour on one string;
    requiring one of three keeps it a check that abstention is reachable at all.
    """

    bodies = [_predict(client, text) for text in OUT_OF_DOMAIN_TEXTS]
    abstentions = [body for body in bodies if body["decision"] == "abstain"]

    assert abstentions, (
        "no out-of-domain text abstained; confidences "
        f"{[body['confidence'] for body in bodies]} against threshold "
        f"{bodies[0]['threshold']}"
    )
    for body in abstentions:
        assert body["intent"] is None
        assert body["confidence"] < body["threshold"]


def test_every_decision_agrees_with_the_persisted_threshold(
    client: TestClient, predictor: ArtifactPredictor
) -> None:
    """The published decision must be the shared `decide` rule, not a second opinion."""

    for text in (IN_DOMAIN_TEXT, *OUT_OF_DOMAIN_TEXTS):
        body = _predict(client, text)

        assert body["threshold"] == pytest.approx(predictor.threshold)
        assert body["decision"] == decide(body["confidence"], predictor.threshold)
        assert (body["intent"] is None) == (body["decision"] == "abstain")


def test_repeated_identical_requests_produce_identical_predictions(
    client: TestClient,
) -> None:
    """Determinism at serving: eval mode means no dropout, so nothing should vary.

    `latency_ms` and `request_id` legitimately differ between calls and are excluded.
    """

    varying = {"latency_ms", "request_id"}
    first = _predict(client, IN_DOMAIN_TEXT)
    second = _predict(client, IN_DOMAIN_TEXT)

    assert {k: v for k, v in first.items() if k not in varying} == {
        k: v for k, v in second.items() if k not in varying
    }


# --------------------------------------------------------------------------------
# Truncation — the second tokenizer pass
# --------------------------------------------------------------------------------


def test_short_input_is_not_reported_as_truncated(predictor: ArtifactPredictor) -> None:
    assert predictor.input_truncated(IN_DOMAIN_TEXT) is False


def test_long_input_within_the_character_limit_is_reported_as_truncated(
    client: TestClient, predictor: ArtifactPredictor
) -> None:
    """A 512-character request is valid input that still exceeds the token budget.

    This is why `input_truncated` cannot be derived from the truncating encode: the
    request passes the 512-character schema bound, so it reaches the model, and the
    truncating pass returns exactly `max_sequence_length` tokens either way.
    """

    text = ("overdraft " * 52)[:512]
    assert len(text) == 512

    assert predictor.input_truncated(text) is True
    body = _predict(client, text)
    assert body["input_truncated"] is True


def test_truncation_boundary_is_the_configured_maximum_sequence_length(
    predictor: ArtifactPredictor,
) -> None:
    """Cross-check the flag against the bundle's own persisted `max_sequence_length`.

    Read from the artifact rather than from `configs/default.toml`, because the live
    file can be edited after a bundle is sealed and serving must obey the bundle.
    """

    persisted = predictor.bundle.config["training"]
    assert isinstance(persisted, dict)
    maximum = persisted["max_sequence_length"]
    assert isinstance(maximum, int)

    # The loaded tokenizer, not a fresh one: the assertion is about the pass the
    # predictor actually makes.
    tokenizer = predictor._tokenizer
    short_ids = tokenizer([IN_DOMAIN_TEXT], truncation=False, verbose=False)["input_ids"][0]
    long_text = ("overdraft " * 52)[:512]
    long_ids = tokenizer([long_text], truncation=False, verbose=False)["input_ids"][0]

    assert len(short_ids) <= maximum
    assert len(long_ids) > maximum


# --------------------------------------------------------------------------------
# Startup validation
# --------------------------------------------------------------------------------


def test_create_serving_app_installs_a_real_predictor() -> None:
    assert ARTIFACT_ROOT is not None
    app = create_serving_app(CONFIG, artifact_root=ARTIFACT_ROOT)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["label_count"] == LABEL_COUNT


def test_missing_artifact_root_fails_at_startup(tmp_path: Path) -> None:
    """Startup must refuse rather than serve 503s for a knowable defect."""

    with pytest.raises(PredictorError, match="No intentguard-distilbert artifact directory"):
        load_artifact_predictor(CONFIG, artifact_root=tmp_path)


def test_empty_artifact_directory_fails_at_startup(tmp_path: Path) -> None:
    (tmp_path / "intentguard-distilbert").mkdir()

    with pytest.raises(PredictorError, match="No intentguard-distilbert bundle exists"):
        load_artifact_predictor(CONFIG, artifact_root=tmp_path)


def test_two_candidate_bundles_are_refused_as_ambiguous(tmp_path: Path) -> None:
    """A stale sibling bundle must stop startup, not be chosen silently."""

    parent = tmp_path / "intentguard-distilbert"
    parent.mkdir()
    (parent / "intentguard-distilbert-aaaaaaaaaaaa-111111111111").mkdir()
    (parent / "intentguard-distilbert-aaaaaaaaaaaa-222222222222").mkdir()

    with pytest.raises(PredictorError, match="ambiguous"):
        locate_transformer_bundle(tmp_path)


def test_a_corrupted_bundle_file_fails_verification(tmp_path: Path) -> None:
    """Checksum verification must run at serving load, not only at save time."""

    assert ARTIFACT_ROOT is not None
    import shutil

    source = locate_transformer_bundle(ARTIFACT_ROOT)
    destination = tmp_path / "intentguard-distilbert" / source.name
    shutil.copytree(source, destination)
    labels = destination / "labels.json"
    labels.write_text(labels.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ArtifactError, match="checksum mismatch"):
        load_artifact_predictor(CONFIG, artifact_root=tmp_path)


def test_a_test_sourced_threshold_is_refused(tmp_path: Path) -> None:
    """The leakage control, verified by mutation rather than by reading the code.

    `load_artifact` rejects this first, which is the correct order — a bundle claiming
    a test-selected threshold must not load at all. The predictor's own duplicate
    check is exercised separately in the unit suite.
    """

    assert ARTIFACT_ROOT is not None
    import json
    import shutil

    source = locate_transformer_bundle(ARTIFACT_ROOT)
    destination = tmp_path / "intentguard-distilbert" / source.name
    shutil.copytree(source, destination)
    path = destination / "threshold.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["source"] = "test"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ArtifactError):
        load_artifact_predictor(CONFIG, artifact_root=tmp_path)


def test_environment_variable_overrides_the_configured_artifact_root() -> None:
    assert ARTIFACT_ROOT is not None
    resolved = resolve_artifact_root(CONFIG, {ARTIFACT_ROOT_VARIABLE: str(ARTIFACT_ROOT)})

    assert resolved == ARTIFACT_ROOT
