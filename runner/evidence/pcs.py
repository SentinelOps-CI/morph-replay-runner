"""PCS RuntimeReceipt.v0 emitter and optional PF-Core gate."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runner.evidence.validate import SchemaValidationError, validate_instance
from runner.hashing import canonical_hash, sha256_bytes, sha256_text

SOURCE_REPO = "https://github.com/SentinelOps-CI/morph-replay-runner"
PRODUCER = "morph-replay-runner"
PRODUCER_VERSION = "0.1.0"

# PCS common.defs artifact_status — ReplayValidated is a PF claim class, not a
# RuntimeReceipt.status enum member.
_RECEIPT_STATUSES = frozenset({"RuntimeObserved", "RuntimeChecked", "Draft"})


class EvidenceError(RuntimeError):
    """Fail-closed evidence emission error."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def receipt_status_for_claim_class(claim_class: str, *, check_ran: bool) -> str:
    """Map branch claim class to a schema-legal RuntimeReceipt.status.

    ``ReplayValidated`` is recorded in environment metadata / PF invocation
    evidence; the receipt status upgrades only to ``RuntimeChecked`` when the
    PF-Core check actually ran.
    """
    if not check_ran:
        return "RuntimeObserved"
    if claim_class in {"RuntimeChecked", "ReplayValidated"}:
        return "RuntimeChecked"
    if claim_class == "RuntimeObserved":
        return "RuntimeObserved"
    raise EvidenceError(f"unsupported claim_class for receipt: {claim_class}")


def emit_runtime_receipt(
    *,
    receipt_id: str,
    run_id: str,
    started_at: str,
    ended_at: str,
    run_outcome: str,
    final_reason_code: str,
    source_commit: str,
    input_hashes: dict[str, str],
    output_hashes: dict[str, str],
    environment: Optional[dict[str, str]] = None,
    status: str = "RuntimeObserved",
    events_hash: Optional[str] = None,
    policy_hash: Optional[str] = None,
    trace_hash: Optional[str] = None,
    released: bool = False,
    local_dev: bool = True,
) -> dict[str, Any]:
    """Emit RuntimeReceipt.v0 with observational semantics.

    Status defaults to RuntimeObserved. RuntimeChecked only when the
    corresponding check actually ran. ReplayValidated is never a receipt
    status (PCS enum); use environment claim metadata instead.
    """
    if status not in _RECEIPT_STATUSES:
        raise EvidenceError(
            f"disallowed receipt status: {status} "
            f"(allowed={sorted(_RECEIPT_STATUSES)}; "
            "ReplayValidated is a PF claim class, not a RuntimeReceipt status)"
        )

    empty = sha256_text("")
    body: dict[str, Any] = {
        "receipt_id": receipt_id,
        "schema_version": "v0",
        "run_id": run_id,
        "environment": environment or {"provider": "local-fake"},
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
        "run_outcome": run_outcome,
        "final_reason_code": final_reason_code,
        "released": released,
        "events_hash": events_hash or empty,
        "policy_hash": policy_hash or empty,
        "trace_hash": trace_hash or empty,
        "producer": PRODUCER,
        "producer_version": PRODUCER_VERSION,
        "source_repo": SOURCE_REPO,
        "source_commit": source_commit,
        "local_dev": local_dev,
        "input_hashes": dict(sorted(input_hashes.items())),
        "output_hashes": dict(sorted(output_hashes.items())),
    }
    digest = canonical_hash(body, enforce_number_policy=True)
    body["signature_or_digest"] = digest
    try:
        validate_instance("RuntimeReceipt.v0", body)
    except SchemaValidationError as exc:
        raise EvidenceError(str(exc)) from exc
    return body


def maybe_pf_core_replay_trace(
    *,
    claim_class: str,
    trace_path: Optional[Path],
    out_dir: Path,
) -> Optional[dict[str, Any]]:
    """Invoke ``pcs pf-core replay-trace`` only when claim class applies.

    Never upgrades claim class. Returns subprocess metadata or None if skipped.
    """
    if claim_class not in {"ReplayValidated", "RuntimeChecked"}:
        return None
    if trace_path is None or not trace_path.is_file():
        raise EvidenceError(
            f"claim_class {claim_class} requires PF-Core-shaped trace file"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "pcs",
        "pf-core",
        "replay-trace",
        str(trace_path),
        "--out",
        str(out_dir),
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise EvidenceError(
            "pcs CLI not found; cannot satisfy PF-Core claim class"
        ) from exc
    record = {
        "command": cmd,
        "exit_code": completed.returncode,
        "stdout_digest": sha256_text(completed.stdout or ""),
        "stderr_digest": sha256_text(completed.stderr or ""),
        "claim_class": claim_class,
        "upgraded": False,
    }
    (out_dir / "pf_core_invocation.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if completed.returncode != 0:
        raise EvidenceError(
            f"pcs pf-core replay-trace failed with exit {completed.returncode}"
        )
    return record


def terminal_state_commitment(terminal: dict[str, Any]) -> str:
    return canonical_hash(terminal, enforce_number_policy=True)


def write_json(path: Path, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return sha256_bytes(data.encode("utf-8"))
