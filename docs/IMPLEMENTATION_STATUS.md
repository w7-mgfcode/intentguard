# Implementation status

Status uses the repository vocabulary in `AGENTS.md`. `Measured` is an evidence qualifier and never substitutes for implementation.

| Umbrella | Capability | Status | Evidence |
|---|---|---|---|
| U01 | Project foundation and reproducibility | Implemented | Gate A local checks pass; CPU validation passed for `main` commit `1495776` ([run 30853223606](https://github.com/w7-mgfcode/intentguard/actions/runs/30853223606)) |
| U02 | BANKING77 data contract | Implemented | `make data` validated `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`: source 10,003/3,080, derived 8,502/1,501/3,080, 77 labels, deterministic fingerprints, and local provenance. |
| U03 | TF-IDF logistic-regression baseline | Implemented | `make baseline` produced run `intentguard-baseline-1fb62b1bb463-059ee4b12214` on `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`, measured from the reloaded artifact: test accuracy 0.8653, macro-F1 0.8654, 3,080 examples across 77 classes, seed 42. The test read here is documented divergence D1: `REQUIREMENTS.md` AC-002 requires `make baseline` to write test macro-F1 and outranks `ARCHITECTURE.md`. |
| U04 | DistilBERT training and immutable artifact | Implemented | `make train` sealed run `intentguard-distilbert-1fb62b1bb463-88e538757339` from `distilbert/distilbert-base-uncased@12040accade4e8a0f71eabdb258fecc2e7e948be`: measured validation accuracy 0.7162, macro-F1 0.6541, and threshold 0.1684 selected from validation confidences only at coverage 0.7015, accepted accuracy 0.8395, selective risk 0.1605. No test split was read, so this umbrella has no test metric. CPU-only by decision D10; `NFR-001`'s GPU clause stays unevidenced. |
| U05 | Comparative evaluation and selective prediction | Implemented | `make evaluate` compares both sealed artifacts on the untouched test split as run `intentguard-evaluation-1fb62b1bb463-55796a53ca3e`, applying the persisted validation threshold 0.16841767053420467 without reselecting it. Measured on 3,080 test examples: baseline accuracy 0.8653 / macro-F1 0.8654, transformer accuracy 0.6955 / macro-F1 0.6620, macro-F1 delta -0.2034, verdict `baseline_better`. Selective prediction at that threshold: baseline coverage 0.7500, accepted accuracy 0.9333, selective risk 0.0667; transformer coverage 0.6799, accepted accuracy 0.8161, selective risk 0.1839. Calibration Measured over 15 fixed equal-width bins: baseline ECE 0.4883 (mean confidence 0.3770 against accuracy 0.8653, 15/15 bins occupied), transformer ECE 0.4697 (mean confidence 0.2258 against accuracy 0.6955, 9/15 bins occupied); both are underconfident. Full risk/coverage curves are written for both models (3,074 and 3,081 points). The curated unsupported-request fixture is Measured in the same run: 12 hand-written requests spanning all six declared categories, decided once each at that same persisted threshold, all 12 abstaining, written separately to `unsupported_fixture.json` and `unsupported_fixture.md`. That rate is reported only beside its in-distribution contrast — mean confidence 0.0503 on the fixture against 0.2258 on test, with the same model abstaining on 0.3201 of test — because a total rate alone is indistinguishable from a model that abstains on everything. No accuracy is reported for the fixture: no BANKING77 intent is correct for any row, so accuracy is undefined there. Single-request latency Measured in this run on the recorded CPU over 200 real test texts after 20 discarded warm-up requests: baseline p50 0.55 ms / p95 0.59 ms, transformer p50 8.64 ms / p95 11.08 ms — descriptive for that machine and that run, not a service-level claim, and the only non-reproducing section of the report. Repeated runs of this identical configuration have produced transformer p50 values between roughly 8.6 ms and 10.7 ms on this machine, so read these two figures as one sample from that spread; the run ID covers the sampling protocol and never the durations, which is why re-running rewrites this directory in place with different timings and identical metrics. |
| U06 | FastAPI inference and real-artifact demo | Implemented | All three subtasks are complete: S06.1 typed schemas, stable errors, request IDs, and text-free logging; S06.2 the sealed-artifact predictor behind `/health` and `/v1/predict`; S06.3 `make serve` and `make demo` wired to that path. `make demo` Measured over a real socket against `intentguard-distilbert-1fb62b1bb463-88e538757339`: `/health` returned `ready`, `device` `cpu`, `label_count` 77; the in-domain request `"How do I activate my new card?"` was accepted as `activate_my_card` at confidence 0.5300218231428692; the curated unsupported row `unsupported-001` abstained at 0.04127836201977225 with `intent` `null`. Both decisions used the persisted validation threshold 0.16841767053420467, unchanged from the sealed bundle and reselected nowhere. The abstained confidence agrees with the E05 evaluation's 0.04127837051435484 for the same row to seven decimal places, so serving and evaluation are reading the same weights and the same threshold. Startup logged `service_start` then `artifact_loaded`; the artifact was verified before the port was bound. `make lint` clean (Ruff, mypy strict over 50 files, 10/10 foundation checks) and `make test` passed in both environment states; the suite counts are recorded once, for the current tree, in the reconciliation section below rather than per row, because a count quoted against an older tree reads as a regression when the only thing that changed was the number of tests. |
| U07 | Full validation and acceptance gate | Partial | S07.1 is Implemented: `scripts/validate_acceptance.py` audits all 42 primary identifiers, `make acceptance` and one CI step invoke it, and its 34 collected tests — 31 functions, one parametrized over four statuses — pass in both environment states. S07.2's audit, this document's corrections, and the recorded verdict below are complete. The umbrella stays `Partial` and not `Implemented` because NFR-002's named evidence is a green GitHub Actions run of the added step, and no CI run has executed since the step was written; that claim is `Planned` until Gate C produces one. |
| U08 | Documentation and recruiter-ready delivery | Planned | Foundation documents only; delivery work remains |

Strict MVP is not complete. The pinned dataset contract, both models' test metrics, the transformer's validation metrics and selected threshold, the test-split comparison and abstention behaviour, the curated unsupported-request check, both models' calibration and single-request CPU latency, and the served accept/abstain behaviour of the sealed transformer artifact over HTTP are Measured from executed local runs. No GPU claim is evidenced.

U06 is Implemented, which closes the serving half of the MUST hierarchy: the typed FastAPI boundary loads one sealed artifact, applies the persisted validation threshold, and `make demo` demonstrates one accept and one abstain over a real socket rather than through a test client or a deterministic stand-in.

## Suite counts reconcile across three environments

An earlier revision of this document recorded `make test` as 585 passed with the artifact present and 563 passed / 22 skipped without it. Those figures do not reproduce on any tree and are corrected here. The collected total is what changed: this row's counts were carried forward from the tree that measured them and were never re-measured as tests were added.

Measured on the current E07 tree, which adds 34 tests to the 603 collected at `14d3b27`:

| Environment | Result | Skip gate |
|---|---|---|
| Local, `INTENTGUARD_ARTIFACT_ROOT` set to the E05 artifact root | 637 passed | none |
| Local, variable unset | 615 passed, 22 skipped | all 22 in `tests/integration/test_api.py`, gated on a sealed `intentguard-distilbert` bundle |
| GitHub Actions, clean runner | not yet executed against this tree | expected 598 passed / 39 skipped: the same 22, plus 17 in `tests/integration/test_training_smoke.py` gated on the `distilbert-base-uncased` Hugging Face cache |

Every environment collects the same 637; the three numbers differ only by which gate is unmet, and each gate's skip message names the command that satisfies it. The CI row is an arithmetic expectation, not a measurement: 22 + 17 = 39 skips against a 637 collection. It stays `Planned` until a run exists.

## Strict-MVP verdict: FAIL

Issued by `make acceptance`, which exits non-zero while any cause remains. The audit classified 44 rows over 42 primary identifiers — NFR-001 contributes three rows, one per clause — and reported 38 passed, 1 not evidenced, 5 blocked.

Seven causes, each traced to a row rather than assumed. The audit prints them in this order:

| # | Cause | Evidence |
|---|---|---|
| 1 | U07 is `Partial` | NFR-002's evidence is a green CI run of the acceptance step; none has executed against this tree |
| 2 | U08 is `Planned` | Documentation and recruiter-ready delivery is backlog only |
| 3 | T-007 is blocked | `scripts/validate_acceptance.py` exists, but its owning capability U07 is `Partial` |
| 4 | T-008 is blocked | `README.md` exists, but its owning capability U08 is `Planned` |
| 5 | NFR-002 is blocked | `.github/workflows/ci.yml` exists, but its owning capability U07 is `Partial` |
| 6 | NFR-009 is blocked | `scripts/validate_acceptance.py` exists, but its owning capability U07 is `Partial` |
| 7 | NFR-010 is blocked | `docs/OPERATIONS.md` exists, but its owning capability U08 is `Planned` |

`AGENTS.md` requires every MUST capability to be `Implemented`, so causes 1 and 2 are each independently sufficient. Causes 3–7 are recorded rather than folded into them because the gate enumerates every failure it finds instead of stopping at the first, and because each names the specific file whose presence must not be mistaken for completion.

Causes 3–7 are the audit's own correction to an earlier defect in it. Its first version passed any identifier whose named file was present on disk, consulting the owning capability's status only when the file was *missing*. That reported NFR-010 as `passed` while U08 was `Planned` — a Planned capability rendering as satisfied, which is precisely the substitution this gate exists to prevent. The status now decides, and presence alone never passes.

Three further candidate causes were assessed and did **not** hold:

- **NFR-001's RAM clause passes as `Measured`.** The sealed bundle's `provenance.json` records `peak_memory_bytes` 2,877,472,768 — 2.88 GB against a 24 GB clause.
- **NFR-001's GPU clause is `not_applicable`, not an unmeasured MUST.** The same record shows `cuda_available` false on device `cpu`, so no GPU path was exercised. NFR-002 requires CPU execution; the GPU clause describes local convenience hardware, not a deliverable capability. CUDA compatibility is unverified and no GPU claim is made anywhere. This is the single `not_evidenced` row.
- **The 585/563 contradiction is resolved above** rather than left standing as a verdict input.

No applicable MUST clause is left `unmeasured`: across all 44 rows, 22 are `measured` with an evidence path and 22 are `not_applicable` with a recorded reason. `make lint` enforces that no row can be excused without one.

NFR-006's latency figures remain `Measured` but explicitly non-reproducing: the run ID covers the sampling protocol and never the durations. The audit records that qualifier rather than a bare pass.

The serving evidence above was produced on this machine from the E05 artifact root. It is not a CI claim: the demo has not been executed in GitHub Actions, so the reproducibility of `make demo` on a clean CPU runner is Planned and belongs to U07. The latency figures in the demo transcript are single observations and no service-level claim is made from them. Those figures are also narrower than their published definition, which is documented divergence D2: `INTERFACE_CONTRACT.md:72` defines `latency_ms` as request validation plus inference plus response assembly, while the served value times inference only. Validation has already completed when the handler is entered, and assembly cannot be inside a number the response being assembled must carry. The reported value is therefore a lower bound on the contract's quantity, recorded rather than relabelled.

## The transformer does not beat the baseline

The fine-tuned DistilBERT scored 0.2034 lower on test macro-F1 than the TF-IDF baseline. `REQUIREMENTS.md` AC-004 requires the comparison to be reported whichever way it falls, so this is a satisfied acceptance criterion and not a defect. At the frozen configuration — two CPU epochs, learning rate 2e-5, max sequence length 96 — the lexical baseline is the stronger model on this split.

No configuration, epoch count, seed, or threshold was changed in response to observing this result. Doing so would let a test label influence a modelling decision, which AC-005 forbids. The result stands as measured, and any future attempt to improve the transformer must be justified and validated without reading the test split.

## Neither model's confidence is a probability of correctness

Both models are substantially underconfident on the test split. The baseline reports a mean confidence of 0.3770 against an accuracy of 0.8653, and the transformer 0.2258 against 0.6955. Every occupied bin errs in the same direction for both models, which is why each ECE happens to equal its aggregate confidence-accuracy gap here; that is a property of this data, not of the metric, and the imbalanced fixture in `tests/fixtures/metric_regression.json` separates the two quantities (1/12 against 1/20).

The transformer's confidence never exceeded 0.6000 on any of the 3,080 test examples — six of the fifteen bins are empty. The persisted threshold of 0.1684 therefore has to be read relative to that range, not as a claimed probability of correctness. Reported because a reader who takes 0.1684 as a probability would conclude the system accepts almost anything, which is not what the coverage of 0.6799 shows.

No recalibration was applied. Temperature scaling or an equivalent fit would need its own validation-only evidence, and it is out of scope for the weekend MVP. Abstention here is a ranking decision over confidences, which underconfidence does not invalidate; the cost it imposes is coverage, since answers the model would have got right are discarded.
