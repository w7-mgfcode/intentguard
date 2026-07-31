# Interface Contract

## Decision

The only public inference interface is FastAPI. Training and evaluation remain
operator commands, not alternative inference interfaces.

## `POST /v1/predict`

### Request

```json
{
  "text": "How can I activate my new card?"
}
```

Schema:

```python
class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
```

An optional `X-Request-ID` header may be accepted when it matches the documented
safe character and length rule. Otherwise, the service generates an ID.

### Accepted response

This example illustrates the schema. Its confidence, threshold, model version,
and latency are not measured project results.

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

### Abstained response

```json
{
  "request_id": "req_02",
  "decision": "abstain",
  "intent": null,
  "confidence": 0.41,
  "threshold": 0.72,
  "input_truncated": false,
  "model_version": "example-only",
  "latency_ms": 17.9
}
```

### Response invariants

- HTTP 200 is used for both `accept` and `abstain`; abstention is an expected
  model decision, not a transport error.
- `confidence` and `threshold` are within `[0,1]`.
- `intent` is a valid label only when `decision="accept"`.
- `intent` is null when `decision="abstain"`.
- `input_truncated` is true when tokenizer truncation removed tokens beyond the
  configured maximum sequence length.
- `model_version` identifies the loaded artifact.
- `latency_ms` measures request validation plus inference and response assembly,
  not network time outside the process.

## `GET /health`

### Ready response

This is an illustrative schema, not a claim that the displayed artifact exists.

```json
{
  "status": "ready",
  "model_version": "2026-07-31T120000Z_example",
  "label_count": 77,
  "device": "cuda"
}
```

### Not-ready behavior

Startup should normally fail when artifacts are invalid. If the application is
running during a transient load state, `/health` returns HTTP 503:

```json
{
  "error": {
    "code": "MODEL_NOT_READY",
    "message": "The model bundle is not ready.",
    "request_id": "req_03"
  }
}
```

## Error schema

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "text must contain between 1 and 512 characters.",
    "request_id": "req_04",
    "details": [
      {
        "field": "text",
        "reason": "too_long"
      }
    ]
  }
}
```

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `MALFORMED_JSON` | Body is not valid JSON |
| 422 | `INVALID_REQUEST` | Typed validation failed |
| 503 | `MODEL_NOT_READY` | Artifact is not ready |
| 500 | `PREDICTION_FAILED` | Unexpected inference failure |

Internal exception strings, stack traces, filesystem paths, and raw request text
must not be returned.

## Example requests

```bash
curl -s http://127.0.0.1:8000/health
```

```bash
curl -s \
  -H 'Content-Type: application/json' \
  -d '{"text":"How do I activate my new card?"}' \
  http://127.0.0.1:8000/v1/predict
```

```bash
curl -s \
  -H 'Content-Type: application/json' \
  -d '{"text":"Recommend a hiking trail for tomorrow."}' \
  http://127.0.0.1:8000/v1/predict
```

The final command is expected to exercise abstention but must not be embedded in
an automated test that assumes a particular unmeasured model probability.
`make demo` should instead select a known low-confidence evaluation example or
temporarily use a test fixture with a deterministic predictor.
