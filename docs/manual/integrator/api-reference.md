# API reference

The complete HTTP surface: two endpoints, one error envelope, and the request-ID contract — with the exact validation rules a client will hit.

**Purpose:** everything needed to write a correct client, including the edge cases.
**Intended reader:** integrators calling the service. The authoritative contract is [INTERFACE_CONTRACT.md](../../specification/docs/INTERFACE_CONTRACT.md); this chapter documents the implemented behavior, which encodes that contract and names the one place it is deliberately narrower.

## What you'll accomplish

A working client that handles both decisions, all four error codes, and request correlation. Prerequisite: a running service ([Serving](../operator/serving.md)) at `http://127.0.0.1:8000` (defaults).

The service is FastAPI; its generated OpenAPI document and interactive docs are served at `/openapi.json` and `/docs`, and the declared response models there match the envelope below — including the error shapes, which are declared explicitly so the OpenAPI document stays honest.

## `POST /v1/predict`

### Request

```bash
curl -s -H 'Content-Type: application/json' \
  -d '{"text":"How do I activate my new card?"}' \
  http://127.0.0.1:8000/v1/predict
```

One JSON object with exactly one field:

| Field | Type | Rule |
|---|---|---|
| `text` | string | 1–512 characters **after** leading/trailing whitespace is stripped; no C0/C1 control characters (tab, newline, carriage return are allowed) |

Validation details that bite in practice:

- **Bounds apply post-strip.** 513 spaces is an *empty* request (too short), not an oversized one.
- **Unknown fields are rejected** (`extra="forbid"`) with a 422, never silently ignored (NFR-004).
- **Control characters** other than tab/newline/CR yield a 422 — they arrive from encoding errors or injection attempts and would corrupt a structured log line.
- A request that violates several rules at once gets **one 422 listing every violation** in `details`, independent of validation order.

### Response — HTTP 200 for both decisions

Abstention is a successful response, not an error:

```json
{
  "request_id": "req_01",
  "decision": "accept",
  "intent": "activate_my_card",
  "confidence": 0.93,
  "threshold": 0.72,
  "input_truncated": false,
  "model_version": "example-only",
  "latency_ms": 18.4
}
```

(Field values above are illustrative, per the interface contract — not measured project results.)

| Field | Type | Meaning |
|---|---|---|
| `request_id` | string | echo of a valid `X-Request-ID`, else server-generated |
| `decision` | `"accept"` \| `"abstain"` | the abstention rule's outcome: accept iff `confidence >= threshold` |
| `intent` | string \| null | a valid BANKING77 label when accepting; **always `null` when abstaining** |
| `confidence` | number ∈ [0,1] | max of the model's softmax — a ranking signal, not a probability of correctness ([Interpreting results](../operator/interpreting-results.md)) |
| `threshold` | number ∈ [0,1] | the persisted validation-selected threshold, unchanged per artifact |
| `input_truncated` | boolean | true when tokenisation dropped tokens beyond the configured maximum (96); determined by a second, non-truncating tokenizer pass, because a truncating encode cannot tell one dropped token from four hundred |
| `model_version` | string | the loaded bundle's content-derived run ID, e.g. `intentguard-distilbert-1fb62b1bb463-88e538757339` |
| `latency_ms` | number ≥ 0 | the inference window inside the handler. The contract defines validation + inference + assembly; validation has finished before the handler starts, and assembly cannot be included in a number passed *into* the response being assembled — so the reported figure is a stated lower bound on the contract's quantity, not an invented wider timing |

The `intent`↔`decision` coupling is validated on the way out: a predictor defect that produced an accepted decision with no intent (or the reverse) surfaces as a 500, never as a published response contradicting the contract.

## `GET /health`

```bash
curl -s http://127.0.0.1:8000/health
```

Ready — HTTP 200:

```json
{ "status": "ready", "model_version": "…run id…", "label_count": 77, "device": "cpu" }
```

`status: "ready"` is the only representable value of this model — a not-ready service answers with the error envelope at 503 (`MODEL_NOT_READY`) instead. `/health` can never report ready for an incomplete artifact; readiness is re-checked per request (label map intact, threshold present and in range, model in eval mode), not cached as a constant. In normal operation you will rarely see the 503: an invalid artifact fails startup before the port is bound ([Serving](../operator/serving.md)).

## Errors — one envelope, four codes

Every 4xx and 5xx response, including the framework's own 404/405, is remapped into one shape, so a client parses exactly one error structure:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request failed validation.",
    "request_id": "req_04",
    "details": [ { "field": "text", "reason": "string_too_long" } ]
  }
}
```

| HTTP | `code` | When |
|---:|---|---|
| 400 | `MALFORMED_JSON` | body is not parseable JSON (told apart from schema failures by the parser's error type) |
| 422 | `INVALID_REQUEST` | parsed body failed validation; also the code carried by remapped 404/405 |
| 503 | `MODEL_NOT_READY` | no predictor installed, or readiness check failed |
| 500 | `PREDICTION_FAILED` | inference raised, or the predictor produced a contract-violating outcome |

Guarantees a client can rely on:

- `message` is a **fixed sentence per code** — the variable part travels in `details` as a field path plus Pydantic's stable machine reason (`string_too_long`, `extra_forbidden`, …), never a rendered message.
- **The rejected input is never echoed.** No internal exception string, stack trace, filesystem path, or request text appears in any error body — the failure path deliberately does not inspect or format the exception.
- `details` is present only for 422 schema failures.

## Request correlation: `X-Request-ID`

Send an optional `X-Request-ID` header matching `[A-Za-z0-9_-]{1,64}`. A valid ID is echoed in the response header always, and in the response body for `PredictResponse` and `ErrorResponse`. `HealthResponse` (the 200 body of `/health`) has no `request_id` field — `/health` guarantees only the `X-Request-ID` header. All IDs are used in the service's structured log events. An **invalid ID is replaced, not rejected** — the header is a correlation hint, and an ID that fails the pattern is exactly the value that must not reach a log line unescaped. Server-generated IDs have the form `req_<32 hex>`. Every response, success or error, carries the `X-Request-ID` header.

## Logging, from a client's perspective

The service logs structured events (`prediction_completed`, `prediction_rejected`, `prediction_failed`) that include the request ID, decision, confidence, and input *length* — never the input text. If you need to correlate a client-side failure with server logs, the request ID is the join key.

## Next

[Code architecture](code-architecture.md) — where each of these behaviors lives in `src/intentguard/`.
