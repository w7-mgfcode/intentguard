"""The public HTTP contract: validation, stable errors, request IDs (NFR-004, AC-008).

Every case here runs against the real FastAPI application. The predictor is a
deterministic double, so these tests prove the boundary and say nothing about
transformer quality — which is what `TEST_STRATEGY.md:62-78` asks of them.

The double counts its calls. AC-008 requires that invalid input "does not invoke
model inference", and the only way to demonstrate that is to assert the call count
stayed at zero rather than to assume a 422 implies it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import NoReturn

import pytest
from fastapi.testclient import TestClient

from intentguard.api import (
    INVALID_REQUEST,
    MALFORMED_JSON,
    MODEL_NOT_READY,
    REQUEST_ID_HEADER,
    create_app,
    generate_request_id,
    resolve_request_id,
    set_predictor,
)
from intentguard.schemas import (
    MAX_REQUEST_ID_CHARACTERS,
    MAX_TEXT_CHARACTERS,
    is_valid_request_id,
)

ACCEPT_THRESHOLD = 0.5


@dataclass
class StubPrediction:
    intent: str | None
    confidence: float
    threshold: float
    decision: str
    input_truncated: bool


class CountingPredictor:
    """A deterministic predictor that records how often inference was invoked."""

    def __init__(self, *, confidence: float = 0.9, ready: bool = True) -> None:
        self._confidence = confidence
        self._ready = ready
        self.calls = 0

    @property
    def model_version(self) -> str:
        return "stub-artifact-0000"

    @property
    def label_count(self) -> int:
        return 77

    @property
    def device(self) -> str:
        return "cpu"

    def is_ready(self) -> bool:
        return self._ready

    def predict(self, text: str) -> StubPrediction:
        self.calls += 1
        accepted = self._confidence >= ACCEPT_THRESHOLD
        return StubPrediction(
            intent="activate_my_card" if accepted else None,
            confidence=self._confidence,
            threshold=ACCEPT_THRESHOLD,
            decision="accept" if accepted else "abstain",
            input_truncated=False,
        )


@pytest.fixture
def predictor() -> CountingPredictor:
    return CountingPredictor()


@pytest.fixture
def client(predictor: CountingPredictor) -> TestClient:
    app = create_app()
    set_predictor(app, predictor)
    return TestClient(app)


def test_accepted_request_matches_the_contract(client: TestClient) -> None:
    response = client.post("/v1/predict", json={"text": "How do I activate my new card?"})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "accept"
    assert body["intent"] == "activate_my_card"
    assert 0.0 <= body["confidence"] <= 1.0
    assert 0.0 <= body["threshold"] <= 1.0
    assert body["input_truncated"] is False
    assert body["model_version"] == "stub-artifact-0000"
    assert body["latency_ms"] >= 0.0
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


def test_abstention_is_a_successful_response_with_a_null_intent() -> None:
    app = create_app()
    set_predictor(app, CountingPredictor(confidence=0.1))
    response = TestClient(app).post("/v1/predict", json={"text": "Recommend a hiking trail."})

    # Abstention is a model decision, not a transport error.
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "abstain"
    assert body["intent"] is None


@pytest.mark.parametrize(
    ("description", "payload"),
    [
        ("empty text", {"text": ""}),
        ("whitespace only", {"text": "   "}),
        ("oversized text", {"text": "a" * (MAX_TEXT_CHARACTERS + 1)}),
        ("extra field", {"text": "hello", "unexpected": 1}),
        ("missing field", {}),
        ("wrong type", {"text": 42}),
        ("control character", {"text": "activate\x00card"}),
    ],
)
def test_invalid_payloads_are_rejected_without_inference(
    client: TestClient, predictor: CountingPredictor, description: str, payload: object
) -> None:
    response = client.post("/v1/predict", json=payload)

    assert response.status_code == 422, description
    body = response.json()
    assert body["error"]["code"] == INVALID_REQUEST
    assert body["error"]["request_id"]
    # AC-008: the model must not have been consulted.
    assert predictor.calls == 0, description


def test_malformed_json_is_400_not_422(
    client: TestClient, predictor: CountingPredictor
) -> None:
    response = client.post(
        "/v1/predict",
        content=b'{"text": "unterminated',
        headers={"Content-Type": "application/json"},
    )

    # The contract separates an unparseable body from a schema failure.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == MALFORMED_JSON
    assert predictor.calls == 0


def test_whitespace_is_stripped_before_the_length_bound_is_applied(
    client: TestClient,
) -> None:
    # 512 content characters plus surrounding whitespace is a valid request: the
    # bound applies after stripping.
    padded = "  " + "a" * MAX_TEXT_CHARACTERS + "  "
    accepted = client.post("/v1/predict", json={"text": padded})
    assert accepted.status_code == 200

    # 513 spaces strips to empty, so it is a min_length failure.
    empty = client.post("/v1/predict", json={"text": " " * (MAX_TEXT_CHARACTERS + 1)})
    assert empty.status_code == 422
    reasons = {detail["reason"] for detail in empty.json()["error"]["details"]}
    assert any("short" in reason for reason in reasons)


def test_error_details_never_echo_the_rejected_input(client: TestClient) -> None:
    secret = "my account number is 1234567890 and my pin is 4321"
    response = client.post("/v1/predict", json={"text": secret, "extra": secret})

    assert response.status_code == 422
    # The whole serialised body must not contain the input anywhere: not in the
    # message, not in details, not in a field name.
    assert secret not in response.text
    assert "1234567890" not in response.text


def test_error_body_shape_is_stable(client: TestClient) -> None:
    body = client.post("/v1/predict", json={"text": ""}).json()

    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id", "details"}
    assert isinstance(body["error"]["details"], list)
    for detail in body["error"]["details"]:
        assert set(detail) == {"field", "reason"}


def test_details_are_omitted_when_there_are_none(client: TestClient) -> None:
    body = client.post(
        "/v1/predict",
        content=b"not json at all",
        headers={"Content-Type": "application/json"},
    ).json()

    # `exclude_none` keeps the envelope free of a null field rather than publishing
    # `"details": null`.
    assert "details" not in body["error"]


def test_valid_client_request_id_is_echoed(client: TestClient) -> None:
    response = client.post(
        "/v1/predict",
        json={"text": "activate my card"},
        headers={REQUEST_ID_HEADER: "req_abc-123_XYZ"},
    )

    assert response.json()["request_id"] == "req_abc-123_XYZ"
    assert response.headers[REQUEST_ID_HEADER] == "req_abc-123_XYZ"


@pytest.mark.parametrize(
    "unsafe",
    [
        "has spaces",
        "has\nnewline",
        "a" * (MAX_REQUEST_ID_CHARACTERS + 1),
        "",
        "semi;colon",
        "../../etc/passwd",
    ],
)
def test_unsafe_client_request_id_is_replaced_not_rejected(
    client: TestClient, unsafe: str
) -> None:
    response = client.post(
        "/v1/predict",
        json={"text": "activate my card"},
        headers={REQUEST_ID_HEADER: unsafe},
    )

    # The header is optional, so an unusable value is replaced and the prediction
    # still succeeds.
    assert response.status_code == 200
    assert response.json()["request_id"] != unsafe
    assert is_valid_request_id(response.json()["request_id"])


def test_request_id_is_present_on_error_responses_and_headers(client: TestClient) -> None:
    response = client.post("/v1/predict", json={"text": ""})

    assert response.headers[REQUEST_ID_HEADER]
    assert response.json()["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_generated_request_ids_are_unique_and_safe() -> None:
    generated = {generate_request_id() for _ in range(200)}

    assert len(generated) == 200
    assert all(is_valid_request_id(value) for value in generated)


def test_resolve_request_id_prefers_a_valid_header() -> None:
    assert resolve_request_id("req_01") == "req_01"
    assert resolve_request_id(None) != "req_01"
    assert is_valid_request_id(resolve_request_id("not valid"))


def test_health_reports_not_ready_before_a_predictor_is_installed() -> None:
    # S06.1 ships no predictor. Until S06.2 supplies one, the service must say so
    # rather than claim readiness.
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == MODEL_NOT_READY


def test_prediction_without_a_predictor_is_503() -> None:
    response = TestClient(create_app()).post("/v1/predict", json={"text": "activate my card"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == MODEL_NOT_READY


def test_health_ready_shape(client: TestClient) -> None:
    body = client.get("/health").json()

    assert body == {
        "status": "ready",
        "model_version": "stub-artifact-0000",
        "label_count": 77,
        "device": "cpu",
    }


def test_unready_predictor_is_503_on_both_endpoints() -> None:
    app = create_app()
    set_predictor(app, CountingPredictor(ready=False))
    client = TestClient(app)

    assert client.get("/health").status_code == 503
    assert client.post("/v1/predict", json={"text": "activate my card"}).status_code == 503


def test_inference_failure_is_translated_to_a_stable_500() -> None:
    class ExplodingPredictor(CountingPredictor):
        def predict(self, text: str) -> NoReturn:
            raise RuntimeError(f"internal detail about {text} at /secret/path")

    app = create_app()
    set_predictor(app, ExplodingPredictor())
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/predict", json={"text": "activate my card"}
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PREDICTION_FAILED"
    # Neither the exception text, the input, nor the path may reach the client.
    assert "internal detail" not in response.text
    assert "/secret/path" not in response.text
    assert "activate my card" not in response.text


def test_a_predictor_contradicting_the_contract_fails_closed() -> None:
    class ContradictoryPredictor(CountingPredictor):
        def predict(self, text: str) -> StubPrediction:
            # Accepting without an intent violates a published response invariant.
            return StubPrediction(
                intent=None,
                confidence=0.9,
                threshold=0.5,
                decision="accept",
                input_truncated=False,
            )

    app = create_app()
    set_predictor(app, ContradictoryPredictor())
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/predict", json={"text": "activate my card"}
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PREDICTION_FAILED"


def test_unknown_route_and_method_use_the_same_error_envelope(client: TestClient) -> None:
    missing = client.get("/v1/nope")
    wrong_method = client.get("/v1/predict")

    for response in (missing, wrong_method):
        body = response.json()
        assert set(body) == {"error"}
        assert set(body["error"]) >= {"code", "message", "request_id"}


def test_openapi_document_builds() -> None:
    # A response_model that cannot be rendered would fail here rather than at the
    # first request in the demo.
    document = TestClient(create_app()).get("/openapi.json")

    assert document.status_code == 200
    paths = document.json()["paths"]
    assert "/health" in paths
    assert "/v1/predict" in paths


def test_predict_rejects_a_json_array_body(
    client: TestClient, predictor: CountingPredictor
) -> None:
    response = client.post("/v1/predict", content=json.dumps([1, 2, 3]).encode())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == INVALID_REQUEST
    assert predictor.calls == 0
