"""Tests for the acceptance audit (T-007, NFR-009, AC-014).

The audit's whole value is that it refuses to report evidence it does not have, so
these tests concentrate on the ways a validation gate lies: folding "cannot tell"
into "passed", letting the environment change the verdict, treating its own output as
its own precondition, and averaging a multi-clause requirement into one comfortable
row.

Fixtures are built in `tmp_path` rather than pointed at the real sealed bundle: a test
that depends on a 257 MB artifact would skip in CI, and these invariants must hold
everywhere.
"""

from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_acceptance_validator() -> ModuleType:
    """Load the audit script by path, matching `test_repository_contract.py`.

    `scripts/` is not an importable package, so the existing contract test loads its
    validator this way. Following that convention keeps one mechanism in the suite.
    """

    script_path = REPOSITORY_ROOT / "scripts" / "validate_acceptance.py"
    specification = spec_from_file_location("validate_acceptance", script_path)
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


VALIDATOR = _load_acceptance_validator()

STATUSES_ALL_IMPLEMENTED = {f"U{index:02d}": "Implemented" for index in range(1, 9)}


def _identifier(
    name: str, *, epic: str = "E04", path: str = "src/intentguard/training.py"
) -> object:
    return VALIDATOR.Identifier(
        identifier=name,
        umbrella="W02",
        epic=epic,
        subtask="S04.2",
        implementation_path=path,
        validation_command="make lint && make test",
        expected_evidence="evidence",
    )


def _bundle(root: Path, *, runtime: dict[str, object] | None = None) -> Path:
    """Create a minimal sealed-bundle shape with the files the audit reads."""

    bundle = root / "artifacts" / "intentguard-distilbert" / "intentguard-distilbert-aaaa-bbbb"
    bundle.mkdir(parents=True)
    payload: dict[str, object] = {"run_id": "intentguard-distilbert-aaaa-bbbb"}
    if runtime is not None:
        payload["runtime"] = runtime
    (bundle / "provenance.json").write_text(json.dumps(payload), encoding="utf-8")
    for name in ("manifest.json", "threshold.json"):
        (bundle / name).write_text("{}", encoding="utf-8")
    return bundle


def _evaluation(
    root: Path, *, with_fixture: bool = True, name: str = "intentguard-evaluation-a"
) -> Path:
    directory = root / "reports" / "evaluate" / name
    directory.mkdir(parents=True)
    (directory / "comparison.json").write_text("{}", encoding="utf-8")
    if with_fixture:
        (directory / "unsupported_fixture.json").write_text("{}", encoding="utf-8")
    return directory


def _cpu_runtime(*, peak: int = 2_877_472_768) -> dict[str, object]:
    """The runtime block the real CPU training run recorded, with a tunable peak."""

    return {"cuda_available": False, "device": "cpu", "peak_memory_bytes": peak}


def _nfr001(root: Path, runtime: dict[str, object]) -> Any:
    """Return NFR-001's clause rows for a bundle carrying `runtime`.

    Typed `Any` because the audit's `Row` is only reachable through the
    path-loaded module, so there is no static type to name here.
    """

    evidence = VALIDATOR.Evidence(
        artifact_root=root,
        report_root=root,
        transformer_bundle=_bundle(root, runtime=runtime),
    )
    return VALIDATOR._nfr001_rows(_identifier("NFR-001"), STATUSES_ALL_IMPLEMENTED, evidence)


def _clause(rows: Any, marker: str) -> Any:
    """Select one NFR-001 clause row by a distinctive fragment of its clause text."""

    return next(row for row in rows if row.clause is not None and marker in row.clause)


class TestOwnershipContract:
    def test_the_real_traceability_file_has_42_primary_owners(self) -> None:
        identifiers, secondary = VALIDATOR.load_identifiers()

        assert len(identifiers) == 42
        assert secondary == 1
        prefixes = {name.split("-")[0] for name in (item.identifier for item in identifiers)}
        assert prefixes == {"T", "FR", "NFR", "AC"}

    def test_every_umbrella_status_is_readable_from_the_status_document(self) -> None:
        statuses = VALIDATOR.load_capability_status()

        assert set(statuses) >= {f"U{index:02d}" for index in range(1, 9)}
        assert all(value for value in statuses.values())


