# Serving

`make serve` loads the single sealed transformer bundle behind typed `/health` and `/v1/predict` endpoints; `make demo` starts that same service and proves one accept and one abstain over a real socket.

**Purpose:** what startup verifies, what the two commands do differently, and which environment variables shape the listener.
**Intended reader:** operators running the service; API details live in the [API reference](../integrator/api-reference.md).

## What you'll accomplish

A verified service on `127.0.0.1:8000` answering health and prediction requests, and a demo transcript proving both decision paths. Prerequisite: a sealed transformer bundle ([Training](training.md)), or `INTENTGUARD_ARTIFACT_ROOT` pointing at one.

```bash
make serve   # serve until interrupted
make demo    # start, prove accept + abstain, terminate
```

Both reach the same entry point — `python -m intentguard.app`. `make serve` invokes it directly; `make demo` runs `scripts/demo.py`, which starts that same module as a child process. The demo therefore exercises the shipped serving path, not a private one.

## What startup verifies — before the port is bound

Startup is deliberately ordered so that a process which is *listening* is a process whose artifact was verified:

1. **Settings resolve first.** `INTENTGUARD_HOST`, `INTENTGUARD_PORT`, and `INTENTGUARD_LOG_LEVEL` are validated before anything touches disk, so a bad value fails in under a second rather than after a roughly 257 MB bundle has been loaded and re-hashed. Blank values mean "use the default". The log level must be one of `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG` (case-insensitive); `NOTSET`, `WARN`, `FATAL`, and `TRACE` are refused by design — the accepted set is the intersection of what the service logger and Uvicorn both understand, and every rejection names the variable and the accepted values.
2. **One bundle is located.** Under `<artifact root>/intentguard-distilbert/` there must be exactly one bundle directory. None → startup fails naming the path to fix. More than one → startup fails naming all candidates; serving the wrong one silently would publish predictions attributed to an artifact that did not produce them.
3. **The bundle is verified.** Every file is re-hashed against the checksum manifest; the label map is checked against the canonical 77-label contract (order included, since the order fixes the probability columns); the threshold record must exist and carry `source: "validation"` (FR-006, FR-007). Preprocessing configuration is read from the bundle's own sealed `config.json` — not from the live `configs/default.toml`, which could have been edited since sealing.
4. **The model loads locally.** Weights and tokenizer load with local files only — a bundle missing a tokenizer file fails here rather than being quietly completed from the Hugging Face Hub. The model is placed in eval mode on CPU.
5. Only then does Uvicorn bind the port. Startup logs `service_start`, then `artifact_loaded` — the second line can only appear for an artifact that passed every check.

Serving has **no code path that trains, fits, selects a threshold, or writes to the artifact**. The bundle is opened read-only.

## The listener

Defaults: `127.0.0.1:8000`, log level `INFO`. Loopback is deliberate — the service is unauthenticated, so binding every interface is opt-in (`INTENTGUARD_HOST=0.0.0.0`), never the default. The full variable table is in the [Configuration reference](../configuration.md).

`/v1/predict` is a synchronous handler on purpose: its blocking forward pass runs in the threadpool rather than on the event loop. Measured once locally with 16 concurrent predictions in flight, `/health` answered in 17 ms against 96 ms for a coroutine variant — single observations on one CPU machine, not a service level.

## Anatomy of `make demo`

The demo chooses its own ephemeral port (so a `make serve` already running is not disturbed), waits for `/health` to report ready, then sends exactly two requests:

- an in-domain request — `"How do I activate my new card?"` — expected `accept` (the recorded run answered `activate_my_card`);
- the curated unsupported row `unsupported-001` from `tests/fixtures/unsupported_requests.jsonl` — expected `abstain`, with `intent: null`. This row's abstention was measured in the U05 evaluation, which is what makes it a fair expectation rather than a guess.

It reports the confidences it observed but **asserts only the two decisions** — pinning a confidence would convert a measurement into a fixture. The child process is terminated in a `finally` block, escalating to `kill`, so no process outlives the run. A non-zero exit means one decision did not hold: that is a real observation about the loaded artifact and must not be resolved by changing the model or the threshold.

In the recorded demo run, the abstained confidence agreed with the evaluation's value for the same row to seven decimal places — serving and evaluation reading the same weights and the same threshold, observably.

## Trying it by hand

```bash
curl -s http://127.0.0.1:8000/health
curl -s -H 'Content-Type: application/json' \
  -d '{"text":"How do I activate my new card?"}' \
  http://127.0.0.1:8000/v1/predict
```

Response shapes, every error code, and the request-ID contract: [API reference](../integrator/api-reference.md).

## Next

[Interpreting results](interpreting-results.md) — what the confidences and decisions you just saw actually mean.
