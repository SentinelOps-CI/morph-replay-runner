"""ExecutionProfile models, validation, and digests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from runner.hashing import canonical_hash

SCHEMA_VERSION = "mrr.ExecutionProfile.v1"
FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "secret",
        "secrets",
        "password",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "secret_value",
        "credential",
        "credentials",
    }
)


class ProfileValidationError(ValueError):
    """Fail-closed profile validation error."""


class SnapshotPin(BaseModel):
    snapshot_id: str = Field(..., min_length=1)
    snapshot_digest: str = Field(..., pattern=r"^sha256:[a-f0-9]{64}$")


class EnvironmentPin(BaseModel):
    profile_name: str = Field(..., min_length=1)
    profile_version: str = Field(..., min_length=1)


class OsRuntime(BaseModel):
    os: str = Field(..., min_length=1)
    runtime: str = Field(..., min_length=1)


class NetworkPolicy(BaseModel):
    mode: Literal[
        "no_network",
        "allowlisted_network",
        "recorded_response",
        "partner_local",
        "synthetic_dependency",
    ]
    allowlist_hosts: list[str] = Field(default_factory=list)
    cassette_digest: Optional[str] = Field(
        default=None, pattern=r"^sha256:[a-f0-9]{64}$"
    )
    partner_local_paths: list[str] = Field(default_factory=list)
    synthetic_dependency_digests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _mode_pins(self) -> NetworkPolicy:
        if self.mode == "allowlisted_network" and not self.allowlist_hosts:
            raise ProfileValidationError("allowlisted_network requires allowlist_hosts")
        if self.mode == "recorded_response" and not self.cassette_digest:
            raise ProfileValidationError("recorded_response requires cassette_digest")
        if self.mode == "partner_local" and not self.partner_local_paths:
            raise ProfileValidationError("partner_local requires partner_local_paths")
        if (
            self.mode == "synthetic_dependency"
            and not self.synthetic_dependency_digests
        ):
            raise ProfileValidationError(
                "synthetic_dependency requires synthetic_dependency_digests"
            )
        return self


class ClockPolicy(BaseModel):
    mode: Literal["frozen", "offset"]
    fixed_epoch_ms: int = Field(..., ge=0)


class RandomSeedPolicy(BaseModel):
    seed: int = Field(..., ge=0)


class ModelPin(BaseModel):
    endpoint: Optional[str] = None
    version: Optional[str] = None
    local_checkpoint_digest: Optional[str] = Field(
        default=None, pattern=r"^sha256:[a-f0-9]{64}$"
    )

    @model_validator(mode="after")
    def _require_pin(self) -> ModelPin:
        if not any([self.endpoint, self.version, self.local_checkpoint_digest]):
            raise ProfileValidationError(
                "model requires endpoint/version or local_checkpoint_digest"
            )
        return self


class Budgets(BaseModel):
    cpu_cores: int = Field(..., ge=1)
    memory_mib: int = Field(..., ge=1)
    accelerator_count: int = Field(default=0, ge=0)
    storage_mib: int = Field(..., ge=1)
    wall_time_ms: int = Field(..., ge=1)
    token_budget: int = Field(..., ge=0)
    api_call_budget: int = Field(..., ge=0)


class SecretRef(BaseModel):
    secret_ref: str = Field(..., min_length=1, pattern=r"^[A-Za-z0-9_./:-]+$")
    purpose: Optional[str] = None

    @field_validator("secret_ref")
    @classmethod
    def _no_embedded_secret(cls, value: str) -> str:
        lowered = value.lower()
        if any(token in lowered for token in ("=", "bearer ", "sk-")):
            raise ProfileValidationError(
                "secret_ref must be an identifier only; values rejected"
            )
        return value


class OutputRetention(BaseModel):
    mode: Literal["ephemeral", "retain"]
    retention_days: int = Field(..., ge=0)


class IntegrityEnvelope(BaseModel):
    canonicalization_version: Literal["v1"]
    artifact_digest: Optional[str] = Field(
        default=None, pattern=r"^sha256:[a-f0-9]{64}$"
    )


class ExecutionProfile(BaseModel):
    schema_version: Literal["mrr.ExecutionProfile.v1"] = "mrr.ExecutionProfile.v1"
    profile_id: str = Field(..., min_length=1)
    profile_digest: Optional[str] = Field(
        default=None, pattern=r"^sha256:[a-f0-9]{64}$"
    )
    snapshot: SnapshotPin
    container_image_digests: list[str] = Field(..., min_length=1)
    environment: EnvironmentPin
    os_runtime: OsRuntime
    dependency_lock_digest: str = Field(..., pattern=r"^sha256:[a-f0-9]{64}$")
    network_policy: NetworkPolicy
    clock_policy: ClockPolicy
    random_seed_policy: RandomSeedPolicy
    tool_versions: dict[str, str] = Field(..., min_length=1)
    model: Optional[ModelPin] = None
    budgets: Budgets
    secret_refs: list[SecretRef] = Field(default_factory=list)
    output_retention: OutputRetention
    source_commit: str = Field(..., pattern=r"^[0-9a-f]{40}$")
    integrity: IntegrityEnvelope

    @field_validator("container_image_digests")
    @classmethod
    def _digest_items(cls, values: list[str]) -> list[str]:
        for item in values:
            if not item.startswith("sha256:") or len(item) != 71:
                raise ProfileValidationError(f"invalid image digest: {item}")
        return values

    @field_validator("tool_versions")
    @classmethod
    def _tool_versions_nonempty(cls, values: dict[str, str]) -> dict[str, str]:
        if not values:
            raise ProfileValidationError("tool_versions must be non-empty")
        for key, value in values.items():
            if not value:
                raise ProfileValidationError(f"tool_versions[{key}] empty")
        return values


def _reject_secret_values(obj: Any, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in FORBIDDEN_SECRET_KEYS:
                raise ProfileValidationError(
                    f"secret values forbidden at {path}.{key}; use secret_refs only"
                )
            if key_l in {"secret_ref", "secret_refs"}:
                _reject_secret_values(value, f"{path}.{key}")
                continue
            if isinstance(value, str) and key_l.endswith(
                ("_secret", "_token", "_password")
            ):
                raise ProfileValidationError(f"secret values forbidden at {path}.{key}")
            _reject_secret_values(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _reject_secret_values(item, f"{path}[{index}]")


def profile_digest(profile: ExecutionProfile | dict[str, Any]) -> str:
    """SHA-256 over Canonical JSON v1 with integrity/digest fields stripped."""
    if isinstance(profile, ExecutionProfile):
        data = profile.model_dump(mode="json", exclude_none=True)
    else:
        data = dict(profile)
    return canonical_hash(
        data,
        enforce_number_policy=True,
        extra_excluded=frozenset({"profile_digest", "integrity"}),
    )


def load_profile(path: Path | str) -> ExecutionProfile:
    raw_path = Path(path)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    return validate_profile(raw)


def validate_profile(raw: dict[str, Any]) -> ExecutionProfile:
    if not isinstance(raw, dict):
        raise ProfileValidationError("profile must be a JSON object")
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ProfileValidationError(
            f"unknown schema_version {version!r}; expected {SCHEMA_VERSION}"
        )
    _reject_secret_values(raw)
    try:
        profile = ExecutionProfile.model_validate(raw)
    except Exception as exc:
        raise ProfileValidationError(str(exc)) from exc

    digest = profile_digest(profile)
    if profile.profile_digest is not None and profile.profile_digest != digest:
        raise ProfileValidationError(
            f"profile_digest drift: declared {profile.profile_digest}, computed {digest}"
        )
    return profile.model_copy(update={"profile_digest": digest})


def write_profile_with_digest(profile: ExecutionProfile, path: Path | str) -> str:
    digest = profile_digest(profile)
    payload = profile.model_dump(mode="json", exclude_none=True)
    payload["profile_digest"] = digest
    payload["integrity"] = {
        "canonicalization_version": "v1",
        "artifact_digest": digest,
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return digest
