"""Core runner logic for executing replay bundles on Morph Cloud."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Union

from morphcloud.api import MorphCloudClient

from .models import (
    ExecutionResult,
    ExecutionSummary,
    ReplayBundle,
    RunnerConfig,
)


class ReplayRunner:
    """Main runner class for executing replay bundles on Morph Cloud."""

    def __init__(self, config: RunnerConfig) -> None:
        """Initialize the replay runner."""
        self.config = config
        self.client = MorphCloudClient()
        self.summary = ExecutionSummary()

        os.makedirs(f"{config.output_directory}/certs", exist_ok=True)
        os.makedirs(f"{config.output_directory}/logs", exist_ok=True)
        os.makedirs(f"{config.output_directory}/reports", exist_ok=True)

    def run_sync(self, bundle_paths: list[str]) -> ExecutionSummary:
        """Run replay bundles synchronously."""
        bundles = [ReplayBundle.from_path(path) for path in bundle_paths]

        print(f"Starting replay execution for {len(bundles)} bundles...")
        print(f"Using snapshot: {self.config.snapshot_id}")
        print(f"Parallel instances: {self.config.parallel_count}")

        try:
            base_snapshot = self.client.snapshots.get(self.config.snapshot_id)
            print(f"✓ Base snapshot loaded: {base_snapshot.id}")
        except Exception as exc:
            print(f"✗ Failed to load snapshot: {exc}")
            return self.summary

        try:
            base_instance = self.client.instances.start(snapshot_id=base_snapshot.id)
            base_instance.wait_until_ready()
            print(f"✓ Base instance started: {base_instance.id}")
        except Exception as exc:
            print(f"✗ Failed to start base instance: {exc}")
            return self.summary

        branches: list[Any] = []
        try:
            branches = list(base_instance.branch(count=self.config.parallel_count))
            print(f"✓ Created {len(branches)} branch instances")

            for i, bundle in enumerate(bundles):
                branch_idx = i % len(branches)
                branch = branches[branch_idx]
                result = self._execute_bundle_sync(branch, bundle, i)
                self.summary.add_result(result)
                print(f"Bundle {i+1}/{len(bundles)}: {result.status}")

            self._generate_summary_report()
        finally:
            print("Cleaning up instances...")
            for branch in branches:
                try:
                    branch.stop()
                except Exception as cleanup_exc:
                    print(f"WARNING: branch stop failed during cleanup: {cleanup_exc}")
            try:
                base_instance.stop()
            except Exception as cleanup_exc:
                print(f"WARNING: base stop failed during cleanup: {cleanup_exc}")

        return self.summary

    async def run_async(self, bundle_paths: list[str]) -> ExecutionSummary:
        """Run replay bundles asynchronously."""
        bundles = [ReplayBundle.from_path(path) for path in bundle_paths]

        print(f"Starting async replay execution for {len(bundles)} bundles...")
        print(f"Using snapshot: {self.config.snapshot_id}")
        print(f"Parallel instances: {self.config.parallel_count}")

        try:
            base_snapshot = await self.client.snapshots.aget(self.config.snapshot_id)
            print(f"✓ Base snapshot loaded: {base_snapshot.id}")
        except Exception as exc:
            print(f"✗ Failed to load snapshot: {exc}")
            return self.summary

        try:
            base_instance = await self.client.instances.astart(
                snapshot_id=base_snapshot.id
            )
            await base_instance.await_until_ready()
            print(f"✓ Base instance started: {base_instance.id}")
        except Exception as exc:
            print(f"✗ Failed to start base instance: {exc}")
            return self.summary

        branches: list[Any] = []
        try:
            branches = list(base_instance.branch(count=self.config.parallel_count))
            print(f"✓ Created {len(branches)} branch instances")

            tasks = []
            for i, bundle in enumerate(bundles):
                branch_idx = i % len(branches)
                branch = branches[branch_idx]
                tasks.append(self._execute_bundle_async(branch, bundle, i))

            results: list[Union[ExecutionResult, BaseException]] = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    error_result = ExecutionResult(
                        bundle_path=str(bundles[i].path),
                        status="ERROR",
                        execution_time_ms=0,
                        error_message=str(result),
                    )
                    self.summary.add_result(error_result)
                    print(f"Bundle {i+1}/{len(bundles)}: ERROR")
                else:
                    self.summary.add_result(result)
                    print(f"Bundle {i+1}/{len(bundles)}: {result.status}")

            await self._generate_summary_report_async()
        finally:
            print("Cleaning up instances...")
            for branch in branches:
                try:
                    await branch.astop()
                except Exception as cleanup_exc:
                    print(f"WARNING: branch astop failed during cleanup: {cleanup_exc}")
            try:
                await base_instance.astop()
            except Exception as cleanup_exc:
                print(f"WARNING: base astop failed during cleanup: {cleanup_exc}")

        return self.summary

    def _execute_bundle_sync(
        self, instance: Any, bundle: ReplayBundle, bundle_index: int
    ) -> ExecutionResult:
        """Execute a single bundle synchronously."""
        start_time = time.time()

        try:
            remote_path = f"/tmp/replay_{bundle_index}.zip"
            instance.copy(str(bundle.path), remote_path)

            if self.config.emit_cert:
                cmd = (
                    f"replay --in {remote_path} "
                    f"--emit /tmp/cert_{bundle_index}.json"
                )
            else:
                cmd = f"replay --in {remote_path}"

            with instance.ssh() as ssh:
                result = ssh.run(cmd)
                stdout = result.stdout
                stderr = result.stderr
                exit_code = result.exit_code

                if exit_code == 0:
                    status = "PASS"
                elif getattr(result, "timed_out", False):
                    status = "TIMEOUT"
                else:
                    status = "FAIL"

                cert_path = None
                if self.config.emit_cert and exit_code == 0:
                    local_cert_path = (
                        f"{self.config.output_directory}/certs/"
                        f"cert_{bundle_index}.json"
                    )
                    try:
                        instance.copy(f"/tmp/cert_{bundle_index}.json", local_cert_path)
                        cert_path = local_cert_path
                    except Exception as exc:
                        print(f"Warning: Failed to copy cert: {exc}")

                log_path = f"{self.config.output_directory}/logs/log_{bundle_index}.txt"
                with open(log_path, "w", encoding="utf-8") as handle:
                    handle.write(f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n")

                execution_time_ms = int((time.time() - start_time) * 1000)
                return ExecutionResult(
                    bundle_path=str(bundle.path),
                    bundle_hash=bundle.hash,
                    status=status,
                    execution_time_ms=execution_time_ms,
                    cert_path=cert_path,
                    log_path=log_path,
                    instance_id=getattr(instance, "id", None),
                    error_message=None if status == "PASS" else stderr,
                )
        except Exception as exc:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                bundle_path=str(bundle.path),
                bundle_hash=bundle.hash,
                status="ERROR",
                execution_time_ms=execution_time_ms,
                error_message=str(exc),
            )

    async def _execute_bundle_async(
        self, instance: Any, bundle: ReplayBundle, bundle_index: int
    ) -> ExecutionResult:
        """Execute a single bundle asynchronously (SSH still sync via Morph SDK)."""
        return await asyncio.to_thread(
            self._execute_bundle_sync, instance, bundle, bundle_index
        )

    def _generate_summary_report(self) -> None:
        """Generate summary report synchronously."""
        self.summary.end_time = datetime.now(timezone.utc).replace(tzinfo=None)
        report_path = f"{self.config.output_directory}/reports/index.json"
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(self.summary.model_dump(), handle, indent=2, default=str)

        print("\nExecution Summary:")
        print(f"  Total bundles: {self.summary.total_bundles}")
        print(f"  Successful: {self.summary.successful}")
        print(f"  Failed: {self.summary.failed}")
        print(f"  Timed out: {self.summary.timed_out}")
        print(f"  Success rate: {self.summary.success_rate:.1f}%")
        print(f"  Total time: {self.summary.total_execution_time_ms/1000:.1f}s")
        print(f"  Report saved to: {report_path}")

    async def _generate_summary_report_async(self) -> None:
        """Generate summary report asynchronously."""
        await asyncio.to_thread(self._generate_summary_report)
