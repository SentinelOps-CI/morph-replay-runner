"""PCS Canonical JSON v1 hashing (algorithm-compatible with pcs-core).

Do not invent a second hash. ``HASH_EXCLUDED_FIELDS`` matches pcs-core
(``signature_or_digest``, ``artifact_digest``, ``signature``). Domain digests
such as ``profile_digest`` / ``record_digest`` / ``report_digest`` must be
passed via ``extra_excluded``.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SIGNATURE_FIELD = "signature_or_digest"
ARTIFACT_DIGEST_FIELD = "artifact_digest"
SIGNATURE_OBJECT_FIELD = "signature"
# Match pcs-core HASH_EXCLUDED_FIELDS exactly. Domain digests (profile_digest,
# record_digest, report_digest, integrity) must be passed via extra_excluded.
HASH_EXCLUDED_FIELDS = frozenset(
    {
        SIGNATURE_FIELD,
        ARTIFACT_DIGEST_FIELD,
        SIGNATURE_OBJECT_FIELD,
    }
)

CANONICALIZATION_VERSION = "v1"
SAFE_INTEGER_MIN = -9007199254740991
SAFE_INTEGER_MAX = 9007199254740991
REJECTION_FLOAT_PROHIBITED = "float_prohibited"
REJECTION_INTEGER_OUT_OF_RANGE = "integer_out_of_range"
REJECTION_NEGATIVE_ZERO = "negative_zero"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented under Canonical JSON v1 rules."""

    def __init__(self, code: str, message: str, *, path: str = "$") -> None:
        self.code = code
        self.path = path
        super().__init__(message)


def assert_canonical_number_policy(value: Any, *, path: str = "$") -> None:
    """Enforce Canonical JSON v1 number policy."""
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if value < SAFE_INTEGER_MIN or value > SAFE_INTEGER_MAX:
            raise CanonicalizationError(
                REJECTION_INTEGER_OUT_OF_RANGE,
                f"{path}: integer {value} outside safe-integer range",
                path=path,
            )
        return
    if isinstance(value, float):
        if value == 0.0 and math.copysign(1.0, value) < 0.0:
            raise CanonicalizationError(
                REJECTION_NEGATIVE_ZERO,
                f"{path}: negative zero is prohibited",
                path=path,
            )
        raise CanonicalizationError(
            REJECTION_FLOAT_PROHIBITED,
            f"{path}: float values are prohibited; use decimal strings",
            path=path,
        )
    if isinstance(value, dict):
        for key, child in value.items():
            assert_canonical_number_policy(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_canonical_number_policy(child, path=f"{path}[{index}]")


def _sort_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort_keys(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_keys(item) for item in value]
    return value


def canonicalize_for_hash(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = False,
    extra_excluded: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return a copy suitable for hashing (integrity fields removed, keys sorted)."""
    excluded = (
        HASH_EXCLUDED_FIELDS
        if extra_excluded is None
        else (HASH_EXCLUDED_FIELDS | extra_excluded)
    )
    payload = {k: v for k, v in data.items() if k not in excluded}
    if enforce_number_policy:
        assert_canonical_number_policy(payload)
    sorted_payload = _sort_keys(payload)
    assert isinstance(sorted_payload, dict)
    return sorted_payload


def canonical_json_bytes(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = False,
    extra_excluded: frozenset[str] | None = None,
) -> bytes:
    canonical = canonicalize_for_hash(
        data,
        enforce_number_policy=enforce_number_policy,
        extra_excluded=extra_excluded,
    )
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def canonical_hash(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = False,
    extra_excluded: frozenset[str] | None = None,
) -> str:
    digest = hashlib.sha256(
        canonical_json_bytes(
            data,
            enforce_number_policy=enforce_number_policy,
            extra_excluded=extra_excluded,
        )
    ).hexdigest()
    return f"sha256:{digest}"


def sha256_file(path: str) -> str:
    """Return ``sha256:<hex>`` for file bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
