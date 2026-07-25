"""Provider protocol types and ExecutionProvider Protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional, Protocol, runtime_checkable

from runner.hermeticity.modes import HermeticityMode


class ProviderError(RuntimeError):
    """Fail-closed provider error."""


@dataclass(frozen=True)
class SnapshotRef:
    snapshot_id: str
    snapshot_digest: Optional[str] = None


@dataclass(frozen=True)
class SnapshotHandle:
    snapshot_id: str
    snapshot_digest: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BranchHandle:
    branch_id: str
    snapshot_id: str
    snapshot_digest: str
    root_path: str
    provider_ref: str


@dataclass(frozen=True)
class ExecRequest:
    command: list[str]
    timeout_ms: int
    env: dict[str, str] = field(default_factory=dict)
    workdir: Optional[str] = None
    intervention_paths: list[str] = field(default_factory=list)


class ExecStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


@dataclass
class ExecResult:
    status: ExecStatus
    exit_code: int
    stdout: str
    stderr: str
    wall_time_ms: int
    terminal_state: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


MetricAvailability = Literal["observed", "unavailable", "not_applicable"]


@dataclass(frozen=True)
class MetricValue:
    value: Optional[float | int | str]
    unit: str
    availability: MetricAvailability
    source: Literal["provider", "runner", "guest"]


@dataclass
class ResourceSample:
    metrics: dict[str, MetricValue]


@dataclass
class ArtifactBag:
    files: dict[str, bytes]
    digests: dict[str, str]


@dataclass
class TeardownReceipt:
    branch_id: str
    cleaned: bool
    residual_paths: list[str] = field(default_factory=list)
    secrets_scrubbed: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ExecutionProvider(Protocol):
    """Backend-neutral execution provider."""

    name: str

    def supports(self, mode: HermeticityMode) -> bool:
        """Return True if the provider can enforce the hermeticity mode."""

    def lookup_snapshot(self, ref: SnapshotRef) -> SnapshotHandle: ...

    def clone(self, snapshot: SnapshotHandle, *, branch_id: str) -> BranchHandle: ...

    def execute(self, branch: BranchHandle, request: ExecRequest) -> ExecResult: ...

    def measure(self, branch: BranchHandle) -> ResourceSample: ...

    def extract_artifacts(
        self, branch: BranchHandle, paths: list[str]
    ) -> ArtifactBag: ...

    def teardown(self, branch: BranchHandle) -> TeardownReceipt: ...
