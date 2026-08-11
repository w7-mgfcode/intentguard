# Troubleshooting

Symptom → cause → fix, for every failure mode this manual's commands can produce — and the five stop points where the correct fix is to *stop*.

**Purpose:** resolve the failure you are looking at without breaking an evidence guarantee on the way.
**Intended reader:** operators and integrators mid-incident. The terse authority for operating rules is [OPERATIONS.md](../OPERATIONS.md).

## First: is this a stop point?

Five conditions are findings, not obstacles. Working around them destroys exactly the property the system exists to demonstrate:

| Stop point | Why you must not work around it |
|---|---|
| Two bundles under one artifact directory | attributing metrics to the wrong configuration is worse than failing; remove the superseded bundle deliberately |
| A provenance disagreement between bundles or splits | comparing models trained on different data yields a number that resembles a comparison but is not one |
| A demo decision that does not hold | a real observation about the loaded artifact — never resolved by changing the model or threshold |
| A rejected `INTENTGUARD_LOG_LEVEL` | the rejection names the accepted set and fires before the bundle loads; fix the value |
| A checksum failure on load | the bundle is not the bundle its manifest describes; **never re-seal it** — rebuild through the lifecycle |

## Setup and environment

**`make setup` fails resolving packages** — the environment must install from `uv.lock` exactly (`--locked`). Check `uv` is current and the network reachable; do not regenerate the lock to make it pass — that changes the environment every recorded run describes.

**`make test`: 22 tests skip** — expected without a sealed transformer bundle; they are the integration tests gated on it. Train one ([Training](operator/training.md)) or set `INTENTGUARD_ARTIFACT_ROOT`. On clean CI runners, 39 skips (22 + 17 gated on the Hugging Face cache) is the recorded, correct count ([CI integration](integrator/ci-integration.md)).

## Data

**`make data` fails wanting network** — the first run downloads the pinned BANKING77 revision; later runs use the local cache. Behind a proxy, allow the download once, or copy a cache from a machine that has one.

**Dataset or label validation fails** — the pins in `configs/default.toml` are cross-checked in code, and the 77-label map must match the canonical names in order. If you edited the pins, that is the refusal working ([Configuration reference](configuration.md)).

## Training and artifacts

**`make train` seems to do nothing** — a bundle with the same content-derived run ID already exists; it is reused and only the report is rebuilt. Intended ([Training](operator/training.md)). To force a genuinely new run, change configuration (new run ID) — and then deal with the sibling-bundle rule below.

**`make evaluate`: names two bundles and stops** — a superseded bundle sits beside the current one (typically after a config change). Remove the stale `artifacts/<name>/<run_id>/` directory by hand; nothing removes it for you. Stop point: pick deliberately, using each bundle's `config.json` and `provenance.json` to identify the current one.

**`make evaluate`: provenance disagreement** — the bundles, or a bundle and the local splits, disagree on dataset revision, label-map hash, split fingerprints, or test example IDs. Usual cause: artifacts trained before a data change, evaluated after. Rebuild the out-of-date side; do not edit provenance.

**`make evaluate`: fixture error** — the curated fixture is missing, malformed (schema: `request_id`, `text`, `category` ∈ the six declared, `rationale`), or a row collides with a BANKING77 split. Authoring error — fix the fixture ([Extending IntentGuard](integrator/extending.md)).

**`ArtifactError: … already exists and is immutable`** — you attempted to write onto a published `artifact_name/run_id`. Never delete the existing bundle to let a writer through unless you have established it is superseded; identical configuration reproduces the identical run ID on purpose.

**Checksum mismatch on load** — stop point. The bundle changed after sealing (partial copy, disk fault, manual edit). Rebuild via `make train`; treat the mismatch as the finding it is.

## Serving and demo

**Startup fails before binding: settings error** — the message names the variable and its accepted values ([Configuration reference](configuration.md)). By design this fires in under a second, before the roughly 257 MB bundle is touched.

**Startup fails: `No intentguard-distilbert artifact directory exists…`** — no bundle under the resolved artifact root. Train one, or point `INTENTGUARD_ARTIFACT_ROOT` at the root that has one. Check which root the process resolved: an exported-but-empty variable counts as unset.

**Startup fails: multiple bundles** — the single-bundle rule, at serving. Same fix as the evaluate case above.

**`/health` answers 503 `MODEL_NOT_READY`** — rare by construction (verification happens before the port binds). If you built the app programmatically without installing a predictor, that is the cause; through `make serve`, treat it as a bug worth reporting rather than restarting past.

**`make demo` exits non-zero on a decision** — stop point. The in-domain request did not accept, or `unsupported-001` did not abstain, against the loaded artifact. Verify which artifact was loaded (the transcript's `model_version` names the run ID) before concluding anything.

**Port already in use** — `make serve` binds `127.0.0.1:8000` by default; another process holds it. Set `INTENTGUARD_PORT`, or find the stale process. `make demo` is immune — it picks an ephemeral port precisely so an abandoned server cannot make the next run fail mysteriously.

**Client gets 422 unexpectedly** — the request bounds apply after whitespace stripping, unknown fields are rejected, and control characters (other than tab/newline/CR) are refused. The `details` array names each field and machine reason ([API reference](integrator/api-reference.md)).

## Acceptance audit

**`make acceptance` exits non-zero** — the gate speaking, not a broken command. Read the enumerated causes; each names an identifier and its gap. Note the layering when quoting: the script exits 1, `make` reports `Error 1` and exits 2.

**Rows report `not_evidenced`** — the audit cannot reach sealed bundles or reports from where it ran. Degraded mode is legitimate and reported separately from verdict causes; to audit real evidence, set both roots and prefer `--print-only` ([CI integration](integrator/ci-integration.md)).

## Related

[FAQ](faq.md) · [OPERATIONS.md](../OPERATIONS.md) · [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md)
