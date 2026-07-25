"""ExecutionProfile validation and digest tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.profile import (
    ProfileValidationError,
    load_profile,
    profile_digest,
    validate_profile,
)

FIX = Path("fixtures/profile")


def test_valid_profile_loads() -> None:
    profile = load_profile(FIX / "valid_profile.json")
    assert profile.profile_digest is not None
    assert profile.profile_digest.startswith("sha256:")


def test_digest_drift_on_mutation() -> None:
    profile = load_profile(FIX / "valid_profile.json")
    base = profile_digest(profile)
    mutated = profile.model_copy(
        update={"tool_versions": {**profile.tool_versions, "replay-runner": "0.1.1"}}
    )
    assert profile_digest(mutated) != base


def test_unknown_schema_version_fails() -> None:
    raw = json.loads((FIX / "invalid_schema_version.json").read_text(encoding="utf-8"))
    with pytest.raises(ProfileValidationError):
        validate_profile(raw)


def test_missing_material_pin_fails() -> None:
    raw = json.loads((FIX / "invalid_missing_pin.json").read_text(encoding="utf-8"))
    with pytest.raises(ProfileValidationError):
        validate_profile(raw)


def test_secret_values_rejected() -> None:
    raw = json.loads((FIX / "invalid_secret_value.json").read_text(encoding="utf-8"))
    with pytest.raises(ProfileValidationError):
        validate_profile(raw)


def test_secret_ref_only_allowed() -> None:
    profile = load_profile(FIX / "valid_profile.json")
    assert profile.secret_refs[0].secret_ref == "vault/morph/api"
