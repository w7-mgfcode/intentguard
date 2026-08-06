"""Structured serving logs that cannot carry raw request text (NFR-005).

`PRODUCTION_READINESS.md:50-77` fixes both the event vocabulary and the field list.
Both are encoded here as constants and enforced at construction, because the
privacy property this module exists for is not something a caller can be trusted
to remember at every call site.

The design decision worth stating: **raw text never enters a log record, not even
to be stripped later.** A sanitiser that removes text after it has been formatted
is one refactor away from leaking, and a redaction helper that takes the text as an
argument has already put it in the caller's stack frame. So :class:`PredictionEvent`
has no text field at all. It carries ``input_characters`` — a length — and that is
the only thing about the request body a log line can say.

The one field that looks like text and is not: ``intent``. It is a BANKING77 label
name drawn from the artifact's own label list, never anything a client sent, and it
is present only when the decision was ``accept``.

`AGENTS.md` requires "ordinary structured logging". This module therefore emits
JSON through the standard library's `logging` and adds no dependency, no handler
registry, and no metrics exporter.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Final

LOGGER_NAME: Final = "intentguard"

#: Required verbatim by `PRODUCTION_READINESS.md:52-60`. `evaluation_started` and
#: `evaluation_completed` belong to the offline evaluation command rather than to
#: serving; they are listed here so the vocabulary stays in one place and a future
#: evaluation log cannot invent a near-miss spelling of an existing event.
SERVICE_START: Final = "service_start"
ARTIFACT_LOADED: Final = "artifact_loaded"
PREDICTION_COMPLETED: Final = "prediction_completed"
PREDICTION_REJECTED: Final = "prediction_rejected"
PREDICTION_FAILED: Final = "prediction_failed"
EVALUATION_STARTED: Final = "evaluation_started"
EVALUATION_COMPLETED: Final = "evaluation_completed"

DECLARED_EVENTS: Final = (
    SERVICE_START,
    ARTIFACT_LOADED,
    PREDICTION_COMPLETED,
    PREDICTION_REJECTED,
    PREDICTION_FAILED,
    EVALUATION_STARTED,
    EVALUATION_COMPLETED,
)

#: The fields `PRODUCTION_READINESS.md:64-77` permits in a prediction log. Raw
#: request text is absent by construction, not by filtering.
PERMITTED_PREDICTION_FIELDS: Final = (
    "event",
    "request_id",
    "input_characters",
    "decision",
    "intent",
    "confidence",
    "input_truncated",
    "model_version",
    "latency_ms",
    "error_category",
)


class LoggingError(ValueError):
    """Raised when a log event would violate the declared logging contract."""


@dataclass(frozen=True, slots=True)
class PredictionEvent:
    """One serving event, structurally incapable of holding request text.

    ``intent`` is a label name from the loaded artifact and is permitted only
    alongside ``decision="accept"``; an abstained request has no intent to name.
    ``error_category`` is a stable category string such as ``INVALID_REQUEST`` —
    never an exception message, which could quote the offending input back into the
    log and defeat the whole point of this class.
    """

    event: str
    request_id: str
    input_characters: int
    decision: str | None = None
    intent: str | None = None
    confidence: float | None = None
    input_truncated: bool | None = None
    model_version: str | None = None
    latency_ms: float | None = None
    error_category: str | None = None

    def __post_init__(self) -> None:
        if self.event not in DECLARED_EVENTS:
            raise LoggingError(f"{self.event!r} is not a declared event")
        if self.input_characters < 0:
            raise LoggingError("input_characters cannot be negative")
        if self.decision is not None and self.decision not in ("accept", "abstain"):
            raise LoggingError(f"{self.decision!r} is not a valid decision")
        # An intent beside an abstention would contradict the response contract in
        # the log, so a reader reconciling logs against responses would see a
        # disagreement that never happened on the wire.
        if self.intent is not None and self.decision != "accept":
            raise LoggingError("intent may be logged only for an accepted decision")

    def payload(self) -> dict[str, object]:
        """Render the event, omitting fields that do not apply to it."""

        candidate: dict[str, object | None] = {
            "event": self.event,
            "request_id": self.request_id,
            "input_characters": self.input_characters,
            "decision": self.decision,
            "intent": self.intent,
            "confidence": self.confidence,
            "input_truncated": self.input_truncated,
            "model_version": self.model_version,
            "latency_ms": self.latency_ms,
            "error_category": self.error_category,
        }
        return {key: value for key, value in candidate.items() if value is not None}


def get_logger() -> logging.Logger:
    """Return the service logger.

    No handler or level is configured here. Configuring logging is the
    application entry point's job, and a library that mutates global logging
    state on import surprises every test that captures records.
    """

    return logging.getLogger(LOGGER_NAME)


def configure_logging(level: str) -> None:
    """Configure the service logger once, at application startup.

    The service logger is configured directly rather than through
    `logging.basicConfig`, which does nothing at all when the root logger already
    has a handler. Under any host that configured logging first — Uvicorn, pytest —
    `basicConfig` would silently leave the level untouched and the operator would
    get a quieter service than they asked for, with no error to explain it.

    Idempotent: a repeated call updates the level without stacking another handler
    and duplicating every line.
    """

    resolved = logging.getLevelName(level.upper())
    if not isinstance(resolved, int):
        raise LoggingError(f"{level!r} is not a valid log level")

    logger = get_logger()
    logger.setLevel(resolved)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    # Records are emitted by this logger's own handler; propagating would also hand
    # them to the root logger and print each event twice under Uvicorn.
    logger.propagate = False


def log_event(event: PredictionEvent, *, level: int = logging.INFO) -> None:
    """Emit one event as a single JSON object.

    ``sort_keys`` is deliberate: a stable key order makes two log lines from
    different runs diffable, which matters when the demo transcript is the
    evidence for AC-013.
    """

    get_logger().log(level, json.dumps(event.payload(), sort_keys=True))
