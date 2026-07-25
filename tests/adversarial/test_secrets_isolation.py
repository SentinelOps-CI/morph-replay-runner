"""Adversarial secret and isolation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.branch import run_branch_job
from runner.evidence import assert_no_secret_material, redact_text
from runner.profile import ProfileValidationError, validate_profile
from runner.providers.local_fake import LocalFakeProvider


def test_redaction_strips_tokens() -> None:
    text = "Authorization: Bearer abcdefTOKEN api_key=supersecret"
    redacted = redact_text(text)
    assert "supersecret" not in redacted
    assert "abcdefTOKEN" not in redacted or "[REDACTED]" in redacted


def test_secret_refs_never_materialize(tmp_path: Path) -> None:
    snap = json.loads(
        Path("fixtures/branch/snapshot_ref.json").read_text(encoding="utf-8")
    )
    payload = Path("fixtures/branch/snapshot.payload").read_bytes()
    provider = LocalFakeProvider(tmp_path / "prov")
    provider.register_snapshot(
        snap["snapshot_id"], payload, digest=snap["snapshot_digest"]
    )
    out = tmp_path / "branches"
    run_branch_job(
        provider=provider,
        profile_path=Path("fixtures/profile/valid_profile.json"),
        manifest_path=Path("fixtures/branch/manifest.json"),
        interventions_dir=Path("fixtures/branch/interventions"),
        parallel=4,
        out_dir=out,
    )
    for path in out.rglob("*.json"):
        blob = path.read_text(encoding="utf-8")
        assert "sk-" not in blob.lower()
        assert "password=" not in blob.lower()
        assert_no_secret_material(
            json.loads(blob) if blob.strip().startswith("{") else blob
        )


def test_profile_rejects_embedded_secret_ref_value() -> None:
    raw = json.loads(
        Path("fixtures/profile/valid_profile.json").read_text(encoding="utf-8")
    )
    raw["secret_refs"] = [{"secret_ref": "token=Bearer sk-abc"}]
    with pytest.raises(ProfileValidationError):
        validate_profile(raw)


def test_no_cross_branch_file_bleed(tmp_path: Path) -> None:
    provider = LocalFakeProvider(tmp_path)
    snap = provider.register_snapshot("s", b"shared")
    h1 = provider.clone(snap, branch_id="b1")
    h2 = provider.clone(snap, branch_id="b2")
    secret = Path(h1.root_path) / "fs" / "secret.txt"
    secret.write_text("tenant-a-secret", encoding="utf-8")
    assert not (Path(h2.root_path) / "fs" / "secret.txt").exists()
    provider.teardown(h1)
    provider.teardown(h2)
    assert not Path(h1.root_path).exists()
    assert not Path(h2.root_path).exists()
