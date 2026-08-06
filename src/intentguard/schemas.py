"""Typed records for the BANKING77 data contract and the public API boundary.

Two concerns share this module because `docs/backlog/TRACEABILITY.md` names it as
the primary owner of NFR-004 while it already owns the dataset records. Splitting
it would move an identifier's primary owner, which `AGENTS.md` forbids doing as a
side effect of an unrelated change. The dataset records are frozen dataclasses; the
API models are Pydantic, because only the API boundary needs runtime validation.

The API models encode `INTERFACE_CONTRACT.md` exactly, including the parts that are
easy to get subtly wrong:

* ``text`` is bounded **after** whitespace stripping, so 513 spaces is an empty
  request rather than an oversized one.
* ``extra="forbid"`` makes an unknown field a 422 rather than something silently
  ignored — NFR-004 requires rejection.
* Abstention is a *successful* response. ``intent`` is null exactly when
  ``decision="abstain"``, and that coupling is validated here rather than trusted
  to the caller, so a predictor bug cannot produce a response that contradicts the
  published contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

SplitName = Literal["train", "validation", "test"]

MAX_TEXT_CHARACTERS: Final = 512
MAX_REQUEST_ID_CHARACTERS: Final = 64

#: The request-ID rule `INTERFACE_CONTRACT.md:26` refers to but never spells out.
#: Restricted to characters that are safe to place in a log line unescaped, which
#: is the whole reason the header is accepted at all. The length bound is
#: interpolated from the constant above so the two cannot drift apart.
REQUEST_ID_PATTERN: Final = re.compile(
    rf"\A[A-Za-z0-9_-]{{1,{MAX_REQUEST_ID_CHARACTERS}}}\Z"
)

#: C0 and C1 control characters, excluding tab, newline, and carriage return.
#: Those three are ordinary in pasted support text; the rest arrive from encoding
#: errors or injection attempts and would corrupt a log line.
_FORBIDDEN_CONTROL_CHARACTERS: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def is_valid_request_id(candidate: str) -> bool:
    """Return whether a client-supplied request ID may be echoed back and logged."""

    return REQUEST_ID_PATTERN.match(candidate) is not None


@dataclass(frozen=True, slots=True)
class CanonicalExample:
    """One validated example with a stable upstream-derived identity."""

    example_id: str
    text: str
    label_id: int
    label_name: str
    split: SplitName


@dataclass(frozen=True, slots=True)
class PreparedDataset:
    """Validated canonical splits and deterministic provenance."""

    train: tuple[CanonicalExample, ...]
    validation: tuple[CanonicalExample, ...]
    test: tuple[CanonicalExample, ...]
    label_names: tuple[str, ...]
    provenance: dict[str, object]


class PredictRequest(BaseModel):
    """The only accepted request body for ``POST /v1/predict``.

    Field order matters for the error contract: Pydantic reports ``extra="forbid"``
    violations alongside length violations, and both map to ``INVALID_REQUEST``, so
    a request that is both oversized and carries an unknown field yields one 422
    listing both rather than a status that depends on validation order.
    """

    model_config = ConfigDict(extra="forbid")

    text: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=MAX_TEXT_CHARACTERS,
        ),
    ]

    @model_validator(mode="after")
    def _reject_control_characters(self) -> Self:
        """Reject control characters that would corrupt a structured log line.

        Applied after stripping, so a request whose only content is a control
        character has already failed the length bound and reports the clearer
        error.
        """

        if _FORBIDDEN_CONTROL_CHARACTERS.search(self.text):
            raise ValueError("text must not contain control characters")
        return self


class PredictResponse(BaseModel):
    """A successful prediction: HTTP 200 for both accept and abstain."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    decision: Literal["accept", "abstain"]
    intent: str | None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    threshold: Annotated[float, Field(ge=0.0, le=1.0)]
    input_truncated: bool
    model_version: str
    latency_ms: Annotated[float, Field(ge=0.0)]

    @model_validator(mode="after")
    def _require_intent_to_match_decision(self) -> Self:
        """Enforce the response invariant that couples ``intent`` to ``decision``.

        `INTERFACE_CONTRACT.md` states both halves: an intent is a valid label only
        when accepting, and null when abstaining. Validating it on the way out means
        a predictor defect surfaces as a caught server error rather than as a
        published response that contradicts the documented contract.
        """

        if self.decision == "accept" and self.intent is None:
            raise ValueError("an accepted prediction must name an intent")
        if self.decision == "abstain" and self.intent is not None:
            raise ValueError("an abstained prediction must not name an intent")
        return self


class HealthResponse(BaseModel):
    """The ready response for ``GET /health``.

    Only ``status="ready"`` is representable. A not-ready service answers with the
    error envelope and HTTP 503, so this model cannot be used to describe a
    degraded state — `ARCHITECTURE.md:110` requires that `/health` never report
    ready for an incomplete artifact, and the type system enforces it here.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"]
    model_version: str
    label_count: Annotated[int, Field(ge=1)]
    device: str


class ErrorDetail(BaseModel):
    """One field-level reason inside an error body."""

    model_config = ConfigDict(extra="forbid")

    field: str
    reason: str


class ErrorBody(BaseModel):
    """The error envelope's contents."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str
    details: tuple[ErrorDetail, ...] | None = None


class ErrorResponse(BaseModel):
    """The single error shape for every 4xx and 5xx response.

    One envelope for all failures means a client parses one shape. Internal
    exception strings, stack traces, filesystem paths, and raw request text are
    excluded by the API layer that builds ``message``; this model only fixes the
    structure.
    """

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
