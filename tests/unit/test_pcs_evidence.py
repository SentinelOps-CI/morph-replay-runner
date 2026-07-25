"""PCS RuntimeReceipt emission tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.evidence.pcs import EvidenceError, emit_runtime_receipt


def test_runtime_receipt_observational() -> None:
    receipt = emit_runtime_receipt(
        receipt_id="r1",
        run_id="run-1",
        started_at="2026-07-24T00:00:00Z",
        ended_at="2026-07-24T00:00:01Z",
        run_outcome="passed",
        final_reason_code="PASSED",
        source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
        input_hashes={"a": "sha256:" + "a" * 64},
        output_hashes={"b": "sha256:" + "b" * 64},
    )
    assert receipt["status"] == "RuntimeObserved"
    assert receipt["schema_version"] == "v0"
    assert receipt["signature_or_digest"].startswith("sha256:")


def test_disallowed_status_without_check() -> None:
    with pytest.raises(EvidenceError):
        emit_runtime_receipt(
            receipt_id="r1",
            run_id="run-1",
            started_at="2026-07-24T00:00:00Z",
            ended_at="2026-07-24T00:00:01Z",
            run_outcome="passed",
            final_reason_code="PASSED",
            source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
            input_hashes={},
            output_hashes={},
            status="CertificateChecked",
        )


def test_receipt_validates_full_vendored_schema() -> None:
    from runner.evidence.validate import validate_instance

    receipt = emit_runtime_receipt(
        receipt_id="r1",
        run_id="run-1",
        started_at="2026-07-24T00:00:00Z",
        ended_at="2026-07-24T00:00:01Z",
        run_outcome="passed",
        final_reason_code="PASSED",
        source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
        input_hashes={"a": "sha256:" + "a" * 64},
        output_hashes={"b": "sha256:" + "b" * 64},
    )
    validate_instance("RuntimeReceipt.v0", receipt)


def test_receipt_schema_shape_against_mirror() -> None:
    schema = json.loads(
        Path("schemas/pcs/RuntimeReceipt.v0.schema.json").read_text(encoding="utf-8")
    )
    assert schema["title"] == "RuntimeReceipt.v0"
    required = set(schema["required"])
    receipt = emit_runtime_receipt(
        receipt_id="r1",
        run_id="run-1",
        started_at="2026-07-24T00:00:00Z",
        ended_at="2026-07-24T00:00:01Z",
        run_outcome="passed",
        final_reason_code="PASSED",
        source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
        input_hashes={"a": "sha256:" + "a" * 64},
        output_hashes={"b": "sha256:" + "b" * 64},
    )
    assert required.issubset(receipt.keys())
