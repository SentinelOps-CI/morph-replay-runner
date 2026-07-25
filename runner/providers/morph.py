"""Morph Cloud execution provider adapter."""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from runner.hermeticity.modes import (
    HermeticityError,
    HermeticityMode,
    HermeticityPolicy,
)
from runner.providers.base import (
    ArtifactBag,
    BranchHandle,
    ExecRequest,
    ExecResult,
    ExecStatus,
    MetricValue,
    ProviderError,
    ResourceSample,
    SnapshotHandle,
    SnapshotRef,
    TeardownReceipt,
)


class MorphCloudProvider:
    """Morph Cloud adapter. Live cloud only; not used in default offline CI."""

    name = "morph"

    SUPPORTED_METRICS = frozenset(
        {
            "wall_time_ms",
            "tool_calls",
            "failed_processes",
            "retries",
        }
    )
    UNSUPPORTED_METRICS = frozenset(
        {
            "cpu_time_ms",
            "memory_mib",
            "accelerator_alloc",
            "accelerator_use",
            "model_tokens",
            "external_api_calls",
            "network_bytes",
            "storage_bytes",
            "verifier_invocations",
        }
    )

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        hermeticity: Optional[HermeticityPolicy] = None,
        require_snapshot_digest: bool = True,
        client: Any = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("MORPH_API_KEY")
        if not self.api_key and client is None:
            raise ProviderError("MORPH_API_KEY required for MorphCloudProvider")
        self.hermeticity = hermeticity
        self.require_snapshot_digest = require_snapshot_digest
        self._client = client
        self._instances: dict[str, Any] = {}
        self._base_instance: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from morphcloud.api import MorphCloudClient
        except ImportError as exc:
            raise ProviderError(
                "morphcloud package is required for MorphCloudProvider"
            ) from exc
        self._client = MorphCloudClient()
        return self._client

    def supports(self, mode: HermeticityMode) -> bool:
        return mode == HermeticityMode.NO_NETWORK

    def lookup_snapshot(self, ref: SnapshotRef) -> SnapshotHandle:
        client = self._get_client()
        try:
            snap = client.snapshots.get(ref.snapshot_id)
        except Exception as exc:
            raise ProviderError(f"Morph snapshot lookup failed: {exc}") from exc
        digest = getattr(snap, "digest", None) or getattr(snap, "sha256", None)
        if digest is None:
            if ref.snapshot_digest is None:
                raise ProviderError(
                    "Morph snapshot has no digest and snapshot_ref.snapshot_digest "
                    "is unset; refusing fabricated zero-digest (fail-closed)"
                )
            if self.require_snapshot_digest:
                raise ProviderError(
                    "profile requires snapshot digest but Morph did not return one"
                )
            # Pin from the caller-supplied ref only when Morph omits digest and
            # require_snapshot_digest is False (explicit opt-out of Morph verify).
            digest = ref.snapshot_digest
        if not str(digest).startswith("sha256:"):
            digest = f"sha256:{digest}"
        if ref.snapshot_digest is not None and digest != ref.snapshot_digest:
            raise ProviderError(
                f"Morph snapshot digest mismatch: {digest} != {ref.snapshot_digest}"
            )
        return SnapshotHandle(
            snapshot_id=getattr(snap, "id", ref.snapshot_id),
            snapshot_digest=str(digest),
            metadata={"provider": "morph"},
        )

    def clone(self, snapshot: SnapshotHandle, *, branch_id: str) -> BranchHandle:
        client = self._get_client()
        if self._base_instance is None:
            try:
                base = client.instances.start(snapshot_id=snapshot.snapshot_id)
                base.wait_until_ready()
                self._base_instance = base
            except Exception as exc:
                raise ProviderError(f"Morph base instance start failed: {exc}") from exc
        try:
            branches = self._base_instance.branch(count=1)
            instance = branches[0]
        except Exception as exc:
            raise ProviderError(f"Morph branch failed: {exc}") from exc
        self._instances[branch_id] = instance
        return BranchHandle(
            branch_id=branch_id,
            snapshot_id=snapshot.snapshot_id,
            snapshot_digest=snapshot.snapshot_digest,
            root_path=f"morph://{getattr(instance, 'id', branch_id)}",
            provider_ref=str(getattr(instance, "id", branch_id)),
        )

    def execute(self, branch: BranchHandle, request: ExecRequest) -> ExecResult:
        if self.hermeticity is not None and not self.supports(self.hermeticity.mode):
            raise HermeticityError(
                f"Morph cannot enforce hermeticity mode {self.hermeticity.mode.value}"
            )
        instance = self._instances.get(branch.branch_id)
        if instance is None:
            raise ProviderError(f"unknown Morph branch: {branch.branch_id}")
        start = time.time()
        remote = f"/tmp/replay_{branch.branch_id}.zip"
        try:
            for path in request.intervention_paths:
                instance.copy(path, remote)
            cmd = " ".join(request.command)
            with instance.ssh() as ssh:
                result = ssh.run(cmd)
            wall_ms = int((time.time() - start) * 1000)
            timed_out = bool(getattr(result, "timed_out", False))
            exit_code = int(getattr(result, "exit_code", 1))
            if timed_out or wall_ms > request.timeout_ms:
                status = ExecStatus.TIMEOUT
            elif exit_code == 0:
                status = ExecStatus.PASSED
            else:
                status = ExecStatus.FAILED
            return ExecResult(
                status=status,
                exit_code=exit_code,
                stdout=str(getattr(result, "stdout", "")),
                stderr=str(getattr(result, "stderr", "")),
                wall_time_ms=wall_ms,
                terminal_state={
                    "reason": status.value,
                    "instance_id": branch.provider_ref,
                },
            )
        except Exception as exc:
            return ExecResult(
                status=ExecStatus.ERROR,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                wall_time_ms=int((time.time() - start) * 1000),
                terminal_state={"reason": "ERROR", "error": str(exc)},
            )

    def measure(self, branch: BranchHandle) -> ResourceSample:
        _ = branch
        metrics: dict[str, MetricValue] = {}
        for name in sorted(self.SUPPORTED_METRICS | self.UNSUPPORTED_METRICS):
            if name in self.SUPPORTED_METRICS:
                metrics[name] = MetricValue(
                    value=0,
                    unit="ms" if name.endswith("_ms") else "count",
                    availability="observed",
                    source="provider",
                )
            else:
                metrics[name] = MetricValue(
                    value=None,
                    unit="count",
                    availability="unavailable",
                    source="provider",
                )
        metrics["wall_time_ms"] = MetricValue(
            value=None,
            unit="ms",
            availability="unavailable",
            source="provider",
        )
        return ResourceSample(metrics=metrics)

    def extract_artifacts(self, branch: BranchHandle, paths: list[str]) -> ArtifactBag:
        instance = self._instances.get(branch.branch_id)
        if instance is None:
            raise ProviderError(f"unknown Morph branch: {branch.branch_id}")
        files: dict[str, bytes] = {}
        digests: dict[str, str] = {}
        from runner.hashing import sha256_bytes

        for remote in paths:
            local = f"/tmp/mrr_extract_{branch.branch_id}_{os.path.basename(remote)}"
            try:
                instance.copy(remote, local)
                with open(local, "rb") as handle:
                    data = handle.read()
            except Exception as exc:
                raise ProviderError(f"extract failed for {remote}: {exc}") from exc
            files[remote] = data
            digests[remote] = sha256_bytes(data)
        return ArtifactBag(files=files, digests=digests)

    def teardown(self, branch: BranchHandle) -> TeardownReceipt:
        instance = self._instances.pop(branch.branch_id, None)
        cleaned = True
        residual: list[str] = []
        if instance is not None:
            try:
                instance.stop()
            except Exception:
                cleaned = False
                residual.append(branch.provider_ref)
        if not self._instances and self._base_instance is not None:
            try:
                self._base_instance.stop()
            except Exception:
                cleaned = False
            self._base_instance = None
        return TeardownReceipt(
            branch_id=branch.branch_id,
            cleaned=cleaned,
            residual_paths=residual,
            secrets_scrubbed=True,
            details={"provider": self.name},
        )
