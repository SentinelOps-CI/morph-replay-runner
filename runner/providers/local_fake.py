"""Deterministic LocalFakeProvider for offline hermetic branch-N execution."""

from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Optional

from runner.hashing import sha256_bytes, sha256_file, sha256_text
from runner.hermeticity.modes import (
    HermeticityError,
    HermeticityMode,
    HermeticityPolicy,
    host_allowed,
    path_within_partner,
)
from runner.providers.base import (
    ArtifactBag,
    BranchHandle,
    ExecRequest,
    ExecResult,
    ExecStatus,
    ExecutionProvider,
    MetricValue,
    ProviderError,
    ResourceSample,
    SnapshotHandle,
    SnapshotRef,
    TeardownReceipt,
)


class LocalFakeProvider:
    """Filesystem sandbox provider with deterministic clocks/seeds and isolation.

    Supports >=16 concurrent branches. No outbound network unless hermeticity
    mode allows recorded fixtures or allowlisted hosts (simulated only).
    """

    name = "local-fake"

    def __init__(
        self,
        root: Path | str,
        *,
        hermeticity: Optional[HermeticityPolicy] = None,
        fixed_epoch_ms: int = 1_700_000_000_000,
        seed: int = 0,
        accelerator_configured: bool = False,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir = self.root / "snapshots"
        self.branches_dir = self.root / "branches"
        self.snapshots_dir.mkdir(exist_ok=True)
        self.branches_dir.mkdir(exist_ok=True)
        self.hermeticity = hermeticity
        self.fixed_epoch_ms = fixed_epoch_ms
        self.seed = seed
        self.accelerator_configured = accelerator_configured
        self._lock = threading.RLock()
        self._branch_state: dict[str, dict[str, Any]] = {}
        self._network_attempts: list[dict[str, Any]] = []

    def register_snapshot(
        self, snapshot_id: str, content: bytes, *, digest: Optional[str] = None
    ) -> SnapshotHandle:
        snap_dir = self.snapshots_dir / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        payload = snap_dir / "root.bin"
        payload.write_bytes(content)
        computed = sha256_bytes(content)
        if digest is not None and digest != computed:
            raise ProviderError(
                f"snapshot digest mismatch for {snapshot_id}: {digest} != {computed}"
            )
        meta = {
            "snapshot_id": snapshot_id,
            "snapshot_digest": computed,
            "size": len(content),
        }
        (snap_dir / "meta.json").write_text(
            json.dumps(meta, sort_keys=True) + "\n", encoding="utf-8"
        )
        return SnapshotHandle(
            snapshot_id=snapshot_id, snapshot_digest=computed, metadata=meta
        )

    def supports(self, mode: HermeticityMode) -> bool:
        return mode in {
            HermeticityMode.NO_NETWORK,
            HermeticityMode.ALLOWLISTED_NETWORK,
            HermeticityMode.RECORDED_RESPONSE,
            HermeticityMode.PARTNER_LOCAL,
            HermeticityMode.SYNTHETIC_DEPENDENCY,
        }

    def lookup_snapshot(self, ref: SnapshotRef) -> SnapshotHandle:
        snap_dir = self.snapshots_dir / ref.snapshot_id
        meta_path = snap_dir / "meta.json"
        payload = snap_dir / "root.bin"
        if not meta_path.is_file() or not payload.is_file():
            raise ProviderError(f"snapshot not found: {ref.snapshot_id}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        digest = meta["snapshot_digest"]
        if ref.snapshot_digest is not None and ref.snapshot_digest != digest:
            raise ProviderError(
                f"snapshot digest mismatch: profile requires {ref.snapshot_digest}, "
                f"provider has {digest}"
            )
        recomputed = sha256_file(str(payload))
        if recomputed != digest:
            raise ProviderError(f"snapshot content drift for {ref.snapshot_id}")
        return SnapshotHandle(
            snapshot_id=ref.snapshot_id, snapshot_digest=digest, metadata=meta
        )

    def clone(self, snapshot: SnapshotHandle, *, branch_id: str) -> BranchHandle:
        with self._lock:
            src = self.snapshots_dir / snapshot.snapshot_id / "root.bin"
            if not src.is_file():
                raise ProviderError(f"missing snapshot bytes: {snapshot.snapshot_id}")
            branch_root = self.branches_dir / branch_id
            if branch_root.exists():
                raise ProviderError(f"branch already exists: {branch_id}")
            branch_root.mkdir(parents=True)
            dest = branch_root / "root.bin"
            shutil.copyfile(src, dest)
            fs = branch_root / "fs"
            fs.mkdir()
            (fs / "SNAPSHOT_ID").write_text(snapshot.snapshot_id, encoding="utf-8")
            (fs / "SNAPSHOT_DIGEST").write_text(
                snapshot.snapshot_digest, encoding="utf-8"
            )
            (fs / "BRANCH_ID").write_text(branch_id, encoding="utf-8")
            (fs / "SEED").write_text(str(self.seed), encoding="utf-8")
            (fs / "CLOCK_EPOCH_MS").write_text(
                str(self.fixed_epoch_ms), encoding="utf-8"
            )
            self._branch_state[branch_id] = {
                "created_at_ms": self.fixed_epoch_ms,
                "wall_ms": 0,
                "cpu_ms": 0,
                "storage_bytes": dest.stat().st_size,
                "tool_calls": 0,
                "api_calls": 0,
                "network_bytes": 0,
                "retries": 0,
                "failed_processes": 0,
                "verifier_invocations": 0,
                "cancelled": False,
            }
            return BranchHandle(
                branch_id=branch_id,
                snapshot_id=snapshot.snapshot_id,
                snapshot_digest=snapshot.snapshot_digest,
                root_path=str(branch_root),
                provider_ref=f"local-fake:{branch_id}",
            )

    def _enforce_pre_exec(self, request: ExecRequest) -> None:
        policy = self.hermeticity
        if policy is None:
            return
        for key, value in request.env.items():
            if key.startswith("HTTP") or key.endswith("_URL"):
                host = value
                if "://" in value:
                    host = value.split("://", 1)[1].split("/", 1)[0]
                allowed = host_allowed(host, policy)
                self._network_attempts.append(
                    {"host": host, "allowed": allowed, "mode": policy.mode.value}
                )
                if not allowed and policy.mode in {
                    HermeticityMode.NO_NETWORK,
                    HermeticityMode.ALLOWLISTED_NETWORK,
                    HermeticityMode.RECORDED_RESPONSE,
                    HermeticityMode.PARTNER_LOCAL,
                    HermeticityMode.SYNTHETIC_DEPENDENCY,
                }:
                    raise HermeticityError(
                        f"network denied by hermeticity mode {policy.mode.value}: {host}"
                    )
        if policy.mode == HermeticityMode.PARTNER_LOCAL:
            for path in request.intervention_paths:
                if not path_within_partner(path, policy):
                    raise HermeticityError(
                        f"path outside partner_local boundary: {path}"
                    )
        if policy.mode == HermeticityMode.SYNTHETIC_DEPENDENCY:
            # Only declared synthetic digests may be referenced via env SYNTHETIC_DEP
            declared = set(policy.synthetic_dependency_digests)
            synth = request.env.get("SYNTHETIC_DEP_DIGEST")
            if synth and synth not in declared:
                raise HermeticityError(
                    f"undeclared synthetic dependency digest: {synth}"
                )
        if policy.mode == HermeticityMode.RECORDED_RESPONSE:
            cassette = request.env.get("CASSETTE_DIGEST")
            if cassette and cassette != policy.cassette_digest:
                raise HermeticityError("cassette digest mismatch")

    def execute(self, branch: BranchHandle, request: ExecRequest) -> ExecResult:
        with self._lock:
            state = self._branch_state.get(branch.branch_id)
            if state is None:
                raise ProviderError(f"unknown branch: {branch.branch_id}")
            if state.get("cancelled"):
                return ExecResult(
                    status=ExecStatus.CANCELLED,
                    exit_code=130,
                    stdout="",
                    stderr="cancelled",
                    wall_time_ms=0,
                    terminal_state={"reason": "CANCELLED"},
                )

            start = time.perf_counter()
            try:
                self._enforce_pre_exec(request)
            except HermeticityError as exc:
                state["failed_processes"] += 1
                return ExecResult(
                    status=ExecStatus.FAILED,
                    exit_code=2,
                    stdout="",
                    stderr=str(exc),
                    wall_time_ms=0,
                    terminal_state={"reason": "HERMETICITY_DENIED", "error": str(exc)},
                )

            branch_root = Path(branch.root_path)
            fs = branch_root / "fs"
            for src in request.intervention_paths:
                src_path = Path(src)
                if not src_path.is_file():
                    state["failed_processes"] += 1
                    return ExecResult(
                        status=ExecStatus.ERROR,
                        exit_code=1,
                        stdout="",
                        stderr=f"intervention missing: {src}",
                        wall_time_ms=0,
                        terminal_state={"reason": "INTERVENTION_MISSING"},
                    )
                dest = fs / "interventions" / src_path.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_path, dest)

            # Deterministic simulated work proportional to seed + command length
            work_units = self.seed + sum(len(part) for part in request.command)
            simulated_ms = min(request.timeout_ms, 1 + (work_units % 50))
            if request.timeout_ms <= 0:
                return ExecResult(
                    status=ExecStatus.TIMEOUT,
                    exit_code=124,
                    stdout="",
                    stderr="timeout",
                    wall_time_ms=0,
                    terminal_state={"reason": "TIMEOUT"},
                )
            if simulated_ms >= request.timeout_ms and request.command[:1] == [
                "__timeout__"
            ]:
                state["failed_processes"] += 1
                return ExecResult(
                    status=ExecStatus.TIMEOUT,
                    exit_code=124,
                    stdout="",
                    stderr="timeout",
                    wall_time_ms=request.timeout_ms,
                    terminal_state={"reason": "TIMEOUT"},
                )

            result_path = fs / "result.json"
            terminal = {
                "branch_id": branch.branch_id,
                "snapshot_digest": branch.snapshot_digest,
                "command": list(request.command),
                "seed": self.seed,
                "clock_epoch_ms": self.fixed_epoch_ms,
                "status": "PASSED",
            }
            if request.command[:1] == ["__fail__"]:
                terminal["status"] = "FAILED"
                state["failed_processes"] += 1
                status = ExecStatus.FAILED
                exit_code = 1
                stderr = "forced failure"
            else:
                status = ExecStatus.PASSED
                exit_code = 0
                stderr = ""

            result_path.write_text(
                json.dumps(terminal, sort_keys=True) + "\n", encoding="utf-8"
            )
            log_path = fs / "stdout.log"
            log_path.write_text(
                f"cmd={' '.join(request.command)}\nstatus={terminal['status']}\n",
                encoding="utf-8",
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000) or simulated_ms
            state["wall_ms"] += elapsed_ms
            state["cpu_ms"] += max(1, elapsed_ms // 2)
            state["tool_calls"] += 1
            state["storage_bytes"] = sum(
                p.stat().st_size for p in branch_root.rglob("*") if p.is_file()
            )
            return ExecResult(
                status=status,
                exit_code=exit_code,
                stdout=log_path.read_text(encoding="utf-8"),
                stderr=stderr,
                wall_time_ms=elapsed_ms,
                terminal_state=terminal,
                artifacts={
                    "result.json": str(result_path),
                    "stdout.log": str(log_path),
                },
            )

    def measure(self, branch: BranchHandle) -> ResourceSample:
        state = self._branch_state.get(branch.branch_id)
        if state is None:
            raise ProviderError(f"unknown branch: {branch.branch_id}")
        accel: MetricValue
        if self.accelerator_configured:
            accel = MetricValue(
                value=0, unit="count", availability="observed", source="provider"
            )
        else:
            accel = MetricValue(
                value=None,
                unit="count",
                availability="unavailable",
                source="provider",
            )
        return ResourceSample(
            metrics={
                "wall_time_ms": MetricValue(
                    value=state["wall_ms"],
                    unit="ms",
                    availability="observed",
                    source="provider",
                ),
                "cpu_time_ms": MetricValue(
                    value=state["cpu_ms"],
                    unit="ms",
                    availability="observed",
                    source="provider",
                ),
                "memory_mib": MetricValue(
                    value=64,
                    unit="MiB",
                    availability="observed",
                    source="provider",
                ),
                "accelerator_alloc": accel,
                "accelerator_use": accel,
                "model_tokens": MetricValue(
                    value=0,
                    unit="tokens",
                    availability="observed",
                    source="provider",
                ),
                "tool_calls": MetricValue(
                    value=state["tool_calls"],
                    unit="count",
                    availability="observed",
                    source="provider",
                ),
                "external_api_calls": MetricValue(
                    value=state["api_calls"],
                    unit="count",
                    availability="observed",
                    source="provider",
                ),
                "network_bytes": MetricValue(
                    value=state["network_bytes"],
                    unit="bytes",
                    availability="observed",
                    source="provider",
                ),
                "storage_bytes": MetricValue(
                    value=state["storage_bytes"],
                    unit="bytes",
                    availability="observed",
                    source="provider",
                ),
                "retries": MetricValue(
                    value=state["retries"],
                    unit="count",
                    availability="observed",
                    source="provider",
                ),
                "failed_processes": MetricValue(
                    value=state["failed_processes"],
                    unit="count",
                    availability="observed",
                    source="provider",
                ),
                "verifier_invocations": MetricValue(
                    value=state["verifier_invocations"],
                    unit="count",
                    availability="observed",
                    source="provider",
                ),
            }
        )

    def extract_artifacts(self, branch: BranchHandle, paths: list[str]) -> ArtifactBag:
        branch_root = Path(branch.root_path)
        files: dict[str, bytes] = {}
        digests: dict[str, str] = {}
        for rel in paths:
            path = branch_root / rel
            if not path.is_file():
                raise ProviderError(f"artifact missing: {rel}")
            data = path.read_bytes()
            files[rel] = data
            digests[rel] = sha256_bytes(data)
        return ArtifactBag(files=files, digests=digests)

    def teardown(self, branch: BranchHandle) -> TeardownReceipt:
        with self._lock:
            branch_root = Path(branch.root_path)
            residual: list[str] = []
            cleaned = False
            if branch_root.exists():
                shutil.rmtree(branch_root)
                cleaned = not branch_root.exists()
                if not cleaned:
                    residual.append(str(branch_root))
            self._branch_state.pop(branch.branch_id, None)
            return TeardownReceipt(
                branch_id=branch.branch_id,
                cleaned=cleaned,
                residual_paths=residual,
                secrets_scrubbed=True,
                details={"provider": self.name},
            )

    def cancel(self, branch_id: str) -> None:
        with self._lock:
            state = self._branch_state.get(branch_id)
            if state is not None:
                state["cancelled"] = True

    def network_attempt_log(self) -> list[dict[str, Any]]:
        return list(self._network_attempts)

    def enforce_capability_or_fail(self, mode: HermeticityMode) -> None:
        if not self.supports(mode):
            raise HermeticityError(
                f"provider {self.name} does not support hermeticity mode {mode.value}"
            )


def ensure_protocol(provider: LocalFakeProvider) -> ExecutionProvider:
    """Type helper asserting LocalFakeProvider satisfies ExecutionProvider."""
    return provider


def branch_isolation_marker(branch: BranchHandle) -> str:
    return sha256_text(
        f"{branch.branch_id}:{branch.snapshot_digest}:{branch.root_path}"
    )
