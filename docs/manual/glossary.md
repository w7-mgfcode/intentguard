# Glossary

The product vocabulary, defined once and used consistently across this manual — with the distinctions that matter flagged where terms are easy to conflate.

**Purpose:** one authoritative lookup for IntentGuard terms.
**Intended reader:** everyone. (For the agent-workflow tooling that *built* this repository — FPAT, PIV loop, and related terms — see the separate [knowledge-base glossary](../../knowledge-base/glossary.md); the two vocabularies are deliberately distinct.)

## Core concepts

**Intent** — one of the 77 BANKING77 categories a support message can be classified into (e.g. `activate_my_card`). An accepted prediction names exactly one; an abstention names none.

**Confidence** — the maximum of the model's softmax distribution for one input. In this system it is a **ranking signal for abstention, not a probability of correctness**; both models are substantially underconfident and no recalibration is applied.

**Abstention** — the decision to answer `abstain` with `intent: null` instead of guessing, taken when confidence falls below the threshold. A successful HTTP 200 response, never an error.

**Threshold** — the single confidence value the accept/abstain decision compares against: selected once from validation predictions during `make train`, sealed into the transformer bundle, and applied unchanged by evaluation and serving. Recorded value: `0.16841767053420467`.

**Decision rule** — `accept` iff `confidence >= threshold`. One shared definition across training, evaluation, and serving, so an exactly-at-threshold confidence resolves identically everywhere.

## Selective prediction

**Coverage** — the fraction of examples the model accepts. **Minimum coverage** (`0.70`) is the floor a candidate threshold must reach on validation data to be eligible for selection.

**Accepted accuracy** — accuracy computed over accepted examples only.

**Selective risk** — `1 − accepted accuracy`: the error rate among what the model was willing to answer. The quantity the threshold selection minimises.

**Risk/coverage curve** — selective risk as a function of coverage across all candidate thresholds; the persisted threshold is one chosen point on it.

**ECE (expected calibration error)** — the gap between stated confidence and observed accuracy, here over 15 fixed equal-width bins. Large for both models, which is the quantified form of "confidence is not a probability".

## Data

**BANKING77** — the pinned public dataset: English online-banking support requests, 77 intents, source splits of 10,003 train / 3,080 test, used at exactly revision `1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`.

**Canonical splits** — the three derived splits (8,502 / 1,501 / 3,080): validation carved deterministically from source train only; test untouched.

**Split fingerprint** — a deterministic hash of one split's contents, recorded in provenance and compared across bundles before any comparison is trusted.

**Label map** — the ordered list of 77 intent names. The order fixes the meaning of every probability column, so the map is hash-checked, order included.

## Artifacts

**Bundle** — one sealed directory `artifacts/<name>/<run_id>/`: payload plus `config.json`, `labels.json`, `provenance.json`, a checksum `manifest.json`, and (transformer only) `threshold.json` and `validation_metrics.json`.

**Run ID** — the bundle's content-derived identity: `<name>-<dataset_revision[:12]>-<config_hash[:12]>`. Never wall-clock-based; identical inputs name the identical bundle. Also what the API reports as `model_version`.

**Sealed / immutable** — published atomically, never overwritten, re-hashed on every load. "Sealed" is not a metaphor: there is no code path that mutates a published bundle.

**Provenance** — the recorded facts a bundle carries about its own origin: dataset pin, split fingerprints, label-map hash, seed, dependency versions, timestamp.

**Superseded bundle** — a sibling left behind after a configuration change produced a new run ID. Evaluation and serving refuse to choose between siblings; removal is a deliberate operator act.

## Process and evidence

**Strict MVP** — the bar: every MUST capability `Implemented`, every applicable claim `Measured`. Audited, not asserted.

**Status vocabulary** — the six governance statuses: `Implemented`, `Measured`, `Partial`, `Mocked`, `Blocked`, `Planned`. Any MUST capability in the last four states fails strict MVP.

**Acceptance audit** — `make acceptance` / `scripts/validate_acceptance.py`: classifies all 42 primary identifiers against reachable evidence and prints an enumerated verdict (currently **PASS**).

**Degraded (audit)** — an audit run without evidence roots: artifact-backed rows report `not_evidenced` with reasons, separated from verdict causes. Legitimate, and reaches the same cause list as a fully-evidenced run.

**Identifier families** — the specification's traceable units: `FR-###` functional and `NFR-###` non-functional requirements, `AC-###` acceptance criteria, `US-###` user stories, `U##` umbrellas (delivery units, U01–U08), `S##.#`/`C##.#` subtasks, and decisions (`D` numbers) recorded in the specification.

**Measured (qualifier)** — a claim backed by reproducible output from the declared artifact and data — as opposed to remembered, estimated, or copied forward.

**Unsupported-request fixture** — the 12 curated rows across six declared categories used as a behavioral check of abstention. Not an OOD benchmark, and reported only beside its in-distribution contrast.

## Serving

**Predictor** — the loaded artifact behind the API: model, tokenizer, label map, threshold, and the sealed preprocessing configuration.

**`MODEL_NOT_READY`** — the 503 error code for a service without a ready predictor; rare in practice because verification happens before the port binds.

**Request ID** — the correlation token (`[A-Za-z0-9_-]{1,64}`) echoed in every response header and body and carried by every log event; invalid client values are replaced, not rejected.

**Truncation (`input_truncated`)** — whether tokenisation dropped tokens beyond the configured maximum (96); detected by a second, non-truncating tokenizer pass.

## Related

[Concepts](operator/concepts.md) explains how these fit together; [Interpreting results](operator/interpreting-results.md) covers the metric semantics in depth.
