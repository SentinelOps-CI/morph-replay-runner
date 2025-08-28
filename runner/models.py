"""Data models for the Morph Replay Runner."""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class HttpCallbackConfig(BaseModel):
    """Configuration for HTTP callback services."""

    enabled: bool = False
    auth_mode: str = "none"  # "none" or "api_key"
    port: int = 8080


class RunnerConfig(BaseModel):
    """Configuration for the replay runner."""

    snapshot_id: str = Field(..., description="Base snapshot ID or digest")
    parallel_count: int = Field(
        ..., ge=1, le=100, description="Number of parallel instances"
    )
    timeout_seconds: int = Field(..., ge=60, description="Execution timeout in seconds")
    emit_cert: bool = True
    output_directory: str = "./evidence"
    http_callback: HttpCallbackConfig = Field(default_factory=HttpCallbackConfig)

    @validator("output_directory")
    def validate_output_directory(cls, v):
        """Ensure output directory exists and is writable."""
        os.makedirs(v, exist_ok=True)
        return v


class ExecutionResult(BaseModel):
    """Result of a single replay execution."""

    bundle_path: str = Field(..., description="Path to the replay bundle file")
    bundle_hash: Optional[str] = None
    status: str = Field(..., description="Execution status: PASS, FAIL, ERROR, TIMEOUT")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    cert_path: Optional[str] = None
    log_path: Optional[str] = None
    instance_id: Optional[str] = None
    error_message: Optional[str] = None
    http_service_url: Optional[str] = None

    @validator("bundle_hash", pre=True, always=True)
    def compute_bundle_hash(cls, v, values):
        """Compute SHA-256 hash of the bundle file if not provided."""
        if v is None and "bundle_path" in values:
            bundle_path = values["bundle_path"]
            if os.path.exists(bundle_path):
                with open(bundle_path, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()
        return v


class ExecutionSummary(BaseModel):
    """Summary of all replay executions."""

    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    total_bundles: int = 0
    successful: int = 0
    failed: int = 0
    timed_out: int = 0
    total_execution_time_ms: int = 0
    average_execution_time_ms: float = 0.0
    results: List[ExecutionResult] = Field(default_factory=list)

    @validator("end_time", pre=True, always=True)
    def set_end_time(cls, v):
        """Set end time if not provided."""
        if v is None:
            return datetime.utcnow()
        return v

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_bundles == 0:
            return 0.0
        return (self.successful / self.total_bundles) * 100

    def add_result(self, result: ExecutionResult):
        """Add an execution result and update summary statistics."""
        self.results.append(result)
        self.total_bundles = len(self.results)

        # Update counters
        if result.status == "PASS":
            self.successful += 1
        elif result.status == "FAIL":
            self.failed += 1
        elif result.status == "TIMEOUT":
            self.timed_out += 1

        # Update timing statistics
        self.total_execution_time_ms += result.execution_time_ms
        self.average_execution_time_ms = (
            self.total_execution_time_ms / self.total_bundles
        )


class ReplayBundle(BaseModel):
    """Represents a replay bundle to be executed."""

    path: Path
    size: int
    hash: str
    created_at: datetime

    @classmethod
    def from_path(cls, bundle_path: str) -> "ReplayBundle":
        """Create a ReplayBundle from a file path."""
        path = Path(bundle_path)
        if not path.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_path}")

        stat = path.stat()
        with open(path, "rb") as f:
            bundle_hash = hashlib.sha256(f.read()).hexdigest()

        return cls(
            path=path,
            size=stat.st_size,
            hash=bundle_hash,
            created_at=datetime.fromtimestamp(stat.st_mtime),
        )