class TestEnvironmentIndependence:
    """The verdict must not depend on which machine ran the audit."""

    def test_a_missing_bundle_does_not_add_verdict_causes(self, tmp_path: Path) -> None:
        rows = [
            VALIDATOR.Row(
                identifier="AC-003",
                clause=None,
                capability="U04",
                capability_status="Implemented",
                evidence_path=None,
                executed_result="not_evidenced",
                reason="no sealed bundle here",
                applicability="unmeasured",
            )
        ]
        empty = VALIDATOR.Evidence(artifact_root=None, report_root=None)

        substantive, environmental = VALIDATOR.strict_mvp_causes(
            rows, STATUSES_ALL_IMPLEMENTED, empty
        )

        assert substantive == []
        assert len(environmental) == 1
        assert "no sealed bundle here" in environmental[0]

    def test_a_missing_measurement_counts_when_the_evidence_root_is_present(
        self, tmp_path: Path
    ) -> None:
        """With the roots available, an unmeasured claim is a real failure, not a gap."""

        complete = VALIDATOR.Evidence(
            artifact_root=tmp_path,
            report_root=tmp_path,
            transformer_bundle=_bundle(tmp_path),
            evaluation_report=_evaluation(tmp_path),
        )
        rows = [
            VALIDATOR.Row(
                identifier="AC-003",
                clause=None,
                capability="U04",
                capability_status="Implemented",
                evidence_path=None,
                executed_result="not_evidenced",
                reason="manifest absent from a bundle that is present",
                applicability="unmeasured",
            )
        ]

        substantive, environmental = VALIDATOR.strict_mvp_causes(
            rows, STATUSES_ALL_IMPLEMENTED, complete
        )

        assert environmental == []
        assert len(substantive) == 1

    def test_a_planned_capability_fails_regardless_of_environment(self, tmp_path: Path) -> None:
        statuses = {**STATUSES_ALL_IMPLEMENTED, "U08": "Planned"}
        empty = VALIDATOR.Evidence(artifact_root=None, report_root=None)

        substantive, _ = VALIDATOR.strict_mvp_causes([], statuses, empty)

        assert len(substantive) == 1
        assert "U08 is Planned" in substantive[0]

    @pytest.mark.parametrize("status", ["Partial", "Mocked", "Blocked", "Planned"])
    def test_no_non_implemented_status_can_pass(self, status: str) -> None:
        statuses = {**STATUSES_ALL_IMPLEMENTED, "U05": status}
        empty = VALIDATOR.Evidence(artifact_root=None, report_root=None)

        substantive, _ = VALIDATOR.strict_mvp_causes([], statuses, empty)

        assert any(f"U05 is {status}" in cause for cause in substantive)


class TestOutcomesStayDistinct:
    def test_not_evidenced_is_never_reported_as_passed(self, tmp_path: Path) -> None:
        empty = VALIDATOR.Evidence(artifact_root=None, report_root=None)
        row = VALIDATOR._file_row(
            _identifier("AC-003"),
            STATUSES_ALL_IMPLEMENTED,
            None,
            missing_reason="absent",
        )

        assert row.executed_result == "not_evidenced"
        assert row.as_json()["measured"] is False
        assert row.reason == "absent"
        assert empty.artifact_root is None

    def test_a_planned_capability_yields_blocked_rather_than_not_evidenced(self) -> None:
        statuses = {**STATUSES_ALL_IMPLEMENTED, "U04": "Planned"}

        row = VALIDATOR._file_row(
            _identifier("AC-003"), statuses, None, missing_reason="absent"
        )

        assert row.executed_result == "blocked"

    def test_a_present_file_is_passed_and_carries_its_path(self, tmp_path: Path) -> None:
        target = tmp_path / "evidence.json"
        target.write_text("{}", encoding="utf-8")

        row = VALIDATOR._file_row(
            _identifier("AC-003"), STATUSES_ALL_IMPLEMENTED, target, missing_reason="absent"
        )

        assert row.executed_result == "passed"
        assert row.evidence_path is not None


class TestNfr001Decomposition:
    """NFR-001's three clauses must never collapse into one row."""

    def test_all_three_clauses_are_reported_separately(self, tmp_path: Path) -> None:
        rows = _nfr001(tmp_path, _cpu_runtime())

        assert len(rows) == 3
        assert all(row.clause is not None for row in rows)
        assert len({row.clause for row in rows}) == 3

    def test_the_ram_clause_is_measured_from_recorded_provenance(self, tmp_path: Path) -> None:
        ram = _clause(_nfr001(tmp_path, _cpu_runtime()), "24 GB")

        assert ram.executed_result == "passed"
        assert ram.applicability == "measured"
        assert ram.applicability_reason is not None
        assert "2877472768" in ram.applicability_reason

    def test_a_peak_above_the_clause_fails_rather_than_passing_quietly(
        self, tmp_path: Path
    ) -> None:
        rows = _nfr001(tmp_path, _cpu_runtime(peak=30_000_000_000))
        ram = _clause(rows, "24 GB")

        assert ram.executed_result == "not_evidenced"
        assert ram.reason is not None and "exceeds" in ram.reason

    def test_the_gpu_clause_is_not_applicable_but_never_measured(self, tmp_path: Path) -> None:
        """A CPU run may excuse the GPU clause; it may not claim GPU evidence."""

        gpu = _clause(_nfr001(tmp_path, _cpu_runtime(peak=1)), "RTX")

        assert gpu.applicability == "not_applicable"
        assert gpu.executed_result == "not_evidenced"
        assert gpu.as_json()["measured"] is False
        assert gpu.reason is not None and "cuda_available false" in gpu.reason

    def test_an_unrecorded_device_leaves_the_gpu_clause_unmeasured(self, tmp_path: Path) -> None:
        """Absent a runtime record, the clause is an open question, not an excused one."""

        gpu = _clause(_nfr001(tmp_path, {"peak_memory_bytes": 1}), "RTX")

        assert gpu.applicability == "unmeasured"


