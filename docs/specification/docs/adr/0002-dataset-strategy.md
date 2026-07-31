# ADR-0002: BANKING77 as the single primary dataset

- **Status:** Accepted
- **Date:** 2026-07-31

## Context

The project needs a public, laptop-sized dataset with enough class granularity
to make evaluation meaningful. It must not require scraping, manual
annotation, private support data, or multiple dataset pipelines.

## Decision

Use one pinned revision of `PolyAI/banking77` under CC BY 4.0.

- Preserve the upstream train/test split.
- Derive a stratified 15% validation split from training data with seed 42.
- Record revision, licence, label mapping, split metadata and hashes.
- Use the untouched test split only for final comparison.
- Maintain a small curated unsupported-query fixture separately and explicitly
  exclude it from general OOD claims.

## Alternatives considered

### CLINC150

Offers explicit out-of-scope examples and more domains, but broadens the
business context and adds taxonomy complexity.

### Proprietary or scraped support tickets

Would be more realistic but introduces privacy, licence, cleaning and
annotation problems that do not fit the weekend.

### Fully synthetic dataset

Useful as a fallback and for tests, but not credible as the primary source for
portfolio performance claims.

### Multiple support datasets

Could improve domain-shift analysis, but violates the one-primary-dataset
constraint and increases normalization work.

## Consequences

### Positive

- Small, public, well-defined and easy to load.
- 77 classes create meaningful confusion and macro-metric analysis.
- Full-data local training is feasible.
- The test split supports fair baseline/model comparison.

### Negative

- Banking taxonomy does not match a real employer’s ticket taxonomy.
- It is closed-set and not a general OOD benchmark.
- English-only data limits generalization.
- Public examples may not represent contemporary operational traffic.

## Reconsideration trigger

Reconsider if:

- the pinned revision or licence becomes unavailable or ambiguous;
- the loader cannot reproduce the upstream split;
- the target job is explicitly non-NLP or requires another domain;
- a real, legally usable employer dataset is later supplied.

Changing the primary dataset requires new requirements, data-contract tests,
evaluation baselines and a superseding ADR.

