# Local GitHub backlog

This directory is the reviewable Gate D source for the future GitHub planning system. It summarizes and links to `docs/specification/`; it does not replace that authoritative source.

## Fixed inventory

- One native GitHub Milestone: `M1 — IntentGuard Weekend MVP`.
- Three MUST umbrella issues: `umbrellas/W01-*.md` through `umbrellas/W03-*.md`.
- Eight MUST epic issues: the existing `umbrellas/U01-*.md` through `umbrellas/U08-*.md` body paths, canonically identified as `E01`–`E08` with `old_identifier` aliases.
- Twenty-three MUST subtasks: the existing `tasks/C01.1-*.md` through `tasks/C08.3-*.md` body paths, canonically identified as `S01.1`–`S08.3` with `old_identifier` aliases.
- Thirty-four Project items and thirty-one native relationships (`W→E` and `E→S`).
- `MASTER_ISSUE.md` remains the versioned milestone acceptance contract; no remote master issue is created.
- Optional work only in `PARKING_LOT.md`; no optional issue bodies exist initially.

## Review order

1. [Milestone acceptance contract](MASTER_ISSUE.md)
2. [Traceability](TRACEABILITY.md)
3. [Project configuration](PROJECT_CONFIGURATION.md)
4. [Labels](LABELS.md)
5. [GitHub execution plan](GITHUB_EXECUTION_PLAN.md)
6. [Optional parking lot](PARKING_LOT.md)
7. `umbrellas/` and `tasks/` issue bodies (legacy-compatible paths for E/S records)
8. `github-manifest.json` and `traceability.json`

The manifests are inert local data. Executing them or creating any GitHub resource requires explicit Gate D approval after Gates B and C.
