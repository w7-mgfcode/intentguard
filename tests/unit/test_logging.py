"""Structured logs carry metadata and never raw request text (NFR-005).

The central assertion is negative: given a request containing a distinctive
string, that string must appear in no emitted log record. A negative assertion is
only as good as its bait, so the texts here are chosen to look like the sensitive
content a support classifier actually receives — card numbers, PINs, names.
"""

from __future__ import annotations

import json
import logging
from typing import NoReturn

import pytest
from fastapi.testclient import TestClient

from intentguard.api import create_app, set_predictor
from intentguard.logging import (
    DECLARED_EVENTS,
    LOGGER_NAME,
    PERMITTED_PREDICTION_FIELDS,
    PREDICTION_COMPLETED,
    PREDICTION_REJECTED,
    LoggingError,
    PredictionEvent,
    configure_logging,
    log_event,
)
from tests.contract.test_api_contract import CountingPredictor

SENSITIVE = "my card 4111111111111111 pin 9876 for Alex Morgan"


def test_declared_events_match_the_specification() -> None:
    # `PRODUCTION_READINESS.md:52-60` fixes these names; a rename would silently
    # break log-based operations.
    assert DECLARED_EVENTS == (
        "service_start",
        "artifact_loaded",
        "prediction_completed",
        "prediction_rejected",
        "prediction_failed",
        "evaluation_started",
        "evaluation_completed",
    )


def test_prediction_event_payload_uses_only_permitted_fields() -> None:
    event = PredictionEvent(
        event=PREDICTION_COMPLETED,
        request_id="req_01",
        input_characters=30,
        decision="accept",
        intent="activate_my_card",
        confidence=0.93,
        input_truncated=False,
        model_version="artifact-1",
        latency_ms=18.4,
    )

    assert set(event.payload()) <= set(PERMITTED_PREDICTION_FIELDS)


def test_prediction_event_has_no_text_field() -> None:
    # The privacy property is structural: there is no field to put text in.
    assert "text" not in PredictionEvent.__dataclass_fields__
    assert not any("text" in name for name in PredictionEvent.__dataclass_fields__)


def test_unknown_event_is_refused() -> None:
    with pytest.raises(LoggingError, match="not a declared event"):
        PredictionEvent(event="prediction_maybe", request_id="req_01", input_characters=1)


def test_intent_beside_an_abstention_is_refused() -> None:
    with pytest.raises(LoggingError, match="only for an accepted decision"):
        PredictionEvent(
            event=PREDICTION_COMPLETED,
            request_id="req_01",
            input_characters=10,
            decision="abstain",
            intent="activate_my_card",
        )


def test_invalid_decision_is_refused() -> None:
    with pytest.raises(LoggingError, match="not a valid decision"):
        PredictionEvent(
            event=PREDICTION_COMPLETED,
            request_id="req_01",
            input_characters=10,
            decision="maybe",
        )


def test_negative_input_length_is_refused() -> None:
    with pytest.raises(LoggingError, match="cannot be negative"):
        PredictionEvent(event=PREDICTION_COMPLETED, request_id="req_01", input_characters=-1)


def test_inapplicable_fields_are_omitted_rather_than_null() -> None:
    payload = PredictionEvent(
        event=PREDICTION_REJECTED,
        request_id="req_01",
        input_characters=0,
        error_category="INVALID_REQUEST",
    ).payload()

    assert payload == {
        "event": "prediction_rejected",
        "request_id": "req_01",
        "input_characters": 0,
        "error_category": "INVALID_REQUEST",
    }


