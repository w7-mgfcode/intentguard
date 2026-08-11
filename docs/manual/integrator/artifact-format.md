# Artifact format

The sealed bundle: layout, manifest, checksum contract, and the three properties — content-derived identity, atomic publication, immutability — that make a loaded artifact trustworthy.

**Purpose:** enough detail to read, verify, or programmatically consume a bundle without the IntentGuard codebase.
**Intended reader:** integrators consuming artifacts; operators debugging a refused load. The design source is [ML_SYSTEM_DESIGN.md](../../specification/docs/ML_SYSTEM_DESIGN.md).

## What you'll accomplish

Given any bundle directory, you can name every file, verify every checksum by hand, and predict exactly which defects the loader will refuse.

## Layout

A bundle is one directory: `artifacts/<artifact_name>/<run_id>/`. Two artifact names exist — `intentguard-baseline` and `intentguard-distilbert` — sharing one schema (version 1):

```
artifacts/intentguard-distilbert/<run_id>/
├── manifest.json              # the checksum manifest — every other file, hashed
├── config.json                # the full configuration the bundle was built under
├── labels.json                # {"label_count": 77, "label_names": [...]} in canonical order
├── provenance.json            # dataset pin, split fingerprints, seed, dependency versions…
├── threshold.json             # transformer only: the sealed abstention threshold
├── validation_metrics.json    # transformer only: validation evidence
├── model/                     # transformer payload: weights (directory)
└── tokenizer/                 # transformer payload: tokenizer files (directory)
```

The baseline bundle has the same four required metadata files with its fitted pipeline as a file payload; `threshold.json` and `validation_metrics.json` are optional in the schema precisely so both bundle kinds load through one code path.

## The manifest

`manifest.json` lists **every file in the bundle except itself**, each with byte size and SHA-256, plus `artifact_name`, `run_id`, `schema_version`, and the payload-file list. On load, the set of files on disk must equal the manifested set exactly — a missing manifested file and an *unmanifested extra* file are both hard failures — and every hash is recomputed and compared. Payload entries must themselves be manifested.

Verify one by hand:

```bash
BUNDLE=artifacts/intentguard-distilbert/<run_id>   # path to the bundle you're verifying
python3 - "$BUNDLE" <<'EOF'
import hashlib, json, pathlib, sys
bundle = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
manifest = json.loads((bundle / "manifest.json").read_text())
for name, entry in sorted(manifest["files"].items()):
    digest = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
    print("OK " if digest == entry["sha256"] else "FAIL", name)
EOF
```

## Identity: the content-derived `run_id`

```
<artifact_name>-<dataset_revision[:12]>-<sha256(canonical(config))[:12]>
e.g. intentguard-distilbert-1fb62b1bb463-88e538757339
```

The run ID hashes the dataset revision and the configuration — never wall-clock time. Two identical runs therefore name the *same* bundle (which is what lets `make train` reuse instead of retrain), and any configuration change names a new sibling. The creation timestamp is recorded inside `provenance.json`, where it cannot poison the identity. The specification's architecture sketch described a timestamped directory; the implementation deliberately diverged, because a wall-clock identifier would contradict the determinism requirement and make the refuse-overwrite guarantee untestable.

## Required metadata contents

**`provenance.json`** — required fields, all validated at save and at every load: `artifact_name`, `run_id` (both must match the directory being loaded), `created_at`, `dataset_id`, `dataset_revision`, `label_map_hash` (must match the hash of `labels.json`'s ordered names), `split_fingerprints` (all three of `train`, `validation`, `test`), `seed`, and `dependency_versions` (a non-empty map of installed package versions). These fields are what [Evaluation](../operator/evaluation.md) compares across bundles before trusting a comparison.

**`threshold.json`** — nine required fields: `threshold`, `source`, `rule`, `rule_version`, `minimum_coverage`, `coverage`, `accepted_accuracy`, `selective_risk`, and `validation_example_count` (the writer also records `accepted_count` and `candidate_count`, which the loader does not require). Validation enforces: `source` must be `"validation"` (the leakage control at the artifact boundary — a test-selected threshold cannot be published even if some future caller computed one), `threshold` and both coverage fields in [0, 1], `coverage >= minimum_coverage`, and a positive example count. The record is re-validated **on every load**, not only at save, because the file on disk is what serving acts on.

## Lifecycle guarantees

**Atomic publication.** A bundle is staged in a hidden sibling directory and `rename`d into place only after every metadata file, the payload, and the manifest exist. An interrupted save leaves no half-written bundle visible.

**Immutability.** Saving onto an existing `artifact_name/run_id` raises; nothing in the codebase can overwrite or mutate a published bundle. Serving opens it read-only.

**Verification on every load.** `load_artifact` re-hashes every file and re-validates provenance and threshold before returning. Loading is inspection only — the artifact layer imports no model framework, so a load cannot fit or train anything.

## What the serving loader additionally refuses

Beyond `load_artifact`'s checks, the serving path ([Serving](../operator/serving.md)) refuses: an artifact directory with zero or multiple bundles (ambiguity is never resolved by guessing); a label map that is not the canonical 77 BANKING77 names *in canonical order* (the order fixes probability-column meaning — 77 right names in the wrong order would mislabel confidently); a missing or non-`validation` threshold; and a persisted training block that fails the same validators as the live TOML. Weights and tokenizer load with local files only, so an incomplete payload fails at startup rather than being silently completed from the Hugging Face Hub.

## A checksum failure is a finding

If a load reports a checksum mismatch, the bundle is not the bundle its manifest describes. Do not re-seal it to make the error go away — that would replace evidence with an assertion. Rebuild from the lifecycle instead ([Troubleshooting](../troubleshooting.md)).

## Next

[Extending IntentGuard](extending.md) — what may change safely, and what these guarantees exist to protect.
