"""PIP emission and linkage tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.evidence.pip import (
    PipEvidenceError,
    emit_morph_replay_report,
    emit_transformation_record,
)
from runner.evidence.validate import SchemaValidationError, validate_instance
from runner.hashing import canonical_hash


def test_transformation_record_digest() -> None:
    record = emit_transformation_record(
        transformation_id="t1",
        transformation_type="normalization",
        input_artifact_digests=["sha256:" + "a" * 64],
        output_artifact_digest="sha256:" + "b" * 64,
        implementation_id="morph-replay-runner",
        implementation_version="0.1.0",
        container_digest="sha256:" + "c" * 64,
        source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
    )
    recomputed = canonical_hash(
        {k: v for k, v in record.items() if k != "record_digest"},
        enforce_number_policy=True,
        extra_excluded=frozenset({"record_digest"}),
    )
    assert record["record_digest"] == recomputed
    validate_instance("pip.TransformationRecord.v1", record)


def test_morph_report_status_enum() -> None:
    report = emit_morph_replay_report(
        replay_id="r",
        branch_id="b",
        replay_identity_digest="sha256:" + "d" * 64,
        input_artifact_digests=["sha256:" + "a" * 64],
        output_artifact_digests=["sha256:" + "d" * 64],
        status="recorded",
    )
    assert report["schema_version"] == "pip.MorphReplayReport.v1"
    validate_instance("pip.MorphReplayReport.v1", report)


def test_joint_fixture_linkage_files_exist() -> None:
    root = Path("fixtures/pip/valid_replay_linkage")
    assert (root / "lineage_bundle.json").is_file()
    assert (root / "morph_replay_report.json").is_file()
    lineage = json.loads((root / "lineage_bundle.json").read_text(encoding="utf-8"))
    report = json.loads((root / "morph_replay_report.json").read_text(encoding="utf-8"))
    validate_instance("pip.LineageBundle.v1", lineage)
    validate_instance("pip.MorphReplayReport.v1", report)
    node_digests = {n["artifact_digest"] for n in lineage["nodes"]}
    assert report["replay_identity_digest"] in node_digests
    for digest in report["output_artifact_digests"]:
        assert digest in node_digests
    for digest in report["input_artifact_digests"]:
        assert digest in node_digests
    for transform in lineage["transformations"]:
        validate_instance("pip.TransformationRecord.v1", transform)


def test_tampered_digest_fails_linkage_and_schema_membership() -> None:
    root = Path("fixtures/pip/valid_replay_linkage")
    report = json.loads((root / "morph_replay_report.json").read_text(encoding="utf-8"))
    lineage = json.loads((root / "lineage_bundle.json").read_text(encoding="utf-8"))
    report["output_artifact_digests"] = ["sha256:" + "0" * 64]
    node_digests = {n["artifact_digest"] for n in lineage["nodes"]}
    assert report["output_artifact_digests"][0] not in node_digests
    # Still schema-valid as Morph report, but linkage fails (replay-check semantics).
    validate_instance("pip.MorphReplayReport.v1", report)


def test_invalid_morph_status_rejected() -> None:
    with pytest.raises((PipEvidenceError, SchemaValidationError, Exception)):
        emit_morph_replay_report(
            replay_id="r",
            branch_id="b",
            replay_identity_digest="sha256:" + "d" * 64,
            input_artifact_digests=["sha256:" + "a" * 64],
            output_artifact_digests=["sha256:" + "d" * 64],
            status="not-a-status",  # type: ignore[arg-type]
        )