def test_log_event_emits_one_parseable_json_object(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_event(
            PredictionEvent(
                event=PREDICTION_COMPLETED,
                request_id="req_01",
                input_characters=12,
                decision="abstain",
                confidence=0.4,
                input_truncated=False,
                model_version="artifact-1",
                latency_ms=9.1,
            )
        )

    assert len(caplog.records) == 1
    parsed = json.loads(caplog.records[0].getMessage())
    assert parsed["event"] == "prediction_completed"
    assert parsed["decision"] == "abstain"
    assert "intent" not in parsed


def test_configure_logging_rejects_an_unknown_level() -> None:
    with pytest.raises(LoggingError, match="not a valid log level"):
        configure_logging("CHATTY")


def test_configure_logging_sets_the_level_and_does_not_stack_handlers() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    # `configure_logging` deliberately mutates global logging state, including
    # `propagate`, which `caplog` depends on. Restore it so this test cannot alter
    # the outcome of any test that runs after it.
    original_level = logger.level
    original_handlers = list(logger.handlers)
    original_propagate = logger.propagate
    try:
        configure_logging("info")
        assert logger.level == logging.INFO

        handler_count = len(logger.handlers)
        configure_logging("warning")
        # Idempotent: a second call re-levels without adding another handler, which
        # would print every event twice.
        assert logger.level == logging.WARNING
        assert len(logger.handlers) == handler_count
    finally:
        logger.setLevel(original_level)
        logger.handlers = original_handlers
        logger.propagate = original_propagate


def test_accepted_prediction_logs_metadata_but_not_the_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app()
    set_predictor(app, CountingPredictor(confidence=0.9))

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        TestClient(app).post("/v1/predict", json={"text": SENSITIVE})

    combined = " ".join(record.getMessage() for record in caplog.records)
    assert SENSITIVE not in combined
    assert "4111111111111111" not in combined
    assert "Alex Morgan" not in combined

    parsed = json.loads(caplog.records[-1].getMessage())
    assert parsed["event"] == "prediction_completed"
    assert parsed["input_characters"] == len(SENSITIVE)
    assert parsed["decision"] == "accept"
    assert parsed["intent"] == "activate_my_card"
    assert parsed["model_version"] == "stub-artifact-0000"
    assert parsed["latency_ms"] >= 0.0


def test_abstained_prediction_logs_no_intent(caplog: pytest.LogCaptureFixture) -> None:
    app = create_app()
    set_predictor(app, CountingPredictor(confidence=0.05))

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        TestClient(app).post("/v1/predict", json={"text": SENSITIVE})

    parsed = json.loads(caplog.records[-1].getMessage())
    assert parsed["decision"] == "abstain"
    assert "intent" not in parsed
    assert SENSITIVE not in caplog.records[-1].getMessage()


def test_rejected_request_logs_a_category_and_not_the_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app()
    set_predictor(app, CountingPredictor())

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        TestClient(app).post("/v1/predict", json={"text": SENSITIVE, "extra": SENSITIVE})

    combined = " ".join(record.getMessage() for record in caplog.records)
    assert SENSITIVE not in combined
    parsed = json.loads(caplog.records[-1].getMessage())
    assert parsed["event"] == "prediction_rejected"
    assert parsed["error_category"] == "INVALID_REQUEST"


def test_failed_prediction_logs_a_category_and_not_the_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ExplodingPredictor(CountingPredictor):
        def predict(self, text: str) -> NoReturn:
            raise RuntimeError(f"boom on {text} at /secret/path")

    app = create_app()
    set_predictor(app, ExplodingPredictor())

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        TestClient(app, raise_server_exceptions=False).post(
            "/v1/predict", json={"text": SENSITIVE}
        )

    combined = " ".join(record.getMessage() for record in caplog.records)
    assert SENSITIVE not in combined
    assert "/secret/path" not in combined
    assert "boom" not in combined
    parsed = json.loads(caplog.records[-1].getMessage())
    assert parsed["event"] == "prediction_failed"
    assert parsed["error_category"] == "PREDICTION_FAILED"


def test_every_emitted_record_is_valid_json(caplog: pytest.LogCaptureFixture) -> None:
    app = create_app()
    set_predictor(app, CountingPredictor())
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        client.post("/v1/predict", json={"text": "activate my card"})
        client.post("/v1/predict", json={"text": ""})

    assert caplog.records
    for record in caplog.records:
        json.loads(record.getMessage())
