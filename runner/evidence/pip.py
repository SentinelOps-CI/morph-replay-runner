"""PIP MorphReplayReport + TransformationRecord emitters."""

from __future__ import annotations

from typing import Any, Literal, Optional

from runner.evidence.validate import SchemaValidationError, validate_instance
from runner.hashing import canonical_hash

MorphStatus = Literal["recorded", "mismatch", "indeterminate"]


class PipEvidenceError(ValueError):
    """Fail-closed PIP emission error."""


def emit_morph_replay_report(
    *,
    replay_id: str,
    branch_id: str,
    replay_identity_digest: str,
    input_artifact_digests: list[str],
    output_artifact_digests: list[str],
    status: MorphStatus = "recorded",
    lineage_node_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    if not output_artifact_digests:
        raise PipEvidenceError("output_artifact_digests must be non-empty")
    body: dict[str, Any] = {
        "schema_version": "pip.MorphReplayReport.v1",
        "replay_id": replay_id,
        "branch_id": branch_id,
        "replay_identity_digest": replay_identity_digest,
        "input_artifact_digests": list(input_artifact_digests),
        "output_artifact_digests": list(output_artifact_digests),
        "status": status,
        "lineage_node_ids": list(lineage_node_ids or []),
    }
    try:
        validate_instance("pip.MorphReplayReport.v1", body)
    except SchemaValidationError as exc:
        raise PipEvidenceError(str(exc)) from exc
    return body


def emit_transformation_record(
    *,
    transformation_id: str,
    transformation_type: str,
    input_artifact_digests: list[str],
    output_artifact_digest: str,
    implementation_id: str,
    implementation_version: str,
    container_digest: str,
    source_commit: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "pip.TransformationRecord.v1",
        "transformation_id": transformation_id,
        "transformation_type": transformation_type,
        "input_artifact_digests": list(input_artifact_digests),
        "output_artifact_digest": output_artifact_digest,
        "implementation_id": implementation_id,
        "implementation_version": implementation_version,
        "container_digest": container_digest,
        "source_commit": source_commit,
    }
    if notes is not None:
        body["notes"] = notes
    body["record_digest"] = canonical_hash(
        body, enforce_number_policy=True, extra_excluded=frozenset({"record_digest"})
    )
    try:
        validate_instance("pip.TransformationRecord.v1", body)
    except SchemaValidationError as exc:
        raise PipEvidenceError(str(exc)) from exc
    return body
