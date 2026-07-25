"""Hermeticity mode enforcement tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.hermeticity import (
    EnforcementStatus,
    HermeticityMode,
    HermeticityPolicy,
)
from runner.providers.base import ExecRequest
from runner.providers.local_fake import LocalFakeProvider
from runner.providers.morph import MorphCloudProvider


@pytest.mark.parametrize(
    "mode,env,should_fail",
    [
        (HermeticityMode.NO_NETWORK, {"HTTP_URL": "https://evil.example"}, True),
        (
            HermeticityMode.ALLOWLISTED_NETWORK,
            {"HTTP_URL": "https://allowed.example"},
            False,
        ),
        (
            HermeticityMode.ALLOWLISTED_NETWORK,
            {"HTTP_URL": "https://denied.example"},
            True,
        ),
        (
            HermeticityMode.RECORDED_RESPONSE,
            {"CASSETTE_DIGEST": "sha256:" + "c" * 64},
            False,
        ),
        (
            HermeticityMode.RECORDED_RESPONSE,
            {"CASSETTE_DIGEST": "sha256:" + "d" * 64},
            True,
        ),
        (
            HermeticityMode.SYNTHETIC_DEPENDENCY,
            {"SYNTHETIC_DEP_DIGEST": "sha256:" + "e" * 64},
            False,
        ),
        (
            HermeticityMode.SYNTHETIC_DEPENDENCY,
            {"SYNTHETIC_DEP_DIGEST": "sha256:" + "f" * 64},
            True,
        ),
    ],
)
def test_fake_mode_enforce_and_deny(
    tmp_path: Path,
    mode: HermeticityMode,
    env: dict[str, str],
    should_fail: bool,
) -> None:
    policy = HermeticityPolicy(
        mode=mode,
        allowlist_hosts=("allowed.example",),
        cassette_digest="sha256:" + "c" * 64,
        synthetic_dependency_digests=("sha256:" + "e" * 64,),
        partner_local_paths=("/approved",),
    )
    provider = LocalFakeProvider(tmp_path, hermeticity=policy)
    assert provider.supports(mode)
    snap = provider.register_snapshot("s", b"x")
    handle = provider.clone(snap, branch_id="b")
    result = provider.execute(
        handle, ExecRequest(command=["replay"], timeout_ms=1000, env=env)
    )
    if should_fail:
        assert result.status.value == "FAILED"
        assert (
            "denied" in result.stderr.lower()
            or "mismatch" in result.stderr.lower()
            or "undeclared" in result.stderr.lower()
        )
    else:
        assert result.status.value == "PASSED"


def test_partner_local_path_boundary(tmp_path: Path) -> None:
    policy = HermeticityPolicy(
        mode=HermeticityMode.PARTNER_LOCAL,
        partner_local_paths=(str(tmp_path / "approved"),),
    )
    approved = tmp_path / "approved"
    approved.mkdir()
    good = approved / "iv.json"
    good.write_text("{}", encoding="utf-8")
    bad = tmp_path / "outside.json"
    bad.write_text("{}", encoding="utf-8")
    provider = LocalFakeProvider(tmp_path / "prov", hermeticity=policy)
    snap = provider.register_snapshot("s", b"x")
    handle = provider.clone(snap, branch_id="b")
    ok = provider.execute(
        handle,
        ExecRequest(
            command=["replay"],
            timeout_ms=1000,
            intervention_paths=[str(good)],
        ),
    )
    assert ok.status.value == "PASSED"
    denied = provider.execute(
        handle,
        ExecRequest(
            command=["replay"],
            timeout_ms=1000,
            intervention_paths=[str(bad)],
        ),
    )
    assert denied.status.value == "FAILED"


def test_morph_unsupported_evidence_status() -> None:
    provider = MorphCloudProvider(api_key="x", client=object())
    assert not provider.supports(HermeticityMode.PARTNER_LOCAL)
    # Preflight pattern used by scheduler
    from runner.hermeticity.modes import HermeticityEvidence

    evidence = HermeticityEvidence(
        mode=HermeticityMode.PARTNER_LOCAL,
        status=EnforcementStatus.UNSUPPORTED,
        policy_digest="sha256:" + "a" * 64,
        probe_result={"supports": False},
        message="unsupported",
    )
    assert evidence.status == EnforcementStatus.UNSUPPORTED
