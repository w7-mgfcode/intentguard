"""The FastAPI boundary: validation, stable errors, request IDs (S06.1).

This module owns the HTTP contract and nothing else. It does not load a model,
tokenize, or decide — S06.2 supplies a predictor through :func:`set_predictor`, and
until one is installed every prediction answers ``MODEL_NOT_READY``. That ordering
is deliberate: the contract is testable, and provably independent of transformer
quality, before any weights exist.

Three places where framework defaults contradict `INTERFACE_CONTRACT.md` and are
overridden here:

**Malformed JSON must be 400, not 422.** FastAPI raises ``RequestValidationError``
for a body it cannot parse *and* for a body that parses but fails the schema,
reporting 422 for both. The contract separates them: ``MALFORMED_JSON`` at 400 and
``INVALID_REQUEST`` at 422. They are told apart by the error type Pydantic reports —
a JSON syntax failure carries ``type="json_invalid"``.

**The error body is an envelope, not FastAPI's ``{"detail": ...}``.** Every 4xx and
5xx answer is remapped to :class:`ErrorResponse`.

**Validation errors must not echo the input.** Pydantic's ``errors()`` include the
offending value in ``input``, and its messages can quote it. Only the field location
and a stable machine reason are copied out; the message is a fixed sentence per code.
Consequently a 422 body cannot leak the request text that produced it.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Final, Protocol

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from intentguard.logging import (
    PREDICTION_COMPLETED,
    PREDICTION_FAILED,
    PREDICTION_REJECTED,
    PredictionEvent,
    log_event,
)
from intentguard.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PredictRequest,
    PredictResponse,
    is_valid_request_id,
)

REQUEST_ID_HEADER: Final = "X-Request-ID"
REQUEST_ID_STATE_ATTRIBUTE: Final = "intentguard_request_id"

MALFORMED_JSON: Final = "MALFORMED_JSON"
INVALID_REQUEST: Final = "INVALID_REQUEST"
MODEL_NOT_READY: Final = "MODEL_NOT_READY"
PREDICTION_FAILED_CODE: Final = "PREDICTION_FAILED"

#: One fixed message per code. Building a message from the exception would risk
#: quoting the rejected input back to the client, so these are constants and the
#: variable part of a validation failure travels in ``details`` as a field path
#: plus a machine-readable reason.
ERROR_MESSAGES: Final = {
    MALFORMED_JSON: "The request body is not valid JSON.",
    INVALID_REQUEST: "The request failed validation.",
    MODEL_NOT_READY: "The model bundle is not ready.",
    PREDICTION_FAILED_CODE: "The prediction could not be completed.",
}

ERROR_STATUS: Final = {
    MALFORMED_JSON: 400,
    INVALID_REQUEST: 422,
    MODEL_NOT_READY: 503,
    PREDICTION_FAILED_CODE: 500,
}


class Prediction(Protocol):
    """What the API needs from a prediction, and nothing more."""

    @property
    def intent(self) -> str | None: ...

    @property
    def confidence(self) -> float: ...

    @property
    def threshold(self) -> float: ...

    @property
    def decision(self) -> str: ...

    @property
    def input_truncated(self) -> bool: ...


class Predictor(Protocol):
    """The seam S06.2 fills with a real loaded artifact.

    Declared structurally so the API never imports a concrete predictor. A
    deterministic test double satisfying this protocol is explicitly permitted for
    contract tests, and is `Mocked` evidence only — it can never satisfy AC-013.
    """

    @property
    def model_version(self) -> str: ...

    @property
    def label_count(self) -> int: ...

    @property
    def device(self) -> str: ...

    def is_ready(self) -> bool: ...

    def predict(self, text: str) -> Prediction: ...


def generate_request_id() -> str:
    """Generate a request ID that satisfies the documented safe-character rule."""

    return f"req_{uuid.uuid4().hex}"


def resolve_request_id(header_value: str | None) -> str:
    """Accept a well-formed client ID, otherwise generate one.

    A malformed ``X-Request-ID`` is replaced rather than rejected. The header is
    optional, so failing an otherwise-valid prediction over a correlation hint
    would be harsher than the contract implies — and an ID that fails the pattern
    is exactly the value that must not reach a log line unescaped.
    """

    if header_value is not None and is_valid_request_id(header_value):
        return header_value
    return generate_request_id()


def error_response(
    code: str,
    request_id: str,
    *,
    details: tuple[ErrorDetail, ...] | None = None,
) -> JSONResponse:
    """Build one of the four declared error responses."""

    if code not in ERROR_STATUS:
        raise ValueError(f"{code!r} is not a declared error code")
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=ERROR_MESSAGES[code],
            request_id=request_id,
            details=details,
        )
    )
    return JSONResponse(
        status_code=ERROR_STATUS[code],
        content=jsonable_encoder(body, exclude_none=True),
        headers={REQUEST_ID_HEADER: request_id},
    )


def _request_id_of(request: Request) -> str:
    """Return the ID the middleware attached, generating one if it did not run."""

    existing = getattr(request.state, REQUEST_ID_STATE_ATTRIBUTE, None)
    return existing if isinstance(existing, str) else generate_request_id()


def _validation_details(error: RequestValidationError) -> tuple[ErrorDetail, ...]:
    """Summarise a validation failure without copying the rejected value.

    ``location`` is joined from the error's ``loc`` with the leading ``body``
    dropped, so a client sees ``text`` rather than ``body.text``. ``reason`` is
    Pydantic's stable ``type`` string, never its rendered message.
    """

    details: list[ErrorDetail] = []
    for raw in error.errors():
        location = [str(part) for part in raw.get("loc", ()) if str(part) != "body"]
        details.append(
            ErrorDetail(
                field=".".join(location) or "body",
                reason=str(raw.get("type", "invalid")),
            )
        )
    return tuple(details)


def _is_malformed_json(error: RequestValidationError) -> bool:
    """Distinguish an unparseable body from a parsed body that failed the schema."""

    return any(raw.get("type") == "json_invalid" for raw in error.errors())


def create_app() -> FastAPI:
    """Build the application with its error contract and request-ID middleware.

    A factory rather than a module-level singleton, so each test gets an isolated
    application and predictor rather than inheriting whatever a previous test
    installed.
    """

    app = FastAPI(
        title="IntentGuard",
        version="0.1.0",
        # FastAPI's generated 422 body does not match the error envelope. Declaring
        # the real shape keeps the OpenAPI document honest about what clients get.
        responses={
            400: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    app.state.predictor = None

    @app.middleware("http")
    async def attach_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        setattr(request.state, REQUEST_ID_STATE_ATTRIBUTE, request_id)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id_of(request)
        malformed = _is_malformed_json(exc)
        code = MALFORMED_JSON if malformed else INVALID_REQUEST
        details = None if malformed else _validation_details(exc)
        # Rejected before any inference: the event records the category, never the
        # body that caused it.
        log_event(
            PredictionEvent(
                event=PREDICTION_REJECTED,
                request_id=request_id,
                input_characters=0,
                error_category=code,
            )
        )
        return error_response(code, request_id, details=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = _request_id_of(request)
        # Remap the framework's own errors (404, 405) into the single envelope so a
        # client never has to parse a second error shape. Anything that is not one
        # of the four declared codes is reported as a validation failure, because
        # the alternative is inventing a code the contract does not publish.
        code = INVALID_REQUEST if exc.status_code < 500 else PREDICTION_FAILED_CODE
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(
                ErrorResponse(
                    error=ErrorBody(
                        code=code,
                        message=ERROR_MESSAGES[code],
                        request_id=request_id,
                    )
                ),
                exclude_none=True,
            ),
            headers={REQUEST_ID_HEADER: request_id},
        )

    @app.get("/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
    async def health(request: Request) -> Response:
        request_id = _request_id_of(request)
        predictor: Predictor | None = app.state.predictor
        if predictor is None or not predictor.is_ready():
            return error_response(MODEL_NOT_READY, request_id)
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                HealthResponse(
                    status="ready",
                    model_version=predictor.model_version,
                    label_count=predictor.label_count,
                    device=predictor.device,
                )
            ),
            headers={REQUEST_ID_HEADER: request_id},
        )

    @app.post(
        "/v1/predict",
        response_model=PredictResponse,
        responses={
            400: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    def predict(request: Request, payload: PredictRequest) -> Response:
        # Deliberately `def` and not `async def`, which is the one place in this module
        # where that matters. `predictor.predict` is a synchronous torch forward pass of
        # several milliseconds; in a coroutine it would occupy the event loop for its
        # whole duration, serialising concurrent requests and delaying `/health` behind
        # inference. FastAPI runs a non-async handler in the threadpool instead. Nothing
        # in this body awaits, so there is nothing to give up by not being a coroutine.
        request_id = _request_id_of(request)
        predictor: Predictor | None = app.state.predictor
        if predictor is None or not predictor.is_ready():
            log_event(
                PredictionEvent(
                    event=PREDICTION_REJECTED,
                    request_id=request_id,
                    input_characters=len(payload.text),
                    error_category=MODEL_NOT_READY,
                )
            )
            return error_response(MODEL_NOT_READY, request_id)

        # This window is inference only, which is narrower than the contract's wording,
        # and the gap is stated rather than papered over. `INTERFACE_CONTRACT.md:72`
        # defines `latency_ms` as request validation plus inference plus response
        # assembly. Validation has already finished when this handler is entered, and
        # assembly cannot be included in a number that has to be passed *into* the
        # response being assembled — the value would have to exist before the work it
        # measures. So the reported figure is a lower bound on the contract's quantity,
        # and calling it validation-plus-assembly would be inventing a timing.
        started = time.perf_counter()
        try:
            outcome = predictor.predict(payload.text)
        except Exception:
            # The exception is deliberately not inspected, formatted, or logged: its
            # message could contain the request text or a filesystem path, both of
            # which the contract forbids returning.
            log_event(
                PredictionEvent(
                    event=PREDICTION_FAILED,
                    request_id=request_id,
                    input_characters=len(payload.text),
                    error_category=PREDICTION_FAILED_CODE,
                )
            )
            return error_response(PREDICTION_FAILED_CODE, request_id)
        latency_ms = (time.perf_counter() - started) * 1000.0

        try:
            body = PredictResponse(
                request_id=request_id,
                decision=outcome.decision,  # type: ignore[arg-type]
                intent=outcome.intent,
                confidence=outcome.confidence,
                threshold=outcome.threshold,
                input_truncated=outcome.input_truncated,
                model_version=predictor.model_version,
                latency_ms=latency_ms,
            )
        except ValueError:
            # The predictor produced something the published contract forbids — an
            # accepted decision with no intent, or a confidence outside [0,1]. A
            # caught server error is the honest answer; serving it would publish a
            # response contradicting the contract.
            log_event(
                PredictionEvent(
                    event=PREDICTION_FAILED,
                    request_id=request_id,
                    input_characters=len(payload.text),
                    error_category=PREDICTION_FAILED_CODE,
                )
            )
            return error_response(PREDICTION_FAILED_CODE, request_id)

        log_event(
            PredictionEvent(
                event=PREDICTION_COMPLETED,
                request_id=request_id,
                input_characters=len(payload.text),
                decision=body.decision,
                intent=body.intent,
                confidence=body.confidence,
                input_truncated=body.input_truncated,
                model_version=body.model_version,
                latency_ms=body.latency_ms,
            )
        )
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(body),
            headers={REQUEST_ID_HEADER: request_id},
        )

    return app


def set_predictor(app: FastAPI, predictor: Predictor | None) -> None:
    """Install (or clear) the predictor S06.2 will supply."""

    app.state.predictor = predictor
