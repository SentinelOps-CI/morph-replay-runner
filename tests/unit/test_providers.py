"""LocalFakeProvider and Morph capability contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.hermeticity import HermeticityError, HermeticityMode, HermeticityPolicy
from runner.providers.base import ExecRequest, ProviderError, SnapshotRef
from runner.providers.local_fake import LocalFakeProvider
from runner.providers.morph import MorphCloudProvider


def test_fake_clone_isolation(tmp_path: Path) -> None:
    provider = LocalFakeProvider(tmp_path)
    snap = provider.register_snapshot("s1", b"base-bytes")
    b1 = provider.clone(snap, branch_id="b1")
    b2 = provider.clone(snap, branch_id="b2")
    p1 = Path(b1.root_path) / "fs" / "marker"
    p1.write_text("one", encoding="utf-8")
    assert not (Path(b2.root_path) / "fs" / "marker").exists()
    assert (Path(b1.root_path) / "root.bin").read_bytes() == b"base-bytes"
    assert (Path(b2.root_path) / "root.bin").read_bytes() == b"base-bytes"


def test_fake_supports_sixteen_concurrent(tmp_path: Path) -> None:
    provider = LocalFakeProvider(tmp_path)
    snap = provider.register_snapshot("s1", b"base")
    handles = [provider.clone(snap, branch_id=f"b{i}") for i in range(16)]
    assert len(handles) == 16
    for handle in handles:
        result = provider.execute(
            handle, ExecRequest(command=["replay"], timeout_ms=1000)
        )
        assert result.status.value == "PASSED"
        provider.teardown(handle)


def test_fake_measure_unavailable_accelerator(tmp_path: Path) -> None:
    provider = LocalFakeProvider(tmp_path)
    snap = provider.register_snapshot("s1", b"base")
    handle = provider.clone(snap, branch_id="b1")
    provider.execute(handle, ExecRequest(command=["replay"], timeout_ms=1000))
    sample = provider.measure(handle)
    assert sample.metrics["accelerator_alloc"].availability == "unavailable"
    assert sample.metrics["accelerator_alloc"].value is None
    assert sample.metrics["wall_time_ms"].availability == "observed"


def test_morph_missing_capability_fail_closed() -> None:
    provider = MorphCloudProvider(api_key="test", client=object())
    assert provider.supports(HermeticityMode.NO_NETWORK)
    assert not provider.supports(HermeticityMode.ALLOWLISTED_NETWORK)
    provider.hermeticity = HermeticityPolicy(mode=HermeticityMode.ALLOWLISTED_NETWORK)
    # execute path raises before cloud call when mode unsupported
    from runner.providers.base import BranchHandle

    with pytest.raises(HermeticityError):
        provider.execute(
            BranchHandle(
                branch_id="x",
                snapshot_id="s",
                snapshot_digest="sha256:" + "a" * 64,
                root_path="morph://x",
                provider_ref="x",
            ),
            ExecRequest(command=["true"], timeout_ms=1000),
        )


def test_morph_metric_contract_documents_unavailable() -> None:
    assert "cpu_time_ms" in MorphCloudProvider.UNSUPPORTED_METRICS
    provider = MorphCloudProvider(api_key="test", client=object())
    sample = provider.measure(
        __import__("runner.providers.base", fromlist=["BranchHandle"]).BranchHandle(
            branch_id="x",
            snapshot_id="s",
            snapshot_digest="sha256:" + "a" * 64,
            root_path="morph://x",
            provider_ref="x",
        )
    )
    assert sample.metrics["cpu_time_ms"].availability == "unavailable"


def test_snapshot_digest_enforced(tmp_path: Path) -> None:
    provider = LocalFakeProvider(tmp_path)
    snap = provider.register_snapshot("s1", b"base")
    with pytest.raises(ProviderError):
        provider.lookup_snapshot(
            SnapshotRef(snapshot_id="s1", snapshot_digest="sha256:" + "0" * 64)
        )
    got = provider.lookup_snapshot(
        SnapshotRef(snapshot_id="s1", snapshot_digest=snap.snapshot_digest)
    )
    assert got.snapshot_digest == snap.snapshot_digest
