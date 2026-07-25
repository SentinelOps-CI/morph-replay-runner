"""Always-on vendored JSON Schema instance validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.evidence.pcs import EvidenceError, emit_runtime_receipt
from runner.evidence.validate import (
    SchemaValidationError,
    validate_instance,
    validate_json_file,
)


def test_runtime_receipt_validates_against_vendored_schema() -> None:
    receipt = emit_runtime_receipt(
        receipt_id="r1",
        run_id="run-1",
        started_at="2026-07-24T00:00:00Z",
        ended_at="2026-07-24T00:00:01Z",
        run_outcome="passed",
        final_reason_code="PASSED",
        source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
        input_hashes={"a": "sha256:" + "a" * 64},
        output_hashes={"b": "sha256:" + "b" * 64},
    )
    validate_instance("RuntimeReceipt.v0", receipt)


def test_replay_validated_rejected_as_receipt_status() -> None:
    with pytest.raises(EvidenceError, match="ReplayValidated"):
        emit_runtime_receipt(
            receipt_id="r1",
            run_id="run-1",
            started_at="2026-07-24T00:00:00Z",
            ended_at="2026-07-24T00:00:01Z",
            run_outcome="passed",
            final_reason_code="PASSED",
            source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
            input_hashes={},
            output_hashes={},
            status="ReplayValidated",
        )


def test_tampered_receipt_fails_schema() -> None:
    receipt = emit_runtime_receipt(
        receipt_id="r1",
        run_id="run-1",
        started_at="2026-07-24T00:00:00Z",
        ended_at="2026-07-24T00:00:01Z",
        run_outcome="passed",
        final_reason_code="PASSED",
        source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
        input_hashes={"a": "sha256:" + "a" * 64},
        output_hashes={"b": "sha256:" + "b" * 64},
    )
    receipt["status"] = "NotARealStatus"
    with pytest.raises(SchemaValidationError):
        validate_instance("RuntimeReceipt.v0", receipt)


def test_pip_linkage_fixtures_schema_valid() -> None:
    root = Path("fixtures/pip/valid_replay_linkage")
    validate_json_file("pip.LineageBundle.v1", root / "lineage_bundle.json")
    validate_json_file("pip.MorphReplayReport.v1", root / "morph_replay_report.json")


def test_mrr_manifest_and_profile_schema_valid() -> None:
    validate_json_file(
        "mrr.BranchReplayManifest.v1", Path("fixtures/branch/manifest.json")
    )
    profile = json.loads(
        Path("fixtures/profile/valid_profile.json").read_text(encoding="utf-8")
    )
    validate_instance("mrr.ExecutionProfile.v1", profile)
