#!/usr/bin/env python3
"""Generate deterministic fixtures and example trees."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runner.profile.schema import (
    profile_digest,
    validate_profile,
    write_profile_with_digest,
)

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "b3018d790e3e7c622b28641c0230a61bb3b78955"


def main() -> None:
    payload = b"mrr-local-fake-snapshot-v1\n"
    snap_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    (ROOT / "fixtures/branch/snapshot.payload").write_bytes(payload)
    snap = {"snapshot_id": "snap-demo", "snapshot_digest": snap_digest}
    for path in (
        ROOT / "fixtures/branch/snapshot_ref.json",
        ROOT / "examples/hermetic-branch-n/snapshot_ref.json",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    for path in (
        ROOT / "fixtures/branch/snapshot.payload",
        ROOT / "examples/hermetic-branch-n/snapshot.payload",
    ):
        path.write_bytes(payload)

    incident = {
        "incident_id": "inc-demo",
        "incident_digest": "sha256:" + hashlib.sha256(b"inc-demo").hexdigest(),
    }
    for path in (
        ROOT / "fixtures/branch/incident_bundle.json",
        ROOT / "examples/hermetic-branch-n/incident_bundle.json",
    ):
        path.write_text(json.dumps(incident, indent=2) + "\n", encoding="utf-8")

    lock = "sha256:" + hashlib.sha256(b"lock").hexdigest()
    img = "sha256:" + hashlib.sha256(b"image").hexdigest()
    base_profile = {
        "schema_version": "mrr.ExecutionProfile.v1",
        "profile_id": "profile-demo",
        "snapshot": snap,
        "container_image_digests": [img],
        "environment": {"profile_name": "hermetic-demo", "profile_version": "1.0.0"},
        "os_runtime": {"os": "linux", "runtime": "python3.11"},
        "dependency_lock_digest": lock,
        "network_policy": {"mode": "no_network"},
        "clock_policy": {"mode": "frozen", "fixed_epoch_ms": 1700000000000},
        "random_seed_policy": {"seed": 42},
        "tool_versions": {"replay-runner": "0.1.0"},
        "budgets": {
            "cpu_cores": 2,
            "memory_mib": 1024,
            "accelerator_count": 0,
            "storage_mib": 2048,
            "wall_time_ms": 60000,
            "token_budget": 0,
            "api_call_budget": 0,
        },
        "secret_refs": [{"secret_ref": "vault/morph/api", "purpose": "optional-morph"}],
        "output_retention": {"mode": "retain", "retention_days": 30},
        "source_commit": COMMIT,
        "integrity": {"canonicalization_version": "v1"},
    }

    profile = validate_profile(base_profile)
    digest = profile_digest(profile)
    write_profile_with_digest(profile, ROOT / "fixtures/profile/valid_profile.json")
    write_profile_with_digest(
        profile, ROOT / "examples/hermetic-branch-n/execution_profile.json"
    )

    bad = dict(base_profile)
    bad["api_key"] = "sk-secret-value"
    (ROOT / "fixtures/profile/invalid_secret_value.json").write_text(
        json.dumps(bad, indent=2) + "\n", encoding="utf-8"
    )

    bad2 = dict(base_profile)
    bad2["schema_version"] = "mrr.ExecutionProfile.v999"
    (ROOT / "fixtures/profile/invalid_schema_version.json").write_text(
        json.dumps(bad2, indent=2) + "\n", encoding="utf-8"
    )

    bad3 = dict(base_profile)
    del bad3["dependency_lock_digest"]
    (ROOT / "fixtures/profile/invalid_missing_pin.json").write_text(
        json.dumps(bad3, indent=2) + "\n", encoding="utf-8"
    )

    int_dir = ROOT / "fixtures/branch/interventions"
    ex_int = ROOT / "examples/hermetic-branch-n/interventions"
    int_dir.mkdir(parents=True, exist_ok=True)
    ex_int.mkdir(parents=True, exist_ok=True)
    branches = []
    for i in range(16):
        bid = f"branch-{i:02d}"
        body = {
            "branch_id": bid,
            "intervention_id": f"iv-{i:02d}",
            "artifact_paths": [f"{bid}.json"],
            "action_sequence": ["replay", bid],
        }
        for directory in (int_dir, ex_int):
            (directory / f"{bid}.json").write_text(
                json.dumps(body, indent=2) + "\n", encoding="utf-8"
            )
        branches.append(
            {
                "branch_id": bid,
                "intervention": {
                    "intervention_id": f"iv-{i:02d}",
                    "artifact_paths": [f"{bid}.json"],
                },
                "action_sequence": ["replay", bid],
                "claim_class": "RuntimeObserved",
            }
        )

    manifest = {
        "schema_version": "mrr.BranchReplayManifest.v1",
        "manifest_id": "manifest-demo",
        "incident_ref": incident,
        "snapshot_ref": snap,
        "execution_profile_digest": digest,
        "branches": branches,
        "retry_policy": {"max_retries": 1, "retry_on": ["TIMEOUT", "ERROR"]},
        "cancellation_policy": {"cancel_others_on_failure": False},
        "branch_independence": True,
    }
    for path in (
        ROOT / "fixtures/branch/manifest.json",
        ROOT / "examples/hermetic-branch-n/manifest.json",
    ):
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    drift = dict(manifest)
    drift["execution_profile_digest"] = "sha256:" + ("b" * 64)
    (ROOT / "fixtures/branch/manifest_digest_drift.json").write_text(
        json.dumps(drift, indent=2) + "\n", encoding="utf-8"
    )
    print("profile_digest", digest)
    print("snapshot_digest", snap_digest)


if __name__ == "__main__":
    main()
