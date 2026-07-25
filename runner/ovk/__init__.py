"""OVK shell-out only; do not vendor OVK schemas."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from runner.hashing import sha256_file, sha256_text


class OvkError(RuntimeError):
    """OVK invocation failure."""


def resolve_ovk_cli() -> str:
    path = shutil.which("ovk") or shutil.which("open-verification-kernel")
    if path is None:
        raise OvkError("OVK CLI not found on PATH")
    return path


def run_ovk_check(
    *,
    target: Path,
    profile: Optional[str] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Shell out to OVK checker; return digests/refs only."""
    cli = resolve_ovk_cli()
    cmd = [cli, "check", str(target)]
    if profile:
        cmd.extend(["--profile", profile])
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    record: dict[str, Any] = {
        "tool": "ovk",
        "tool_version_pin": "1.2.1",
        "command": cmd,
        "exit_code": completed.returncode,
        "stdout_digest": sha256_text(completed.stdout or ""),
        "stderr_digest": sha256_text(completed.stderr or ""),
        "target_digest": sha256_file(str(target)) if target.is_file() else None,
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ovk_invocation.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if completed.returncode != 0:
        raise OvkError(f"OVK check failed with exit {completed.returncode}")
    return record
