"""BranchReplayManifest models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "mrr.BranchReplayManifest.v1"


class ManifestValidationError(ValueError):
    """Fail-closed manifest validation."""


class IncidentRef(BaseModel):
    incident_id: str
    incident_digest: str = Field(..., pattern=r"^sha256:[a-f0-9]{64}$")


class SnapshotRefModel(BaseModel):
    snapshot_id: str
    snapshot_digest: str = Field(..., pattern=r"^sha256:[a-f0-9]{64}$")


class InterventionSpec(BaseModel):
    intervention_id: str
    artifact_paths: list[str] = Field(default_factory=list)
    digest: Optional[str] = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")


class BranchSpec(BaseModel):
    branch_id: str
    intervention: InterventionSpec
    action_sequence: list[str] = Field(..., min_length=1)
    policy_checkpoint: Optional[str] = None
    verifier_profiles: list[str] = Field(default_factory=list)
    expected_output_classes: list[str] = Field(default_factory=list)
    claim_class: Literal[
        "runtime_observed",
        "RuntimeObserved",
        "RuntimeChecked",
        "ReplayValidated",
    ] = "RuntimeObserved"


class RetryPolicy(BaseModel):
    max_retries: int = Field(..., ge=0)
    retry_on: list[Literal["TIMEOUT", "ERROR", "FAILED"]] = Field(default_factory=list)


class CancellationPolicy(BaseModel):
    cancel_others_on_failure: bool = False


class BranchReplayManifest(BaseModel):
    schema_version: Literal["mrr.BranchReplayManifest.v1"] = (
        "mrr.BranchReplayManifest.v1"
    )
    manifest_id: str
    incident_ref: IncidentRef
    snapshot_ref: SnapshotRefModel
    execution_profile_digest: str = Field(..., pattern=r"^sha256:[a-f0-9]{64}$")
    branches: list[BranchSpec] = Field(..., min_length=1)
    retry_policy: RetryPolicy
    cancellation_policy: CancellationPolicy
    branch_independence: bool = True


def load_manifest(path: Path | str) -> BranchReplayManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_manifest(raw)


def validate_manifest(raw: dict[str, Any]) -> BranchReplayManifest:
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ManifestValidationError(
            f"unknown schema_version {raw.get('schema_version')!r}"
        )
    try:
        return BranchReplayManifest.model_validate(raw)
    except Exception as exc:
        raise ManifestValidationError(str(exc)) from exc
