#!/usr/bin/env python3
"""Validate fixture/example instances against vendored JSON Schemas.

Always-on offline gate — does not require pcs / post-incident CLIs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runner.evidence.pcs import emit_runtime_receipt  # noqa: E402
from runner.evidence.pip import (  # noqa: E402
    emit_morph_replay_report,
    emit_transformation_record,
)
from runner.evidence.validate import (  # noqa: E402
    ArtifactKind,
    SchemaValidationError,
    validate_instance,
    validate_json_file,
)
from runner.profile import load_profile  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SchemaValidationError(f"{path}: expected object")
    return data


def main() -> int:
    errors: list[str] = []

    def check(kind: ArtifactKind, path: Path) -> None:
        try:
            validate_json_file(kind, path)
            print(f"ok  {kind}  {path.relative_to(ROOT)}")
        except (SchemaValidationError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            print(f"FAIL {kind}  {path.relative_to(ROOT)}: {exc}", file=sys.stderr)

    for path in [
        ROOT / "fixtures/profile/valid_profile.json",
        ROOT / "examples/hermetic-branch-n/execution_profile.json",
    ]:
        try:
            profile = load_profile(path)
            payload = profile.model_dump(mode="json", exclude_none=True)
            validate_instance("mrr.ExecutionProfile.v1", payload)
            print(f"ok  mrr.ExecutionProfile.v1  {path.relative_to(ROOT)}")
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            print(f"FAIL profile {path}: {exc}", file=sys.stderr)

    check("mrr.BranchReplayManifest.v1", ROOT / "fixtures/branch/manifest.json")
    check(
        "mrr.BranchReplayManifest.v1",
        ROOT / "examples/hermetic-branch-n/manifest.json",
    )

    pip_root = ROOT / "fixtures/pip/valid_replay_linkage"
    check("pip.LineageBundle.v1", pip_root / "lineage_bundle.json")
    check("pip.MorphReplayReport.v1", pip_root / "morph_replay_report.json")

    lineage = _load(pip_root / "lineage_bundle.json")
    for transform in lineage.get("transformations", []):
        try:
            validate_instance("pip.TransformationRecord.v1", transform)
        except SchemaValidationError as exc:
            errors.append(f"lineage transform: {exc}")

    try:
        receipt = emit_runtime_receipt(
            receipt_id="ci-receipt",
            run_id="ci-run",
            started_at="2026-07-24T00:00:00Z",
            ended_at="2026-07-24T00:00:01Z",
            run_outcome="passed",
            final_reason_code="PASSED",
            source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
            input_hashes={"a": "sha256:" + "a" * 64},
            output_hashes={"b": "sha256:" + "b" * 64},
        )
        validate_instance("RuntimeReceipt.v0", receipt)
        print("ok  RuntimeReceipt.v0  (emitted)")
        emit_morph_replay_report(
            replay_id="ci-replay",
            branch_id="branch-00",
            replay_identity_digest="sha256:" + "d" * 64,
            input_artifact_digests=["sha256:" + "a" * 64],
            output_artifact_digests=["sha256:" + "d" * 64],
            status="recorded",
        )
        emit_transformation_record(
            transformation_id="t-ci",
            transformation_type="normalization",
            input_artifact_digests=["sha256:" + "a" * 64],
            output_artifact_digest="sha256:" + "b" * 64,
            implementation_id="morph-replay-runner",
            implementation_version="0.1.0",
            container_digest="sha256:" + "c" * 64,
            source_commit="b3018d790e3e7c622b28641c0230a61bb3b78955",
        )
        print("ok  PIP emitters (emitted)")
    except Exception as exc:
        errors.append(f"emitter round-trip: {exc}")
        print(f"FAIL emitter round-trip: {exc}", file=sys.stderr)

    if errors:
        print(f"{len(errors)} schema instance validation error(s)", file=sys.stderr)
        return 1
    print("vendored instance validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
