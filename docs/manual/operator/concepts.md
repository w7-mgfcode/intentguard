# What IntentGuard is

IntentGuard is a confidence-aware support-intent classifier: it maps one short banking support message to one of 77 BANKING77 intents, or abstains when its confidence falls below a threshold it selected from validation data and sealed inside an immutable artifact.

**Purpose:** give a first-time operator the five concepts every later chapter builds on, before any command is run.
**Intended reader:** operators new to the project; integrators will also want the [glossary](../glossary.md).

## What you'll accomplish

After this chapter you can read any page of this repository — a report, a status table, an API response — and know what its vocabulary commits to. There is nothing to install yet; that starts in [Installation](installation.md).

## The task: intent classification on BANKING77

BANKING77 is a public dataset of English online-banking support requests, each labelled with one of 77 fine-grained intents (`activate_my_card`, `lost_or_stolen_card`, …). IntentGuard pins one exact dataset revision in `configs/default.toml` and never floats it, so every run, metric, and artifact names the data that produced it. The pinned source provides 10,003 training and 3,080 test examples; a validation split of 1,501 examples is carved deterministically out of the training data only ([Preparing data](data.md)).

## Two models, one honest comparison

The repository trains two classifiers over the same splits:

- a **TF-IDF logistic-regression baseline** — a lexical model, trained by `make baseline`;
- a **fine-tuned DistilBERT** — `distilbert-base-uncased` at a pinned revision, fine-tuned for two CPU epochs by `make train`.

`make evaluate` compares both on the untouched test split. The measured verdict is `baseline_better`: the baseline reaches 0.8654 macro-F1 against the transformer's 0.6620. That result is reported as measured — changing a configuration, seed, or threshold *in response to* a test metric would breach the leakage controls, so nothing was retuned after the number was seen. It reflects the frozen two-epoch CPU configuration, and is not a statement about DistilBERT's ceiling on this dataset ([LIMITATIONS.md](../../LIMITATIONS.md)).

## Confidence and abstention

Every prediction carries a confidence — the maximum of the model's softmax distribution. IntentGuard treats that confidence as a **ranking signal, not a probability of correctness**: both models are substantially underconfident, and no recalibration is applied. What makes the confidence useful is the **abstention rule**: a prediction whose confidence falls below the threshold answers `decision: "abstain"` with `intent: null` instead of guessing. Abstention is a successful response (HTTP 200), not an error.

The threshold is the spine of the system's honesty story:

1. `make train` selects it — from **validation predictions only** — by enumerating candidate thresholds, discarding any whose coverage falls below the configured minimum (0.70), and choosing the lowest selective risk (FR-004, AC-005).
2. The selected value is sealed inside the transformer's artifact bundle.
3. `make evaluate` and `make serve` load that persisted value and apply it unchanged. Serving has no code path that could select a threshold, and an artifact whose recorded threshold source is anything but `validation` is refused at load.

[Interpreting results](interpreting-results.md) covers what coverage and selective risk mean and how to read the threshold `0.1684` against the models' observed confidence ranges.

## Sealed artifacts

Training does not leave loose weight files behind; it publishes an **artifact bundle** — a directory whose every file is listed in a checksum manifest, whose identity (`run_id`) is derived from the dataset revision and configuration rather than from wall-clock time, and which is never overwritten once published. Evaluation and serving both re-verify every checksum on load, so a listening server is by construction one whose artifact passed verification. The full layout is in [Artifact format](../integrator/artifact-format.md).

## Strict MVP and the status vocabulary

Every capability in this repository carries one of six statuses — `Implemented`, `Measured`, `Partial`, `Mocked`, `Blocked`, `Planned` — and **strict MVP** requires every MUST capability to be `Implemented` with every applicable claim `Measured`. `make acceptance` audits all 42 primary identifiers (FR/NFR/AC/T families) against the evidence it can reach and prints an enumerated verdict; that script, not any sentence of prose, is the authority on the question. The current verdict and each capability's evidence live in [IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md).

## What IntentGuard is not

It is a compact portfolio project demonstrating an honest ML lifecycle end to end — not a production service. There is no authentication, no horizontal scaling story, and no operational monitoring; the server binds loopback by default for exactly that reason. The scope boundary is specified, not accidental: see [SCOPE_CONTROL.md](../../specification/docs/SCOPE_CONTROL.md).

## Next

[Installation](installation.md) — get the locked environment onto your machine.
