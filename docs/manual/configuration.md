# Configuration reference

Every field of `configs/default.toml` and every `INTENTGUARD_*` environment variable: type, constraint, default, and which command reads it.

**Purpose:** the single lookup table for configuration — including the validation each value passes and the one declared variable nothing currently reads.
**Intended reader:** operators and integrators; both tracks link here rather than restating values.

## The two configuration surfaces

**`configs/default.toml`** — the reviewed defaults: dataset and model pins, hyperparameters, threshold policy, output roots. Loaded through typed validators that reject wrong types, out-of-range values (including NaN/infinity), and non-allow-listed choices, each with a named field in the error. Changing these is a reviewed change to a tracked file ([Extending IntentGuard](integrator/extending.md)).

**Environment variables** — per-machine, per-run settings: where to listen, how loudly to log, where artifacts live. `.env.example` is the tracked schema; real values are never committed.

A third surface outranks the TOML for one consumer: **serving reads preprocessing from the bundle's own sealed `config.json`**, not from the live TOML, so editing `[training]` after sealing changes future training runs — never how an existing bundle tokenises ([Artifact format](integrator/artifact-format.md)).

## `configs/default.toml`

### `[project]`

| Field | Default | Constraint | Meaning |
|---|---|---|---|
| `name` | `"intentguard"` | string | project identifier |
| `seed` | `42` | integer | the seed behind the validation carve-out and other deterministic choices; recorded in provenance |

### `[data]`

| Field | Default | Constraint | Meaning |
|---|---|---|---|
| `dataset_id` | `"PolyAI/banking77"` | **must equal the constant in code** | the approved dataset (U02) |
| `dataset_revision` | `1fb62b1bb463…` | **must equal the constant in code** | the immutable pin |
| `validation_fraction` | `0.15` | 0 < x < 1 | share of source train carved into validation |

The two pins are cross-checked against constants in `src/intentguard/config.py`; an edited TOML naming any other source is refused at load. The same applies to `[model]`.

### `[baseline]` — the TF-IDF logistic regression (U03)

| Field | Default | Constraint |
|---|---|---|
| `lowercase` | `true` | boolean |
| `ngram_min` / `ngram_max` | `1` / `2` | positive integers, `min <= max` |
| `max_features` | `50000` | positive integer |
| `min_df` | `1` | positive integer |
| `sublinear_tf` | `true` | boolean |
| `solver` | `"lbfgs"` | allow-list: `lbfgs`, `saga` |
| `regularization_c` | `1.0` | positive finite float |
| `max_iter` | `1000` | positive integer |
| `class_weight` | `"balanced"` | allow-list: `balanced`, `none` (mapped to scikit-learn's `None`) |

### `[model]`

| Field | Default | Constraint |
|---|---|---|
| `base_model_id` | `"distilbert/distilbert-base-uncased"` | **must equal the constant in code** |
| `base_model_revision` | `12040accade4…` | **must equal the constant in code** |

### `[training]` — the DistilBERT fine-tune (U04)

| Field | Default | Constraint |
|---|---|---|
| `max_sequence_length` | `96` | positive integer; also drives the served `input_truncated` check |
| `threshold_source` | `"validation"` | allow-list of one — the leakage control as configuration |
| `epochs` | `2` | positive integer |
| `train_batch_size` / `eval_batch_size` | `16` / `32` | positive integers |
| `learning_rate` | `2e-5` | positive finite float |
| `weight_decay` | `0.01` | non-negative finite float (zero is legitimate) |
| `warmup_ratio` | `0.1` | finite, `0.0 <= x < 1.0` (no warmup is legitimate) |
| `max_grad_norm` | `1.0` | positive finite float |
| `selection_metric` | `"validation_macro_f1"` | allow-list of one |

This exact block is sealed into every transformer bundle and re-validated through the same functions when a bundle is loaded — a hand-edited bundle claiming `threshold_source = "test"` is refused.

### `[threshold]`

| Field | Default | Constraint | Meaning |
|---|---|---|---|
| `minimum_coverage` | `0.70` | 0 < x < 1 | candidates below this validation coverage are ineligible |
| `objective` | `"selective_risk"` | allow-list of one | the quantity minimised among eligible candidates |

### `[paths]`

| Field | Default | Meaning |
|---|---|---|
| `data_root` | `"data"` | dataset cache + provenance |
| `artifact_root` | `"artifacts"` | sealed bundles (overridable per-process by `INTENTGUARD_ARTIFACT_ROOT`) |
| `report_root` | `"reports"` | generated evidence |

### `[status]`

`allowed` must be exactly the six-status governance vocabulary — `Implemented`, `Measured`, `Partial`, `Mocked`, `Blocked`, `Planned` — or loading fails. It exists so the vocabulary is data the validators can hold the repository to, not prose.

## Environment variables

| Variable | Default | Read by | Constraint |
|---|---|---|---|
| `INTENTGUARD_HOST` | `127.0.0.1` | `make serve` / `make demo` (the app entry point) | any host string; loopback by default because the service is unauthenticated |
| `INTENTGUARD_PORT` | `8000` | same | integer 1–65535; port 0 is rejected (it would bind an address the operator cannot know) |
| `INTENTGUARD_LOG_LEVEL` | `INFO` | same | one of `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`, case-insensitive. `NOTSET`, `WARN`, `FATAL`, `TRACE` are refused — the accepted set is the intersection of what the service logger and Uvicorn both understand. Validated before the bundle loads, so a bad value fails in under a second |
| `INTENTGUARD_ARTIFACT_ROOT` | `[paths].artifact_root` | serving, demo, evaluation, acceptance audit | path to the root holding sealed bundles; blank or whitespace-only means unset; `~` is expanded |
| `INTENTGUARD_REPORT_ROOT` | `[paths].report_root`, or `<artifact root>/../reports` when only the artifact root is redirected | acceptance audit | where the audit looks for generated reports ([CI integration](integrator/ci-integration.md)) |
| `INTENTGUARD_DEVICE` | `auto` (declared) | **nothing, currently** | declared in `.env.example`, but no code path reads it: the device is fixed to CPU by decision D10, so setting this variable has no effect today. Recorded here so the discrepancy is visible rather than discovered |

Blank values are treated as unset everywhere — a shell that exports a variable without a value gets the default, not an empty host or a crash from `int("")`.

## Precedence, summarised

1. Sealed bundle `config.json` — how an existing artifact behaves (preprocessing, threshold). Immutable.
2. Environment variables — where this process listens, logs, and finds artifacts.
3. `configs/default.toml` — everything else, and the input to any *future* training run.

## Related

[Serving](operator/serving.md) · [Training](operator/training.md) · [Troubleshooting](troubleshooting.md)
