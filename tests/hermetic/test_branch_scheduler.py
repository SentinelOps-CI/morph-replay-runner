"""Branch-N scheduler acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.branch import run_branch_job
from runner.branch.manifest import load_manifest
from runner.hermeticity import HermeticityError
from runner.profile import load_profile
from runner.providers.local_fake import LocalFakeProvider


def _provider_with_fixture_snapshot(tmp_path: Path) -> LocalFakeProvider:
    snap = json.loads(
        Path("fixtures/branch/snapshot_ref.json").read_text(encoding="utf-8")
    )
    payload = Path("fixtures/branch/snapshot.payload").read_bytes()
    provider = LocalFakeProvider(tmp_path)
    provider.register_snapshot(
        snap["snapshot_id"], payload, digest=snap["snapshot_digest"]
    )
    return provider


def test_sixteen_branches_isolated(tmp_path: Path) -> None:
    provider = _provider_with_fixture_snapshot(tmp_path / "prov")
    out = tmp_path / "branches"
    summary = run_branch_job(
        provider=provider,
        profile_path=Path("fixtures/profile/valid_profile.json"),
        manifest_path=Path("fixtures/branch/manifest.json"),
        interventions_dir=Path("fixtures/branch/interventions"),
        parallel=16,
        out_dir=out,
    )
    assert len(summary["branches"]) == 16
    roots: set[str] = set()
    markers: list[str] = []
    for branch_id, result in summary["branches"].items():
        assert result["status"] == "complete", branch_id
        status = json.loads(
            (out / branch_id / "status.json").read_text(encoding="utf-8")
        )
        assert status["status"] == "complete"
        assert (out / branch_id / "runtime_receipt.json").is_file()
        assert (out / branch_id / "execution_profile.json").is_file()
        receipt = json.loads(
            (out / branch_id / "runtime_receipt.json").read_text(encoding="utf-8")
        )
        assert receipt["status"] == "RuntimeObserved"
        from runner.evidence.validate import validate_instance

        validate_instance("RuntimeReceipt.v0", receipt)
        validate_instance(
            "pip.MorphReplayReport.v1",
            json.loads(
                (out / branch_id / "morph_replay_report.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        # Isolation: each branch writes its own status content keyed by id
        marker = (out / branch_id / "status.json").read_text(encoding="utf-8")
        assert branch_id in marker
        markers.append(marker)
        roots.add(str((out / branch_id).resolve()))
    assert len(roots) == 16
    assert len(set(markers)) == 16


def test_profile_digest_drift_detected(tmp_path: Path) -> None:
    provider = _provider_with_fixture_snapshot(tmp_path / "prov")
    with pytest.raises(HermeticityError, match="digest drift"):
        run_branch_job(
            provider=provider,
            profile_path=Path("fixtures/profile/valid_profile.json"),
            manifest_path=Path("fixtures/branch/manifest_digest_drift.json"),
            interventions_dir=Path("fixtures/branch/interventions"),
            parallel=2,
            out_dir=tmp_path / "out",
        )


def test_timeout_and_retry_from_clean(tmp_path: Path) -> None:
    provider = _provider_with_fixture_snapshot(tmp_path / "prov")
    profile = load_profile("fixtures/profile/valid_profile.json")
    manifest = load_manifest("fixtures/branch/manifest.json")
    # Shrink to one timeout branch
    branch = manifest.branches[0].model_copy(
        update={"action_sequence": ["__timeout__"], "branch_id": "timeout-branch"}
    )
    manifest = manifest.model_copy(
        update={
            "branches": [branch],
            "retry_policy": manifest.retry_policy.model_copy(
                update={"max_retries": 1, "retry_on": ["TIMEOUT"]}
            ),
        }
    )
    # Force tiny timeout via profile budgets
    profile = profile.model_copy(
        update={
            "budgets": profile.budgets.model_copy(update={"wall_time_ms": 1}),
            "profile_digest": None,
        }
    )
    from runner.profile.schema import profile_digest

    digest = profile_digest(profile)
    profile = profile.model_copy(update={"profile_digest": digest})
    manifest = manifest.model_copy(update={"execution_profile_digest": digest})

    from runner.branch.scheduler import BranchScheduler, SchedulerConfig

    # Write intervention file
    iv = tmp_path / "iv"
    iv.mkdir()
    (iv / "timeout-branch.json").write_text("{}", encoding="utf-8")
    branch = manifest.branches[0].model_copy(
        update={
            "intervention": manifest.branches[0].intervention.model_copy(
                update={"artifact_paths": ["timeout-branch.json"]}
            )
        }
    )
    manifest = manifest.model_copy(update={"branches": [branch]})

    scheduler = BranchScheduler(
        provider,
        profile,
        manifest,
        SchedulerConfig(parallel=1, out_dir=tmp_path / "out", interventions_dir=iv),
    )
    summary = scheduler.run()
    result = summary["branches"]["timeout-branch"]
    assert result["terminal"] == "TIMEOUT"
    assert result["status"] == "partial"
    assert result["attempts"] >= 1


def test_partial_failure_independence(tmp_path: Path) -> None:
    provider = _provider_with_fixture_snapshot(tmp_path / "prov")
    profile = load_profile("fixtures/profile/valid_profile.json")
    manifest = load_manifest("fixtures/branch/manifest.json")
    good = manifest.branches[0]
    bad = manifest.branches[1].model_copy(
        update={"branch_id": "fail-branch", "action_sequence": ["__fail__"]}
    )
    # Fix intervention paths for fail branch file
    iv = tmp_path / "iv"
    iv.mkdir()
    (iv / good.intervention.artifact_paths[0]).write_text("{}", encoding="utf-8")
    (iv / "fail-branch.json").write_text("{}", encoding="utf-8")
    bad = bad.model_copy(
        update={
            "intervention": bad.intervention.model_copy(
                update={"artifact_paths": ["fail-branch.json"]}
            )
        }
    )
    manifest = manifest.model_copy(update={"branches": [good, bad]})
    from runner.branch.scheduler import BranchScheduler, SchedulerConfig

    summary = BranchScheduler(
        provider,
        profile,
        manifest,
        SchedulerConfig(parallel=2, out_dir=tmp_path / "out", interventions_dir=iv),
    ).run()
    assert summary["branches"][good.branch_id]["status"] == "complete"
    assert summary["branches"]["fail-branch"]["status"] == "partial"


def test_elevated_claim_class_without_pf_trace_fails(tmp_path: Path) -> None:
    provider = _provider_with_fixture_snapshot(tmp_path / "prov")
    profile = load_profile("fixtures/profile/valid_profile.json")
    manifest = load_manifest("fixtures/branch/manifest.json")
    branch = manifest.branches[0].model_copy(
        update={"claim_class": "RuntimeChecked", "branch_id": "checked-branch"}
    )
    iv = tmp_path / "iv"
    iv.mkdir()
    (iv / "checked-branch.json").write_text("{}", encoding="utf-8")
    branch = branch.model_copy(
        update={
            "intervention": branch.intervention.model_copy(
                update={"artifact_paths": ["checked-branch.json"]}
            )
        }
    )
    manifest = manifest.model_copy(update={"branches": [branch]})
    from runner.branch.scheduler import BranchScheduler, SchedulerConfig

    summary = BranchScheduler(
        provider,
        profile,
        manifest,
        SchedulerConfig(parallel=1, out_dir=tmp_path / "out", interventions_dir=iv),
    ).run()
    result = summary["branches"]["checked-branch"]
    assert result["status"] == "partial"
    err = result.get("error", "").lower()
    assert any(
        needle in err
        for needle in ("pf-core", "pf_trace", "claim_class", "pcs cli", "requires")
    )


def test_cleanup_after_success_and_failure(tmp_path: Path) -> None:
    provider = _provider_with_fixture_snapshot(tmp_path / "prov")
    out = tmp_path / "branches"
    run_branch_job(
        provider=provider,
        profile_path=Path("fixtures/profile/valid_profile.json"),
        manifest_path=Path("fixtures/branch/manifest.json"),
        interventions_dir=Path("fixtures/branch/interventions"),
        parallel=4,
        out_dir=out,
    )
    # Provider branch workdirs cleaned
    assert list((tmp_path / "prov" / "branches").glob("*")) == []
    for branch_dir in out.iterdir():
        if branch_dir.is_dir() and branch_dir.name.startswith("branch-"):
            receipt = json.loads(
                (branch_dir / "teardown_receipt.json").read_text(encoding="utf-8")
            )
            assert receipt["cleaned"] is True
            assert receipt["secrets_scrubbed"] is True
