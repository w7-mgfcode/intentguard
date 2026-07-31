# Local GitHub backlog

This directory is the reviewable Gate D source for the future GitHub planning system. It summarizes and links to `docs/specification/`; it does not replace that authoritative source.

## Fixed inventory

- One master issue: `MASTER_ISSUE.md`.
- Eight MUST umbrellas: `umbrellas/U01-*.md` through `umbrellas/U08-*.md`.
- Twenty-three MUST child tasks: `tasks/C01.1-*.md` through `tasks/C08.3-*.md`.
- Optional work only in `PARKING_LOT.md`; no optional issue bodies exist initially.

## Review order

1. [Master issue](MASTER_ISSUE.md)
2. [Traceability](TRACEABILITY.md)
3. [Project configuration](PROJECT_CONFIGURATION.md)
4. [Labels](LABELS.md)
5. [GitHub execution plan](GITHUB_EXECUTION_PLAN.md)
6. [Optional parking lot](PARKING_LOT.md)
7. `umbrellas/` and `tasks/` issue bodies
8. `github-manifest.json` and `traceability.json`

The manifests are inert local data. Executing them or creating any GitHub resource requires explicit Gate D approval after Gates B and C.
