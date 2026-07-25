"""Isolated branch-N scheduler."""

from __future__ import annotations

import json
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runner.accounting.report import (
    BudgetExceededError,
    assert_unavailable_not_fabricated,
    enforce_budgets,
    sample_to_report,
)
from runner.branch.manifest import (
    BranchReplayManifest,
    BranchSpec,
    CancellationPolicy,
    IncidentRef,
    InterventionSpec,
    RetryPolicy,
    SnapshotRefModel,
    load_manifest,
)
from runner.evidence import (
    assert_no_secret_material,
    emit_morph_replay_report,
    emit_runtime_receipt,
    emit_transformation_record,
    maybe_pf_core_replay_trace,
    redact_text,
    terminal_state_commitment,
    write_json,
)
from runner.hashing import sha256_file, sha256_text
from runner.hermeticity.modes import (
    EnforcementStatus,
    HermeticityError,
    HermeticityEvidence,
    policy_from_profile_network,
)
from runner.profile.schema import ExecutionProfile, load_profile, profile_digest
from runner.providers.base import (
    ExecRequest,
    ExecResult,
    ExecStatus,
    ExecutionProvider,
    SnapshotHandle,
    SnapshotRef,
    TeardownReceipt,
)


def _iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass
class SchedulerConfig:
    parallel: int
    out_dir: Path
    interventions_dir: Optional[Path] = None
    container_digest: str = (
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )


