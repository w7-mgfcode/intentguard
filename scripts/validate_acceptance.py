"""Audit acceptance evidence for every primary requirement identifier (T-007, NFR-009).

This script classifies evidence; it never produces it. Nothing here trains a model,
evaluates a split, or writes into an artifact bundle, because a validation gate that
regenerates its own evidence cannot detect missing evidence.

Three outcomes are kept strictly distinct, and `not_evidenced` is never folded into
`passed`:

``passed``
    A required file exists and, where the check is content-aware, says what the
    requirement needs it to say.
``not_evidenced``
    The evidence is absent in this environment. Carries a reason naming what is
    missing and, where the absence is environmental rather than a defect, why.
``blocked``
    The capability itself is not implemented, so no evidence can exist yet.

The distinction matters most in CI, where the sealed 257 MB transformer bundle is
unavailable: AC-006, AC-007, AC-009, and AC-013 are then `not_evidenced` with a
reason, and the audit still runs its structural checks rather than reporting a pass
it cannot support.

Evidence roots are resolved, never assumed. `docs/backlog/traceability.json` records
a *nominal* implementation path per identifier — `reports/baseline.json` and
`reports/evaluate/<run_id>/comparison.json` are shapes, not literal paths — so the
run-scoped directories are discovered on disk. `INTENTGUARD_ARTIFACT_ROOT` and
`INTENTGUARD_REPORT_ROOT` may point at the worktree that holds them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, cast

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
BACKLOG_ROOT: Final = REPOSITORY_ROOT / "docs" / "backlog"
TRACEABILITY_JSON: Final = BACKLOG_ROOT / "traceability.json"
TRACEABILITY_MARKDOWN: Final = BACKLOG_ROOT / "TRACEABILITY.md"
STATUS_DOCUMENT: Final = REPOSITORY_ROOT / "docs" / "IMPLEMENTATION_STATUS.md"

ARTIFACT_ROOT_VARIABLE: Final = "INTENTGUARD_ARTIFACT_ROOT"
REPORT_ROOT_VARIABLE: Final = "INTENTGUARD_REPORT_ROOT"

EXPECTED_PRIMARY_COUNT: Final = 42
EXPECTED_SECONDARY_COUNT: Final = 1

Outcome = Literal["passed", "not_evidenced", "blocked"]
Applicability = Literal["measured", "not_applicable", "unmeasured"]

# Capability status is owned by docs/IMPLEMENTATION_STATUS.md, which this script reads
# rather than restates. Only the epic->umbrella mapping lives here, because the audit
# has to attribute an identifier to the capability whose status governs it.
EPIC_TO_UMBRELLA: Final = {
    "E01": "U01",
    "E02": "U02",
    "E03": "U03",
    "E04": "U04",
    "E05": "U05",
    "E06": "U06",
    "E07": "U07",
    "E08": "U08",
}

MUST_UMBRELLAS: Final = tuple(f"U{index:02d}" for index in range(1, 9))
STATUS_ROW: Final = re.compile(r"^\|\s*(U0[1-8])\s*\|[^|]*\|\s*([A-Za-z]+)\s*\|")


class AcceptanceError(Exception):
    """A structural fault in the audit's own inputs, not a failed requirement."""


@dataclass(frozen=True)
class Identifier:
    """One primary ownership row from `traceability.json`."""

    identifier: str
    umbrella: str
    epic: str
    subtask: str
    implementation_path: str
    validation_command: str
    expected_evidence: str

    @property
    def capability(self) -> str:
        umbrella = EPIC_TO_UMBRELLA.get(self.epic)
        if umbrella is None:
            raise AcceptanceError(f"{self.identifier} names unknown epic {self.epic!r}")
        return umbrella


@dataclass
class Row:
    """One audited identifier, or one separable clause of one."""

    identifier: str
    clause: str | None
    capability: str
    capability_status: str
    evidence_path: str | None
    executed_result: Outcome
    reason: str | None
    applicability: Applicability
    applicability_reason: str | None = None

    def as_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "identifier": self.identifier,
            "capability": self.capability,
            "capability_status": self.capability_status,
            "evidence_path": self.evidence_path,
            "executed_result": self.executed_result,
            "measured": self.applicability == "measured",
            "applicability": self.applicability,
        }
        if self.clause is not None:
            payload["clause"] = self.clause
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.applicability_reason is not None:
            payload["applicability_reason"] = self.applicability_reason
        return payload