class TestEvidenceResolution:
    def test_the_evaluation_run_carrying_the_fixture_wins_over_a_newer_one(
        self, tmp_path: Path
    ) -> None:
        """AC-012 is evidenced only by a run with the fixture, so newest-wins is wrong."""

        _evaluation(tmp_path, with_fixture=True, name="intentguard-evaluation-aaa")
        _evaluation(tmp_path, with_fixture=False, name="intentguard-evaluation-zzz")

        evidence = VALIDATOR.resolve_evidence(
            {"INTENTGUARD_REPORT_ROOT": str(tmp_path / "reports")}
        )

        assert evidence.evaluation_report is not None
        assert evidence.evaluation_report.name == "intentguard-evaluation-aaa"

    def test_a_redirected_artifact_root_moves_the_report_root_with_it(self, tmp_path: Path) -> None:
        """Mixing one run's artifacts with another's reports would be silent corruption."""

        _bundle(tmp_path)
        _evaluation(tmp_path)

        evidence = VALIDATOR.resolve_evidence(
            {"INTENTGUARD_ARTIFACT_ROOT": str(tmp_path / "artifacts")}
        )

        assert evidence.transformer_bundle is not None
        assert evidence.report_root == tmp_path / "reports"

    def test_absent_roots_are_recorded_as_notes_not_swallowed(self, tmp_path: Path) -> None:
        evidence = VALIDATOR.resolve_evidence(
            {"INTENTGUARD_ARTIFACT_ROOT": str(tmp_path / "missing")}
        )

        assert evidence.artifact_root is None
        assert any("no artifact root" in note for note in evidence.notes)


class TestDegradedRunsDoNotOverwriteEvidencedOnes:
    """A run that could not read the sealed evidence must not become the record."""

    @staticmethod
    def _report(*, complete: bool) -> dict[str, object]:
        return {"strict_mvp": {"evidence_complete": complete, "verdict": "FAIL"}}

    def test_a_degraded_run_refuses_to_replace_a_complete_report(self, tmp_path: Path) -> None:
        output = tmp_path / "acceptance.json"
        output.write_text(json.dumps(self._report(complete=True)), encoding="utf-8")

        refusal = VALIDATOR.would_downgrade(output, self._report(complete=False))

        assert refusal is not None and "fully-evidenced" in refusal

    def test_a_complete_run_may_replace_a_degraded_report(self, tmp_path: Path) -> None:
        output = tmp_path / "acceptance.json"
        output.write_text(json.dumps(self._report(complete=False)), encoding="utf-8")

        assert VALIDATOR.would_downgrade(output, self._report(complete=True)) is None

    def test_a_degraded_run_may_replace_another_degraded_report(self, tmp_path: Path) -> None:
        output = tmp_path / "acceptance.json"
        output.write_text(json.dumps(self._report(complete=False)), encoding="utf-8")

        assert VALIDATOR.would_downgrade(output, self._report(complete=False)) is None

    def test_a_first_run_is_never_blocked(self, tmp_path: Path) -> None:
        absent = tmp_path / "acceptance.json"

        assert VALIDATOR.would_downgrade(absent, self._report(complete=False)) is None

    def test_an_unreadable_existing_report_does_not_block_writing(self, tmp_path: Path) -> None:
        """A corrupt file is not evidence worth protecting."""

        output = tmp_path / "acceptance.json"
        output.write_text("not json", encoding="utf-8")

        assert VALIDATOR.would_downgrade(output, self._report(complete=False)) is None


class TestAc014SelfReference:
    def test_ac014_does_not_require_its_own_output_to_already_exist(self) -> None:
        """The audit's report cannot be a precondition of the run that writes it."""

        row = VALIDATOR._ac014_row(
            _identifier("AC-014", epic="E07", path="reports/acceptance.json"),
            STATUSES_ALL_IMPLEMENTED,
        )

        assert row.executed_result == "passed"
        assert row.reason is None


