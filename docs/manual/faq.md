# FAQ

Short answers to the questions this repository actually gets, each linking to the chapter that carries the full story.

**Purpose:** fast orientation for questions that don't need a whole chapter.
**Intended reader:** everyone; skimmable.

## The result

**Why does the transformer lose to the baseline? Isn't that backwards?**
It is the measured outcome of the frozen configuration — two CPU epochs at learning rate 2e-5 — and it is reported rather than retuned away, because changing anything in response to a test metric would breach the leakage controls. It is not a statement about DistilBERT's ceiling on BANKING77. The point of the repository is the honest lifecycle, and an inconvenient measured result is that lifecycle working ([Interpreting results](operator/interpreting-results.md), [LIMITATIONS.md](../LIMITATIONS.md)).

**Why not just train longer / on GPU until it wins?**
That would be tuning against a seen test result — the exact practice the pipeline forbids. A stronger transformer configuration would be a legitimate *new* experiment: new config, new run ID, new evaluation ([Extending IntentGuard](integrator/extending.md)). And CPU-only is a decision (D10), not a limitation of budget: it keeps every recorded run reproducible on the machine that validated it.

**Is 0.1684 a probability threshold? It seems very low.**
It is a point on the confidence *ranking*, not a probability. The transformer's confidence never exceeded 0.6000 on any test example, so read the threshold against that observed range. It was selected on validation data to minimise selective risk at ≥ 0.70 coverage ([Interpreting results](operator/interpreting-results.md)).

**All 12 unsupported requests abstained — so it detects out-of-domain input?**
No. That is a passed behavioral check over a fixture its author chose, meaningful only beside the in-distribution contrast (mean confidence 0.0503 on the fixture vs 0.2258 on test). Twelve hand-written rows cannot estimate OOD performance, and the repository says so wherever the number appears ([Interpreting results](operator/interpreting-results.md)).

## Running it

**Do I need a GPU?** No — nothing uses one. Training, evaluation, and serving are CPU-only by decision; no CUDA claim is evidenced anywhere ([Installation](operator/installation.md)).

**Why does `make demo` fail on a fresh clone?**
It loads a sealed bundle (roughly 257 MB) that the repository deliberately does not track. Train one (`make data && make baseline && make train`) or point `INTENTGUARD_ARTIFACT_ROOT` at an existing bundle ([Quickstart](operator/quickstart.md)).

**Why did 22 tests skip?**
Same reason — they are gated on the sealed bundle, and a skip is honest evidence of its absence ([Installation](operator/installation.md)).

**Why does `make train` finish instantly sometimes?**
A bundle with the same content-derived run ID exists, so it is reused and only the report rebuilds. Identical configuration = identical identity, by design ([Training](operator/training.md)).

**Can I run the server on my network?**
`INTENTGUARD_HOST=0.0.0.0 make serve` — but the default is loopback because the service is unauthenticated, and exposing it is your deliberate choice, not a default ([Serving](operator/serving.md), [Configuration reference](configuration.md)).

**Why was my `INTENTGUARD_LOG_LEVEL=WARN` rejected? Python accepts WARN.**
The accepted set is the *intersection* of what the service logger and Uvicorn both understand: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`. Accepting a value only one side understands would log at a level nobody asked for. It fails in under a second, before the bundle loads ([Configuration reference](configuration.md)).

## The API

**Is an abstention an error?** No — HTTP 200 with `decision: "abstain"` and `intent: null`. Abstaining is the system doing its job ([API reference](integrator/api-reference.md)).

**Why did my 513-space request get "too short"?** Bounds apply after whitespace stripping; 513 spaces is an empty request ([API reference](integrator/api-reference.md)).

**Why doesn't the error tell me what I sent?** Deliberate: no request text, exception string, path, or stack trace ever appears in an error body or a log line. The machine-readable reason travels in `details`; correlation happens via `X-Request-ID` ([API reference](integrator/api-reference.md)).

## The evidence

**Why do two identical evaluation runs differ?** Only in latency — the one section whose durations are not covered by the run ID (the protocol is; the wall-clock isn't). Every other byte of `comparison.json` reproduces ([Evaluation](operator/evaluation.md)).

**Who decides whether strict MVP passes?** `make acceptance` — an audit over all 42 primary identifiers with an enumerated verdict. Not the README, and not this FAQ ([IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md), currently **PASS**).

**Can I trust a bundle someone sends me?** Verify it first: every file is listed and SHA-256-hashed in `manifest.json`, and the loader re-verifies on every load. A bundle that fails is not the bundle its manifest describes ([Artifact format](integrator/artifact-format.md)).

## Anything else

Symptom-shaped questions: [Troubleshooting](troubleshooting.md). Term lookups: [Glossary](glossary.md). Everything authoritative: [the specification](../specification/README.md).