class BranchScheduler:
    """Clone-from-canonical-snapshot branch-N executor."""

    def __init__(
        self,
        provider: ExecutionProvider,
        profile: ExecutionProfile,
        manifest: BranchReplayManifest,
        config: SchedulerConfig,
    ) -> None:
        self.provider = provider
        self.profile = profile
        self.manifest = manifest
        self.config = config
        digest = profile.profile_digest or profile_digest(profile)
        if digest != manifest.execution_profile_digest:
            raise HermeticityError(
                "execution profile digest drift vs manifest pin: "
                f"{digest} != {manifest.execution_profile_digest}"
            )
        self.profile_digest = digest
        self.policy = policy_from_profile_network(profile.network_policy)

    def preflight(self) -> HermeticityEvidence:
        mode = self.policy.mode
        if not self.provider.supports(mode):
            evidence = HermeticityEvidence(
                mode=mode,
                status=EnforcementStatus.UNSUPPORTED,
                policy_digest=self.policy.policy_digest(),
                probe_result={"provider": self.provider.name, "supports": False},
                message=f"provider {self.provider.name} cannot enforce {mode.value}",
            )
            raise HermeticityError(evidence.message)
        return HermeticityEvidence(
            mode=mode,
            status=EnforcementStatus.ENFORCED,
            policy_digest=self.policy.policy_digest(),
            probe_result={"provider": self.provider.name, "supports": True},
            message="hermeticity mode supported",
        )

    def run(self) -> dict[str, Any]:
        evidence = self.preflight()
        self.config.out_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            self.config.out_dir / "hermeticity_evidence.json", evidence.to_dict()
        )

        snapshot = self.provider.lookup_snapshot(
            SnapshotRef(
                snapshot_id=self.manifest.snapshot_ref.snapshot_id,
                snapshot_digest=self.manifest.snapshot_ref.snapshot_digest,
            )
        )
        write_json(
            self.config.out_dir / "snapshot_ref.json",
            {
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_digest": snapshot.snapshot_digest,
            },
        )

        results: dict[str, Any] = {}
        branches = list(self.manifest.branches)
        with ThreadPoolExecutor(max_workers=max(1, self.config.parallel)) as pool:
            futures = {
                pool.submit(self._run_branch, spec, snapshot): spec for spec in branches
            }
            for future in as_completed(futures):
                spec = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "branch_id": spec.branch_id,
                        "status": "partial",
                        "terminal": "ERROR",
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                    err_dir = self.config.out_dir / spec.branch_id
                    err_dir.mkdir(parents=True, exist_ok=True)
                    write_json(err_dir / "status.json", result)
                results[spec.branch_id] = result
                if (
                    self.manifest.cancellation_policy.cancel_others_on_failure
                    and result.get("terminal") in {"FAILED", "ERROR", "TIMEOUT"}
                ):
                    cancel = getattr(self.provider, "cancel", None)
                    if callable(cancel):
                        for other in branches:
                            if other.branch_id != spec.branch_id:
                                cancel(other.branch_id)

        summary = {
            "schema_version": "mrr.BranchRunSummary.v1",
            "manifest_id": self.manifest.manifest_id,
            "profile_digest": self.profile_digest,
            "snapshot_digest": snapshot.snapshot_digest,
            "branches": results,
            "non_claims": [
                "Observational/differential evidence only.",
                "No causality or remediation ranking.",
            ],
        }
        write_json(self.config.out_dir / "summary.json", summary)
        return summary

    def _resolve_intervention_paths(self, spec: BranchSpec) -> list[str]:
        paths: list[str] = []
        for rel in spec.intervention.artifact_paths:
            candidate = Path(rel)
            if not candidate.is_file() and self.config.interventions_dir is not None:
                candidate = self.config.interventions_dir / rel
            if not candidate.is_file():
                raise FileNotFoundError(f"intervention artifact missing: {rel}")
            paths.append(str(candidate.resolve()))
        return paths

    def _run_branch(self, spec: BranchSpec, snapshot: SnapshotHandle) -> dict[str, Any]:
        branch_out = self.config.out_dir / spec.branch_id
        if branch_out.exists():
            shutil.rmtree(branch_out)
        branch_out.mkdir(parents=True)

        profile_payload = self.profile.model_dump(mode="json", exclude_none=True)
        profile_payload["profile_digest"] = self.profile_digest
        write_json(branch_out / "execution_profile.json", profile_payload)
        write_json(
            branch_out / "snapshot_ref.json",
            {
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_digest": snapshot.snapshot_digest,
            },
        )

        intervention_paths = self._resolve_intervention_paths(spec)
        intervention_record = {
            "intervention_id": spec.intervention.intervention_id,
            "artifact_paths": [Path(p).name for p in intervention_paths],
            "digests": {Path(p).name: sha256_file(p) for p in intervention_paths},
        }
        write_json(branch_out / "intervention_record.json", intervention_record)

        started_at = _iso_now()
        attempt = 0
        exec_result: Optional[ExecResult] = None
        resource_report: dict[str, Any] = {}
        teardown: Optional[TeardownReceipt] = None

        while attempt <= self.manifest.retry_policy.max_retries:
            handle = self.provider.clone(
                snapshot, branch_id=f"{spec.branch_id}__attempt{attempt}"
            )
            try:
                request = ExecRequest(
                    command=list(spec.action_sequence),
                    timeout_ms=self.profile.budgets.wall_time_ms,
                    env={},
                    intervention_paths=intervention_paths,
                )
                exec_result = self.provider.execute(handle, request)
                sample = self.provider.measure(handle)
                assert_unavailable_not_fabricated(sample)
                try:
                    enforce_budgets(sample, self.profile.budgets)
                    violations: list[str] = []
                except BudgetExceededError as exc:
                    violations = str(exc).split("; ")
                    exec_result = ExecResult(
                        status=ExecStatus.FAILED,
                        exit_code=3,
                        stdout=exec_result.stdout,
                        stderr=str(exc),
                        wall_time_ms=exec_result.wall_time_ms,
                        terminal_state={
                            "reason": "BUDGET_EXCEEDED",
                            "error": str(exc),
                        },
                    )
                resource_report = sample_to_report(spec.branch_id, sample)
                resource_report["budget_violations"] = violations
            finally:
                teardown = self.provider.teardown(handle)

            assert exec_result is not None
            if exec_result.status == ExecStatus.PASSED:
                break
            if exec_result.status.value not in self.manifest.retry_policy.retry_on:
                break
            attempt += 1

        assert exec_result is not None
        assert teardown is not None
        ended_at = _iso_now()
        terminal_status = exec_result.status.value
        status_label = (
            "complete" if exec_result.status == ExecStatus.PASSED else "partial"
        )

        terminal = dict(exec_result.terminal_state or {})
        terminal.setdefault("status", terminal_status)
        terminal_commitment = terminal_state_commitment(terminal)
        write_json(branch_out / "terminal_state.json", terminal)
        write_json(
            branch_out / "terminal_commitment.json", {"digest": terminal_commitment}
        )
        write_json(branch_out / "resource_report.json", resource_report)
        write_json(
            branch_out / "teardown_receipt.json",
            {
                "branch_id": teardown.branch_id,
                "cleaned": teardown.cleaned,
                "residual_paths": teardown.residual_paths,
                "secrets_scrubbed": teardown.secrets_scrubbed,
                "details": teardown.details,
            },
        )

        logs = redact_text(
            f"STDOUT:\n{exec_result.stdout}\n\nSTDERR:\n{exec_result.stderr}\n"
        )
        (branch_out / "logs.txt").write_text(logs, encoding="utf-8")
        log_digest = sha256_text(logs)

        input_hashes = {
            "execution_profile": self.profile_digest,
            "snapshot": snapshot.snapshot_digest,
            "intervention": sha256_text(
                json.dumps(intervention_record, sort_keys=True)
            ),
        }
        output_hashes = {
            "terminal_state": terminal_commitment,
            "logs": log_digest,
        }

        from runner.evidence.pcs import EvidenceError, receipt_status_for_claim_class
        from runner.evidence.validate import SchemaValidationError, validate_instance

        pf_check_ran = False
        if spec.claim_class in {"RuntimeChecked", "ReplayValidated"}:
            # Fail closed: elevated claim classes require PF-Core trace + CLI.
            maybe_pf_core_replay_trace(
                claim_class=spec.claim_class,
                trace_path=branch_out / "pf_trace.json",
                out_dir=branch_out / "pf_core",
            )
            pf_check_ran = True
        receipt_status = receipt_status_for_claim_class(
            spec.claim_class, check_ran=pf_check_ran
        )
        claim_semantics = (
            "runtime_checked"
            if receipt_status == "RuntimeChecked"
            else "runtime_observed"
        )

        try:
            validate_instance("mrr.ResourceReport.v1", resource_report)
        except SchemaValidationError as exc:
            raise EvidenceError(str(exc)) from exc

        receipt = emit_runtime_receipt(
            receipt_id=f"receipt-{spec.branch_id}",
            run_id=f"run-{self.manifest.manifest_id}-{spec.branch_id}",
            started_at=started_at,
            ended_at=ended_at,
            run_outcome="passed" if status_label == "complete" else "failed",
            final_reason_code=terminal_status,
            source_commit=self.profile.source_commit,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            environment={
                "provider": self.provider.name,
                "claim_class": spec.claim_class,
                "claim_semantics": claim_semantics,
            },
            status=receipt_status,
        )
        write_json(branch_out / "runtime_receipt.json", receipt)

        morph_report = emit_morph_replay_report(
            replay_id=f"replay-{self.manifest.manifest_id}",
            branch_id=spec.branch_id,
            replay_identity_digest=terminal_commitment,
            input_artifact_digests=[self.profile_digest, snapshot.snapshot_digest],
            output_artifact_digests=[terminal_commitment],
            status="recorded" if status_label == "complete" else "indeterminate",
        )
        write_json(branch_out / "morph_replay_report.json", morph_report)

        transform = emit_transformation_record(
            transformation_id=f"t-{spec.branch_id}",
            transformation_type="synthetic_variant_derivation",
            input_artifact_digests=[snapshot.snapshot_digest],
            output_artifact_digest=terminal_commitment,
            implementation_id="morph-replay-runner",
            implementation_version="0.1.0",
            container_digest=self.config.container_digest,
            source_commit=self.profile.source_commit,
            notes="branch replay transform",
        )
        write_json(branch_out / "transformation_record.json", transform)

        branch_report = {
            "branch_id": spec.branch_id,
            "process_action": list(spec.action_sequence),
            "authorization": None,
            "side_effect": None,
            "reward": None,
            "verifier_decision": None,
            "unresolved_external_dependency": None,
            "attempts": attempt + 1,
            "teardown_cleaned": teardown.cleaned,
        }
        write_json(branch_out / "branch_report.json", branch_report)

        digests = {
            "execution_profile": self.profile_digest,
            "runtime_receipt": receipt["signature_or_digest"],
            "terminal_state": terminal_commitment,
            "logs": log_digest,
        }
        write_json(branch_out / "digests.json", digests)
        status_payload = {
            "status": status_label,
            "terminal": terminal_status,
            "branch_id": spec.branch_id,
            "complete_evidence": status_label == "complete",
        }
        write_json(branch_out / "status.json", status_payload)
        assert_no_secret_material(status_payload)
        assert_no_secret_material(receipt)

        return {
            "branch_id": spec.branch_id,
            "status": status_label,
            "terminal": terminal_status,
            "digests": digests,
            "attempts": attempt + 1,
        }


