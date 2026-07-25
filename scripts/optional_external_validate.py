#!/usr/bin/env python3
"""Optional deeper semantic gates via sibling CLIs.

Skip-only-when-absent is JUSTIFIED: default CI already enforces conformance via
vendored JSON Schema instance validation (``validate_vendored_instances.py``).
When ``pcs`` / ``post-incident`` are on PATH (or installed via extras), this
script runs their CLI checks and fails closed on non-zero exit.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    completed = subprocess.run(cmd, check=False, cwd=str(ROOT))
    return int(completed.returncode)


def main() -> int:
    skipped: list[str] = []
    failed = 0

    pcs = shutil.which("pcs")
    if pcs:
        # Prefer a previously emitted receipt; otherwise emit one for pcs validate.
        receipt_candidates = list(
            (ROOT / "branches-smoke").glob("*/runtime_receipt.json")
        )
        if receipt_candidates:
            code = _run([pcs, "validate", str(receipt_candidates[0])])
            if code != 0:
                failed += 1
        else:
            print(
                "pcs present but no runtime_receipt fixture to validate; "
                "vendored schema gate remains authoritative"
            )
            skipped.append("pcs-validate-no-receipt")
    else:
        skipped.append("pcs-cli-absent")
        print(
            "SKIP pcs validate: CLI not on PATH "
            "(justified — vendored RuntimeReceipt.v0 schema validation always runs)"
        )

    post = shutil.which("post-incident")
    if post:
        lineage = ROOT / "fixtures/pip/valid_replay_linkage/lineage_bundle.json"
        report = ROOT / "fixtures/pip/valid_replay_linkage/morph_replay_report.json"
        code = _run([post, "lineage", "validate", str(lineage)])
        if code != 0:
            failed += 1
        # replay-check may require a release_dir layout; attempt and fail closed.
        release_dir = ROOT / "fixtures/pip/valid_replay_linkage"
        code = _run(
            [
                post,
                "replay-check",
                str(release_dir),
                "--replay-report",
                str(report),
            ]
        )
        if code != 0:
            failed += 1
    else:
        skipped.append("post-incident-cli-absent")
        print(
            "SKIP post-incident replay-check: CLI not on PATH "
            "(justified — vendored PIP schema + linkage tests always run)"
        )

    print(f"optional_external_validate skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
