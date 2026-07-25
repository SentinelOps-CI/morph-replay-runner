"""Evidence package: digests and redaction helpers."""

from __future__ import annotations

import re
from typing import Any

from runner.evidence.pcs import (
    emit_runtime_receipt,
    maybe_pf_core_replay_trace,
    receipt_status_for_claim_class,
    terminal_state_commitment,
    write_json,
)
from runner.evidence.pip import emit_morph_replay_report, emit_transformation_record
from runner.evidence.validate import SchemaValidationError, validate_instance

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
)


def redact_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def assert_no_secret_material(payload: Any) -> None:
    blob = str(payload).lower()
    for needle in ("sk-", "bearer ", "api_key=", "password="):
        if needle in blob:
            raise ValueError(f"secret material leaked into evidence: {needle}")


__all__ = [
    "SchemaValidationError",
    "assert_no_secret_material",
    "emit_morph_replay_report",
    "emit_runtime_receipt",
    "emit_transformation_record",
    "maybe_pf_core_replay_trace",
    "receipt_status_for_claim_class",
    "redact_text",
    "terminal_state_commitment",
    "validate_instance",
    "write_json",
]