def run_branch_job(
    *,
    provider: ExecutionProvider,
    profile_path: Path,
    manifest_path: Optional[Path] = None,
    incident_path: Optional[Path] = None,
    snapshot_path: Optional[Path] = None,
    interventions_dir: Optional[Path] = None,
    parallel: int = 4,
    out_dir: Path,
    manifest: Optional[BranchReplayManifest] = None,
) -> dict[str, Any]:
    profile = load_profile(profile_path)
    if manifest is None:
        if manifest_path is not None:
            manifest = load_manifest(manifest_path)
        else:
            if incident_path is None or snapshot_path is None:
                raise ValueError("manifest or incident+snapshot required")
            if interventions_dir is None:
                raise ValueError("--interventions required when manifest omitted")
            incident = json.loads(incident_path.read_text(encoding="utf-8"))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            branch_specs: list[BranchSpec] = []
            for path in sorted(interventions_dir.glob("*.json")):
                data = json.loads(path.read_text(encoding="utf-8"))
                branch_specs.append(
                    BranchSpec(
                        branch_id=data["branch_id"],
                        intervention=InterventionSpec(
                            intervention_id=data.get("intervention_id", path.stem),
                            artifact_paths=data.get("artifact_paths", [path.name]),
                        ),
                        action_sequence=data.get("action_sequence", ["replay"]),
                    )
                )
            if not branch_specs:
                raise ValueError("no intervention specs found")
            digest = profile.profile_digest or profile_digest(profile)
            manifest = BranchReplayManifest(
                manifest_id=incident.get("incident_id", "incident"),
                incident_ref=IncidentRef(
                    incident_id=incident["incident_id"],
                    incident_digest=incident["incident_digest"],
                ),
                snapshot_ref=SnapshotRefModel(
                    snapshot_id=snapshot["snapshot_id"],
                    snapshot_digest=snapshot["snapshot_digest"],
                ),
                execution_profile_digest=digest,
                branches=branch_specs,
                retry_policy=RetryPolicy(max_retries=0, retry_on=["TIMEOUT", "ERROR"]),
                cancellation_policy=CancellationPolicy(cancel_others_on_failure=False),
                branch_independence=True,
            )

    from runner.providers.local_fake import LocalFakeProvider

    if isinstance(provider, LocalFakeProvider):
        if provider.hermeticity is None:
            provider.hermeticity = policy_from_profile_network(profile.network_policy)
        provider.fixed_epoch_ms = profile.clock_policy.fixed_epoch_ms
        provider.seed = profile.random_seed_policy.seed

    scheduler = BranchScheduler(
        provider,
        profile,
        manifest,
        SchedulerConfig(
            parallel=parallel,
            out_dir=out_dir,
            interventions_dir=interventions_dir,
            container_digest=profile.container_image_digests[0],
        ),
    )
    return scheduler.run()