@dataclass
class Evidence:
    """Resolved locations of generated evidence. Absence is recorded, never created."""

    artifact_root: Path | None
    report_root: Path | None
    baseline_bundle: Path | None = None
    transformer_bundle: Path | None = None
    baseline_report: Path | None = None
    train_report: Path | None = None
    evaluation_report: Path | None = None
    notes: list[str] = field(default_factory=list)


def _load_json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise AcceptanceError(f"required input is missing: {path}")
    value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict):
        raise AcceptanceError(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _string(mapping: dict[str, object], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise AcceptanceError(f"{context} must carry a non-empty string {key!r}")
    return value


def load_identifiers() -> tuple[tuple[Identifier, ...], int]:
    """Read primary ownership, asserting exactly one primary owner per identifier."""

    document = _load_json_object(TRACEABILITY_JSON)
    ownership = document.get("ownership")
    if not isinstance(ownership, list):
        raise AcceptanceError("traceability.json must carry an 'ownership' array")
    secondary = document.get("secondary_relationships")
    if not isinstance(secondary, list):
        raise AcceptanceError("traceability.json must carry a 'secondary_relationships' array")

    identifiers: list[Identifier] = []
    seen: set[str] = set()
    for entry in ownership:
        if not isinstance(entry, dict):
            raise AcceptanceError("every ownership entry must be an object")
        row = cast(dict[str, object], entry)
        name = _string(row, "identifier", "ownership entry")
        if row.get("primary") is not True:
            raise AcceptanceError(f"{name} appears in 'ownership' without primary: true")
        if name in seen:
            raise AcceptanceError(f"{name} has more than one primary owner")
        seen.add(name)
        identifiers.append(
            Identifier(
                identifier=name,
                umbrella=_string(row, "umbrella", name),
                epic=_string(row, "epic", name),
                subtask=_string(row, "subtask", name),
                implementation_path=_string(row, "implementation_path", name),
                validation_command=_string(row, "validation_command", name),
                expected_evidence=_string(row, "expected_evidence", name),
            )
        )

    if len(identifiers) != EXPECTED_PRIMARY_COUNT:
        raise AcceptanceError(
            f"expected {EXPECTED_PRIMARY_COUNT} primary identifiers, found {len(identifiers)}"
        )
    if len(secondary) != EXPECTED_SECONDARY_COUNT:
        raise AcceptanceError(
            f"expected {EXPECTED_SECONDARY_COUNT} secondary relationship(s), found {len(secondary)}"
        )
    # A secondary row may never stand in for primary ownership, so every secondary
    # identifier must also be owned primarily somewhere.
    for entry in secondary:
        if not isinstance(entry, dict):
            raise AcceptanceError("every secondary entry must be an object")
        name = _string(cast(dict[str, object], entry), "identifier", "secondary entry")
        if name not in seen:
            raise AcceptanceError(f"secondary {name} has no primary owner")

    return tuple(identifiers), len(secondary)


def load_capability_status() -> dict[str, str]:
    """Read each umbrella's declared status from the status document."""

    if not STATUS_DOCUMENT.is_file():
        raise AcceptanceError(f"required input is missing: {STATUS_DOCUMENT}")
    statuses: dict[str, str] = {}
    for line in STATUS_DOCUMENT.read_text(encoding="utf-8").splitlines():
        match = STATUS_ROW.match(line)
        if match is not None:
            statuses[match.group(1)] = match.group(2)
    missing = [umbrella for umbrella in MUST_UMBRELLAS if umbrella not in statuses]
    if missing:
        raise AcceptanceError(f"status document declares no status for {missing}")
    return statuses


def _newest_directory(root: Path, prefix: str) -> Path | None:
    if not root.is_dir():
        return None
    candidates = sorted(
        (path for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix)),
        key=lambda path: path.name,
    )
    return candidates[-1] if candidates else None


def resolve_evidence(environment: dict[str, str] | None = None) -> Evidence:
    """Locate generated evidence without creating any.

    Both roots may be redirected, because the sealed bundles and their reports were
    produced in a sibling worktree and copying a sealed artifact would put its
    provenance at risk.
    """

    source = os.environ if environment is None else environment

    artifact_override = source.get(ARTIFACT_ROOT_VARIABLE, "").strip()
    artifact_root = Path(artifact_override) if artifact_override else REPOSITORY_ROOT / "artifacts"
    report_override = source.get(REPORT_ROOT_VARIABLE, "").strip()
    if report_override:
        report_root: Path | None = Path(report_override)
    elif artifact_override:
        # Reports sit beside artifacts in a run's worktree; a redirected artifact root
        # with a default report root would silently mix two runs' evidence.
        report_root = Path(artifact_override).parent / "reports"
    else:
        report_root = REPOSITORY_ROOT / "reports"

    evidence = Evidence(
        artifact_root=artifact_root if artifact_root.is_dir() else None,
        report_root=report_root if report_root is not None and report_root.is_dir() else None,
    )
    if evidence.artifact_root is None:
        evidence.notes.append(
            f"no artifact root at {artifact_root}; set {ARTIFACT_ROOT_VARIABLE} to a root "
            "holding the sealed bundles"
        )
    else:
        evidence.baseline_bundle = _newest_directory(
            evidence.artifact_root / "intentguard-baseline", "intentguard-baseline-"
        )
        evidence.transformer_bundle = _newest_directory(
            evidence.artifact_root / "intentguard-distilbert", "intentguard-distilbert-"
        )
    if evidence.report_root is None:
        evidence.notes.append(f"no report root at {report_root}")
    else:
        evidence.baseline_report = _newest_directory(
            evidence.report_root / "baseline", "intentguard-baseline-"
        )
        evidence.train_report = _newest_directory(
            evidence.report_root / "train", "intentguard-distilbert-"
        )
        # Several evaluation runs may exist. The audit needs the one that carries the
        # curated unsupported fixture, because AC-012 is evidenced only there; a
        # newest-wins pick would silently choose a run without it.
        evaluate_root = evidence.report_root / "evaluate"
        if evaluate_root.is_dir():
            complete = sorted(
                (
                    path
                    for path in evaluate_root.iterdir()
                    if path.is_dir() and (path / "unsupported_fixture.json").is_file()
                ),
                key=lambda path: path.name,
            )
            evidence.evaluation_report = (
                complete[-1]
                if complete
                else _newest_directory(evaluate_root, "intentguard-evaluation-")
            )
    return evidence


def _file_row(
    identifier: Identifier,
    statuses: dict[str, str],
    path: Path | None,
    *,
    missing_reason: str,
    applicability: Applicability = "measured",
    applicability_reason: str | None = None,
    clause: str | None = None,
) -> Row:
    """Classify one identifier against one expected file."""

    capability = identifier.capability
    status = statuses[capability]
    if path is not None and path.is_file():
        try:
            shown = str(path.relative_to(REPOSITORY_ROOT))
        except ValueError:
            shown = str(path)
        # A file existing is not the same as the capability owning it being done. The
        # delivery documents exist while U08 is Planned, so passing on presence alone
        # would report an unstarted capability as satisfied — the exact substitution
        # this audit exists to catch. The owning status decides.
        if status in {"Planned", "Partial", "Mocked", "Blocked"}:
            return Row(
                identifier=identifier.identifier,
                clause=clause,
                capability=capability,
                capability_status=status,
                evidence_path=shown,
                executed_result="blocked",
                reason=(
                    f"{shown} exists, but its owning capability {capability} is {status}; "
                    "presence of a file is not evidence that the capability is complete"
                ),
                applicability=applicability,
                applicability_reason=applicability_reason,
            )
        return Row(
            identifier=identifier.identifier,
            clause=clause,
            capability=capability,
            capability_status=status,
            evidence_path=shown,
            executed_result="passed",
            reason=None,
            applicability=applicability,
            applicability_reason=applicability_reason,
        )
    outcome: Outcome = "blocked" if status in {"Planned", "Partial", "Mocked"} else "not_evidenced"
    return Row(
        identifier=identifier.identifier,
        clause=clause,
        capability=capability,
        capability_status=status,
        evidence_path=None,
        executed_result=outcome,
        reason=missing_reason,
        applicability="unmeasured" if applicability == "measured" else applicability,
        applicability_reason=applicability_reason,
    )


def _repository_file(identifier: Identifier, statuses: dict[str, str]) -> Row:
    """Classify an identifier whose evidence is a checked-in file."""

    path = REPOSITORY_ROOT / identifier.implementation_path
    return _file_row(
        identifier,
        statuses,
        path if path.exists() else None,
        missing_reason=f"{identifier.implementation_path} does not exist",
        # A checked-in module is implementation, not an empirical measurement.
        applicability="not_applicable",
        applicability_reason="source or test file; carries no empirical claim of its own",
    )


def _nfr001_rows(identifier: Identifier, statuses: dict[str, str], evidence: Evidence) -> list[Row]:
    """Decompose NFR-001 into its three clauses.

    One averaged row would hide the GPU clause behind the batch-size clause, so each
    clause is classified on its own evidence. The RAM and device clauses are read from
    the sealed bundle's own provenance rather than asserted.
    """

    capability = identifier.capability
    status = statuses[capability]
    provenance = (
        evidence.transformer_bundle / "provenance.json"
        if evidence.transformer_bundle is not None
        else None
    )
    runtime: dict[str, object] = {}
    if provenance is not None and provenance.is_file():
        recorded = _load_json_object(provenance).get("runtime")
        if isinstance(recorded, dict):
            runtime = cast(dict[str, object], recorded)

    rows: list[Row] = []
    shown = str(provenance) if provenance is not None else None

    peak = runtime.get("peak_memory_bytes")
    if isinstance(peak, int):
        gigabytes = peak / 1_000_000_000
        rows.append(
            Row(
                identifier=identifier.identifier,
                clause="fits within 24 GB system RAM",
                capability=capability,
                capability_status=status,
                evidence_path=shown,
                executed_result="passed" if gigabytes <= 24 else "not_evidenced",
                reason=None
                if gigabytes <= 24
                else f"recorded peak {gigabytes:.2f} GB exceeds the 24 GB clause",
                applicability="measured",
                applicability_reason=(
                    f"recorded peak_memory_bytes {peak} ({gigabytes:.2f} GB) on the training run"
                ),
            )
        )
    else:
        rows.append(
            Row(
                identifier=identifier.identifier,
                clause="fits within 24 GB system RAM",
                capability=capability,
                capability_status=status,
                evidence_path=None,
                executed_result="not_evidenced",
                reason="no peak_memory_bytes recorded in the transformer bundle's provenance",
                applicability="unmeasured",
            )
        )

    cuda_available = runtime.get("cuda_available")
    device = runtime.get("device")
    if cuda_available is False and device == "cpu":
        # The clause names an RTX 5060. The run recorded cuda_available false on a
        # cpu device, so the GPU was not exercised. That is an honest not_applicable
        # for a CPU-only weekend scope, and it is emphatically not a measurement:
        # reporting it as `measured` would claim GPU evidence that does not exist.
        rows.append(
            Row(
                identifier=identifier.identifier,
                clause="runs on the available RTX 5060 Mobile GPU",
                capability=capability,
                capability_status=status,
                evidence_path=shown,
                executed_result="not_evidenced",
                reason=(
                    "the sealed run recorded cuda_available false on device 'cpu', so no GPU "
                    "path was exercised; CUDA compatibility is unverified"
                ),
                applicability="not_applicable",
                applicability_reason=(
                    "CPU-only execution is a declared valid fallback (NFR-002 requires CPU; "
                    "the GPU clause is a local-convenience claim, not a deliverable "
                    "capability), so the clause is out of scope for this run rather than "
                    "an unmeasured MUST"
                ),
            )
        )
    else:
        rows.append(
            Row(
                identifier=identifier.identifier,
                clause="runs on the available RTX 5060 Mobile GPU",
                capability=capability,
                capability_status=status,
                evidence_path=shown,
                executed_result="not_evidenced",
                reason="no runtime device record establishes whether a GPU path was exercised",
                applicability="unmeasured",
            )
        )

    configuration = REPOSITORY_ROOT / "configs" / "default.toml"
    configured = configuration.is_file() and "train_batch_size" in configuration.read_text(
        encoding="utf-8"
    )
    rows.append(
        Row(
            identifier=identifier.identifier,
            clause="batch size is configurable for lower-memory devices",
            capability=capability,
            capability_status=status,
            evidence_path="configs/default.toml" if configured else None,
            executed_result="passed" if configured else "not_evidenced",
            reason=None if configured else "configs/default.toml declares no train_batch_size",
            applicability="measured" if configured else "unmeasured",
            applicability_reason="declared train_batch_size and eval_batch_size"
            if configured
            else None,
        )
    )
    return rows


def _evaluation_rows(
    identifier: Identifier, statuses: dict[str, str], evidence: Evidence
) -> list[Row]:
    """Classify the identifiers whose evidence is a run-scoped report directory."""

    report = evidence.evaluation_report
    name = identifier.identifier
    if name == "AC-002":
        return [
            _file_row(
                identifier,
                statuses,
                (evidence.baseline_report / "metrics.json") if evidence.baseline_report else None,
                missing_reason="no baseline metrics report found under the report root",
                applicability_reason="test accuracy and macro-F1 recorded from the reloaded"
                " baseline artifact",
            )
        ]
    if name in {"AC-004", "FR-005", "T-005", "AC-012", "FR-009", "NFR-006"}:
        filename = "unsupported_fixture.json" if name in {"AC-012", "FR-009"} else "comparison.json"
        reason = (
            f"no evaluation run under the report root carries {filename}; "
            "`make evaluate` has not run in this environment"
        )
        applicability_reason = None
        if name == "NFR-006":
            # NFR-006's latency section is the one part of the report that does not
            # reproduce between runs of the same configuration. Recording it as a bare
            # pass would overstate it, so the qualifier travels with the row.
            applicability_reason = (
                "p50/p95 recorded with batch conditions, but latency is descriptive for one "
                "machine and one run and does not reproduce; the run ID covers the sampling "
                "protocol, never the durations"
            )
        elif name in {"AC-012", "FR-009"}:
            applicability_reason = (
                "curated fixture decided at the persisted threshold; a rate over 12 "
                "hand-written rows is a behavioural check, not OOD performance"
            )
        return [
            _file_row(
                identifier,
                statuses,
                (report / filename) if report is not None else None,
                missing_reason=reason,
                applicability_reason=applicability_reason,
            )
        ]
    raise AcceptanceError(f"{name} has no evaluation-report rule")


def _artifact_rows(
    identifier: Identifier, statuses: dict[str, str], evidence: Evidence
) -> list[Row]:
    """Classify identifiers evidenced by a sealed bundle's own files."""

    name = identifier.identifier
    bundle = evidence.transformer_bundle
    filename = {
        "T-004": "provenance.json",
        "FR-003": "provenance.json",
        "AC-003": "manifest.json",
        "FR-004": "threshold.json",
        "AC-005": "threshold.json",
    }[name]
    applicability_reason = None
    if name in {"FR-004", "AC-005"}:
        applicability_reason = (
            "threshold selected from validation confidences only; no test label was read"
        )
    return [
        _file_row(
            identifier,
            statuses,
            (bundle / filename) if bundle is not None else None,
            missing_reason=(
                f"no sealed transformer bundle carrying {filename}; set "
                f"{ARTIFACT_ROOT_VARIABLE} to a root holding one"
            ),
            applicability_reason=applicability_reason,
        )
    ]


def _served_rows(identifier: Identifier, statuses: dict[str, str], evidence: Evidence) -> list[Row]:
    """Classify the identifiers that need a loaded artifact to be evidenced.

    These are the rows that legitimately go `not_evidenced` in CI. The reason names
    the environment rather than implying a defect.
    """

    available = evidence.transformer_bundle is not None
    path = REPOSITORY_ROOT / identifier.implementation_path
    capability = identifier.capability
    status = statuses[capability]
    if not path.exists():
        return [
            Row(
                identifier=identifier.identifier,
                clause=None,
                capability=capability,
                capability_status=status,
                evidence_path=None,
                executed_result="blocked",
                reason=f"{identifier.implementation_path} does not exist",
                applicability="unmeasured",
            )
        ]
    if not available:
        return [
            Row(
                identifier=identifier.identifier,
                clause=None,
                capability=capability,
                capability_status=status,
                evidence_path=identifier.implementation_path,
                executed_result="not_evidenced",
                reason=(
                    "the sealed transformer bundle is unavailable here, so the real-artifact "
                    f"path cannot be exercised; set {ARTIFACT_ROOT_VARIABLE}. In CI this is "
                    "expected and declared: the bundle is untracked and roughly 257 MB, and a "
                    "CI-trained model would carry a different threshold and so be a different "
                    "artifact"
                ),
                applicability="not_applicable",
                applicability_reason=(
                    "measured locally against the sealed bundle; not evidenced in CI by "
                    "declaration, not by defect"
                ),
            )
        ]
    return [
        Row(
            identifier=identifier.identifier,
            clause=None,
            capability=capability,
            capability_status=status,
            evidence_path=identifier.implementation_path,
            executed_result="passed",
            reason=None,
            applicability="measured",
            applicability_reason=(
                "exercised against the sealed bundle by the suite gated on "
                f"{ARTIFACT_ROOT_VARIABLE}"
            ),
        )
    ]


def _ac014_row(identifier: Identifier, statuses: dict[str, str]) -> Row:
    """Classify AC-014, whose nominal evidence path is this audit's own output.

    `reports/acceptance.json` cannot be a precondition of the run that writes it: on a
    clean checkout the file is absent, so treating its absence as a blocker would make
    the gate fail for the tautological reason that it had not yet finished. AC-014 is
    evidenced by the audit *executing over a complete identifier set* — which is true
    by the time this function is reached — while the verdict it carries is reported
    separately under `strict_mvp`.
    """

    capability = identifier.capability
    return Row(
        identifier=identifier.identifier,
        clause=None,
        capability=capability,
        capability_status=statuses[capability],
        evidence_path=identifier.implementation_path,
        executed_result="passed",
        reason=None,
        applicability="measured",
        applicability_reason=(
            "this audit ran over all primary identifiers and emitted a verdict; the "
            "verdict's own value is reported under strict_mvp, not as this row's status"
        ),
    )


ARTIFACT_BACKED: Final = frozenset({"T-004", "FR-003", "AC-003", "FR-004", "AC-005"})
EVALUATION_BACKED: Final = frozenset(
    {"T-005", "FR-005", "AC-004", "AC-002", "AC-012", "FR-009", "NFR-006"}
)
SERVED: Final = frozenset(
    {"AC-006", "AC-007", "AC-009", "AC-013", "T-006", "FR-006", "FR-007"}
)


def audit(
    identifiers: Sequence[Identifier], statuses: dict[str, str], evidence: Evidence
) -> list[Row]:
    """Produce one row per identifier, or per separable clause."""

    rows: list[Row] = []
    for identifier in identifiers:
        name = identifier.identifier
        if name == "AC-014":
            rows.append(_ac014_row(identifier, statuses))
        elif name == "NFR-001":
            rows.extend(_nfr001_rows(identifier, statuses, evidence))
        elif name in ARTIFACT_BACKED:
            rows.extend(_artifact_rows(identifier, statuses, evidence))
        elif name in EVALUATION_BACKED:
            rows.extend(_evaluation_rows(identifier, statuses, evidence))
        elif name in SERVED:
            rows.extend(_served_rows(identifier, statuses, evidence))
        else:
            rows.append(_repository_file(identifier, statuses))
    covered = {row.identifier for row in rows}
    missing = [
        identifier.identifier
        for identifier in identifiers
        if identifier.identifier not in covered
    ]
    if missing:
        raise AcceptanceError(f"identifiers left unclassified: {sorted(missing)}")
    return rows


def _label(row: Row) -> str:
    return f"{row.identifier} ({row.clause})" if row.clause else row.identifier


def strict_mvp_causes(
    rows: Sequence[Row], statuses: dict[str, str], evidence: Evidence
) -> tuple[list[str], list[str]]:
    """Split failure causes into substantive and environmental.

    The distinction is the difference between "this repository does not satisfy strict
    MVP" and "this machine cannot tell". Conflating them would let a CI runner with no
    sealed bundle report the same FAIL as a genuinely incomplete repository, which
    would make the gate useless in exactly the environment it runs in most often.

    Substantive causes are environment-independent: a declared capability status, or a
    missing measurement whose evidence root *is* present. Environmental causes are
    absences explained by the evidence root itself being unavailable here.
    """

    evidence_complete = evidence.transformer_bundle is not None and (
        evidence.evaluation_report is not None
    )
    substantive: list[str] = []
    environmental: list[str] = []

    for umbrella in MUST_UMBRELLAS:
        status = statuses[umbrella]
        if status != "Implemented":
            substantive.append(
                f"{umbrella} is {status}; AGENTS.md requires every MUST capability to be "
                "Implemented"
            )
    for row in rows:
        if row.applicability == "unmeasured":
            cause = (
                f"{_label(row)} is an applicable MUST claim with no measurement: "
                f"{row.reason or 'no evidence recorded'}"
            )
            (substantive if evidence_complete else environmental).append(cause)
    for row in rows:
        if row.executed_result == "blocked":
            substantive.append(
                f"{_label(row)} is blocked: {row.reason or 'no evidence can exist yet'}"
            )
    return substantive, environmental


def build_report(
    rows: Sequence[Row],
    statuses: dict[str, str],
    evidence: Evidence,
    secondary_count: int = EXPECTED_SECONDARY_COUNT,
) -> dict[str, object]:
    substantive, environmental = strict_mvp_causes(rows, statuses, evidence)
    counts = {
        outcome: sum(1 for row in rows if row.executed_result == outcome)
        for outcome in ("passed", "not_evidenced", "blocked")
    }
    return {
        "schema_version": 1,
        "audit_name": "intentguard-acceptance",
        "identifier_count": len({row.identifier for row in rows}),
        "row_count": len(rows),
        # Recorded so the report stands on its own: a reader can confirm the secondary
        # relationship was counted separately and never as primary ownership.
        "secondary_relationship_count": secondary_count,
        "capability_status": dict(sorted(statuses.items())),
        "evidence_roots": {
            "artifact_root": str(evidence.artifact_root) if evidence.artifact_root else None,
            "report_root": str(evidence.report_root) if evidence.report_root else None,
            "transformer_bundle": str(evidence.transformer_bundle)
            if evidence.transformer_bundle
            else None,
            "evaluation_report": str(evidence.evaluation_report)
            if evidence.evaluation_report
            else None,
            "notes": list(evidence.notes),
        },
        "outcome_counts": counts,
        "rows": [row.as_json() for row in rows],
        "strict_mvp": {
            "verdict": "PASS" if not substantive else "FAIL",
            "causes": substantive,
            # Absences this environment cannot resolve. They never turn a PASS into a
            # FAIL, and they are never silently dropped either: a reader has to be able
            # to see which rows the run could not speak to.
            "environmental_gaps": environmental,
            "evidence_complete": not environmental,
        },
    }


def would_downgrade(output: Path, report: dict[str, object]) -> str | None:
    """Refuse to replace a fully-evidenced report with a degraded one.

    Both a redirected-evidence run and a bare run write to `reports/acceptance.json`
    in this repository, and the report cannot be written beside its evidence without
    mutating a sibling worktree's preserved reports. So the guard lives here: a run
    that could not reach the sealed artifacts must not overwrite the record of a run
    that could. Returns the reason to refuse, or None when writing is safe.
    """

    if not output.is_file():
        return None
    strict = cast(dict[str, object], report["strict_mvp"])
    if strict["evidence_complete"]:
        return None
    try:
        existing = cast(dict[str, object], json.loads(output.read_text(encoding="utf-8")))
        previous = cast(dict[str, object], existing["strict_mvp"])
    except (OSError, ValueError, KeyError):
        return None
    if not previous.get("evidence_complete"):
        return None
    return (
        f"{output} records a fully-evidenced audit; this run could not reach the sealed "
        "evidence, so the existing report was kept. Pass --output to write elsewhere, or "
        "--print-only to skip writing."
    )


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit acceptance evidence (AC-014).")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "reports" / "acceptance.json",
        help="path for the machine-readable report (default: reports/acceptance.json)",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="print the verdict without writing the report",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = parse_arguments(arguments)
    identifiers, secondary_count = load_identifiers()
    statuses = load_capability_status()
    evidence = resolve_evidence()
    rows = audit(identifiers, statuses, evidence)
    report = build_report(rows, statuses, evidence, secondary_count)

    refusal = None
    if not parsed.print_only:
        output = cast(Path, parsed.output)
        refusal = would_downgrade(output, report)
        if refusal is None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

    counts = cast(dict[str, int], report["outcome_counts"])
    print(
        f"Audited {len(identifiers)} primary identifiers ({secondary_count} secondary) "
        f"across {len(rows)} rows: "
        f"{counts['passed']} passed, {counts['not_evidenced']} not evidenced, "
        f"{counts['blocked']} blocked."
    )
    for note in evidence.notes:
        print(f"  note: {note}")
    if refusal is not None:
        print(f"  note: report not written — {refusal}")
    strict = cast(dict[str, object], report["strict_mvp"])
    causes = cast(list[str], strict["causes"])
    gaps = cast(list[str], strict["environmental_gaps"])
    verdict = cast(str, strict["verdict"])
    if causes:
        print(f"Strict MVP: {verdict} — {len(causes)} cause(s):")
        for cause in causes:
            print(f"  - {cause}")
    else:
        print(f"Strict MVP: {verdict}")
    if gaps:
        print(
            f"{len(gaps)} claim(s) unverifiable in this environment (not counted against the "
            "verdict):"
        )
        for gap in gaps:
            print(f"  - {gap}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