class TestFullAudit:
    def test_every_identifier_is_classified(self) -> None:
        identifiers, _ = VALIDATOR.load_identifiers()
        statuses = VALIDATOR.load_capability_status()
        evidence = VALIDATOR.resolve_evidence({})

        rows = VALIDATOR.audit(identifiers, statuses, evidence)

        assert {row.identifier for row in rows} == {item.identifier for item in identifiers}
        assert all(row.executed_result in {"passed", "not_evidenced", "blocked"} for row in rows)
        applicabilities = {"measured", "not_applicable", "unmeasured"}
        assert all(row.applicability in applicabilities for row in rows)

    def test_no_row_is_left_without_a_reason_when_it_lacks_evidence(self) -> None:
        identifiers, _ = VALIDATOR.load_identifiers()
        statuses = VALIDATOR.load_capability_status()
        rows = VALIDATOR.audit(identifiers, statuses, VALIDATOR.resolve_evidence({}))

        for row in rows:
            if row.executed_result != "passed":
                assert row.reason, f"{row.identifier} lacks a reason for {row.executed_result}"

    def test_the_report_is_stable_across_repeated_runs(self) -> None:
        identifiers, _ = VALIDATOR.load_identifiers()
        statuses = VALIDATOR.load_capability_status()
        evidence = VALIDATOR.resolve_evidence({})

        first = VALIDATOR.build_report(
            VALIDATOR.audit(identifiers, statuses, evidence), statuses, evidence
        )
        second = VALIDATOR.build_report(
            VALIDATOR.audit(identifiers, statuses, evidence), statuses, evidence
        )

        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_the_report_carries_no_timestamp_that_would_break_reproducibility(self) -> None:
        identifiers, _ = VALIDATOR.load_identifiers()
        statuses = VALIDATOR.load_capability_status()
        evidence = VALIDATOR.resolve_evidence({})

        report = VALIDATOR.build_report(
            VALIDATOR.audit(identifiers, statuses, evidence), statuses, evidence
        )

        serialized = json.dumps(report)
        for forbidden in ("created_at", "generated_at", "timestamp"):
            assert forbidden not in serialized

    def test_a_duplicated_primary_owner_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplicate primary ownership must fail loudly; AGENTS.md forbids it."""

        document = json.loads(VALIDATOR.TRACEABILITY_JSON.read_text(encoding="utf-8"))
        document["ownership"].append(dict(document["ownership"][0]))
        target = tmp_path / "traceability.json"
        target.write_text(json.dumps(document), encoding="utf-8")

        monkeypatch.setattr(VALIDATOR, "TRACEABILITY_JSON", target)

        with pytest.raises(VALIDATOR.AcceptanceError, match="more than one primary owner"):
            VALIDATOR.load_identifiers()

    def test_the_report_records_the_secondary_count_without_counting_it_as_primary(
        self,
    ) -> None:
        identifiers, secondary = VALIDATOR.load_identifiers()
        evidence = VALIDATOR.resolve_evidence({})
        statuses = VALIDATOR.load_capability_status()
        report = VALIDATOR.build_report(
            VALIDATOR.audit(identifiers, statuses, evidence), statuses, evidence, secondary
        )

        assert report["identifier_count"] == 42
        assert report["secondary_relationship_count"] == 1

    def test_every_must_clause_is_classified_not_left_blank(self) -> None:
        """Step 4a: no applicable MUST claim may be silently unclassified."""

        identifiers, _ = VALIDATOR.load_identifiers()
        statuses = VALIDATOR.load_capability_status()
        rows = VALIDATOR.audit(identifiers, statuses, VALIDATOR.resolve_evidence({}))

        for row in rows:
            assert row.applicability, f"{row.identifier} has no applicability classification"
            if row.applicability == "not_applicable":
                assert row.applicability_reason, (
                    f"{row.identifier} is excused without a recorded reason"
                )

    def test_the_verdict_is_fail_if_and_only_if_causes_exist(self) -> None:
        identifiers, _ = VALIDATOR.load_identifiers()
        statuses = VALIDATOR.load_capability_status()
        evidence = VALIDATOR.resolve_evidence({})
        report = VALIDATOR.build_report(
            VALIDATOR.audit(identifiers, statuses, evidence), statuses, evidence
        )

        strict = report["strict_mvp"]
        assert (strict["verdict"] == "FAIL") == bool(strict["causes"])
        assert (strict["verdict"] == "PASS") == (not strict["causes"])
