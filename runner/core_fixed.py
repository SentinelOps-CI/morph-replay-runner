"""Core runner logic for executing replay bundles on Morph Cloud."""

import asyncio
import json
import os
import time
from typing import List

from morphcloud.api import MorphCloudClient
from morphcloud.exceptions import MorphCloudError

from .models import (
    ExecutionResult,
    ExecutionSummary,
    ReplayBundle,
    RunnerConfig,
)


class ReplayRunner:
    """Main runner class for executing replay bundles on Morph Cloud."""

    def __init__(self, config: RunnerConfig):
        """Initialize the replay runner."""
        self.config = config
        self.client = MorphCloudClient()
        self.summary = ExecutionSummary()

        # Ensure output directories exist
        os.makedirs(f"{config.output_directory}/certs", exist_ok=True)
        os.makedirs(f"{config.output_directory}/logs", exist_ok=True)
        os.makedirs(f"{config.output_directory}/reports", exist_ok=True)

    def run_sync(self, bundle_paths: List[str]) -> ExecutionSummary:
        """Run replay bundles synchronously."""
        bundles = [ReplayBundle.from_path(path) for path in bundle_paths]

        print(f"Starting replay execution for {len(bundles)} bundles...")
        print(f"Using snapshot: {self.config.snapshot_id}")
        print(f"Parallel instances: {self.config.parallel_count}")

        # Get base snapshot
        try:
            base_snapshot = self.client.snapshots.get(self.config.snapshot_id)
            print(f"✓ Base snapshot loaded: {base_snapshot.id}")
        except MorphCloudError as e:
            print(f"✗ Failed to load snapshot: {e}")
            return self.summary

        # Start base instance
        try:
            base_instance = self.client.instances.start(snapshot_id=base_snapshot.id)
            base_instance.wait_until_ready()
            print(f"✓ Base instance started: {base_instance.id}")
        except MorphCloudError as e:
            print(f"✗ Failed to start base instance: {e}")
            return self.summary

        try:
            # Create branch instances
            branches = base_instance.branch(count=self.config.parallel_count)
            print(f"✓ Created {len(branches)} branch instances")

            # Execute bundles in parallel
            results = []
            for i, bundle in enumerate(bundles):
                branch_idx = i % len(branches)
                branch = branches[branch_idx]

                result = self._execute_bundle_sync(branch, bundle, i)
                results.append(result)
                self.summary.add_result(result)

                print(f"Bundle {i+1}/{len(bundles)}: {result.status}")

            # Generate summary report
            self._generate_summary_report()

        finally:
            # Cleanup instances
            print("Cleaning up instances...")
            for branch in branches:
                try:
                    branch.stop()
                except Exception:
                    pass
            try:
                base_instance.stop()
            except Exception:
                pass

        return self.summary

    async def run_async(self, bundle_paths: List[str]) -> ExecutionSummary:
        """Run replay bundles asynchronously."""
        bundles = [ReplayBundle.from_path(path) for path in bundle_paths]

        print(f"Starting async replay execution for {len(bundles)} bundles...")
        print(f"Using snapshot: {self.config.snapshot_id}")
        print(f"Parallel instances: {self.config.parallel_count}")

        # Get base snapshot
        try:
            base_snapshot = await self.client.snapshots.aget(self.config.snapshot_id)
            print(f"✓ Base snapshot loaded: {base_snapshot.id}")
        except MorphCloudError as e:
            print(f"✗ Failed to load snapshot: {e}")
            return self.summary

        # Start base instance
        try:
            base_instance = await self.client.instances.astart(
                snapshot_id=base_snapshot.id
            )
            await base_instance.await_until_ready()
            print(f"✓ Base instance started: {base_instance.id}")
        except MorphCloudError as e:
            print(f"✗ Failed to start base instance: {e}")
            return self.summary

        try:
            # Create branch instances
            branches = base_instance.branch(count=self.config.parallel_count)
            print(f"✓ Created {len(branches)} branch instances")

            # Execute bundles in parallel
            tasks = []
            for i, bundle in enumerate(bundles):
                branch_idx = i % len(branches)
                branch = branches[branch_idx]

                task = self._execute_bundle_async(branch, bundle, i)
                tasks.append(task)

            # Wait for all executions to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Create error result
                    error_result = ExecutionResult(
                        bundle_path=str(bundles[i].path),
                        status="ERROR",
                        execution_time_ms=0,
                        error_message=str(result),
                    )
                    self.summary.add_result(error_result)
                else:
                    self.summary.add_result(result)

                print(f"Bundle {i+1}/{len(bundles)}: {result.status}")

            # Generate summary report
            await self._generate_summary_report_async()

        finally:
            # Cleanup instances
            print("Cleaning up instances...")
            for branch in branches:
                try:
                    await branch.astop()
                except Exception:
                    pass
            try:
                await base_instance.astop()
            except Exception:
                pass

        return self.summary

    def _execute_bundle_sync(
        self, instance, bundle: ReplayBundle, bundle_index: int
    ) -> ExecutionResult:
        """Execute a single bundle synchronously."""
        start_time = time.time()

        try:
            # Copy bundle to instance
            remote_path = f"/tmp/replay_{bundle_index}.zip"
            instance.copy(str(bundle.path), remote_path)

            # Execute replay command
            if self.config.emit_cert:
                cmd = (
                    f"replay --in {remote_path} "
                    f"--emit /tmp/cert_{bundle_index}.json"
                )
            else:
                cmd = f"replay --in {remote_path}"

            with instance.ssh() as ssh:
                result = ssh.run(cmd)

                # Collect output
                stdout = result.stdout
                stderr = result.stderr
                exit_code = result.exit_code

                # Determine status
                if exit_code == 0:
                    status = "PASS"
                elif result.timed_out:
                    status = "TIMEOUT"
                else:
                    status = "FAIL"

                # Copy certificate if generated
                cert_path = None
                if self.config.emit_cert and exit_code == 0:
                    local_cert_path = (
                        f"{self.config.output_directory}/certs/"
                        f"cert_{bundle_index}.json"
                    )
                    try:
                        instance.copy(f"/tmp/cert_{bundle_index}.json", local_cert_path)
                        cert_path = local_cert_path
                    except Exception as e:
                        print(f"Warning: Failed to copy cert: {e}")

                # Save log
                log_path = (
                    f"{self.config.output_directory}/logs/" f"log_{bundle_index}.txt"
                )
                with open(log_path, "w") as f:
                    f.write(f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n")

                execution_time_ms = int((time.time() - start_time) * 1000)

                return ExecutionResult(
                    bundle_path=str(bundle.path),
                    bundle_hash=bundle.hash,
                    status=status,
                    execution_time_ms=execution_time_ms,
                    cert_path=cert_path,
                    log_path=log_path,
                    instance_id=instance.id,
                    error_message=None if status == "PASS" else stderr,
                )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                bundle_path=str(bundle.path),
                bundle_hash=bundle.hash,
                status="ERROR",
                execution_time_ms=execution_time_ms,
                error_message=str(e),
            )

    async def _execute_bundle_async(
        self, instance, bundle: ReplayBundle, bundle_index: int
    ) -> ExecutionResult:
        """Execute a single bundle asynchronously."""
        start_time = time.time()

        try:
            # Copy bundle to instance
            remote_path = f"/tmp/replay_{bundle_index}.zip"
            instance.copy(str(bundle.path), remote_path)

            # Execute replay command
            if self.config.emit_cert:
                cmd = (
                    f"replay --in {remote_path} "
                    f"--emit /tmp/cert_{bundle_index}.json"
                )
            else:
                cmd = f"replay --in {remote_path}"

            with instance.ssh() as ssh:
                result = ssh.run(cmd)

                # Collect output
                stdout = result.stdout
                stderr = result.stderr
                exit_code = result.exit_code

                # Determine status
                if exit_code == 0:
                    status = "PASS"
                elif result.timed_out:
                    status = "TIMEOUT"
                else:
                    status = "FAIL"

                # Copy certificate if generated
                cert_path = None
                if self.config.emit_cert and exit_code == 0:
                    local_cert_path = (
                        f"{self.config.output_directory}/certs/"
                        f"cert_{bundle_index}.json"
                    )
                    try:
                        instance.copy(f"/tmp/cert_{bundle_index}.json", local_cert_path)
                        cert_path = local_cert_path
                    except Exception as e:
                        print(f"Warning: Failed to copy cert: {e}")

                # Save log
                log_path = (
                    f"{self.config.output_directory}/logs/" f"log_{bundle_index}.txt"
                )
                with open(log_path, "w") as f:
                    f.write(f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n")

                execution_time_ms = int((time.time() - start_time) * 1000)

                return ExecutionResult(
                    bundle_path=str(bundle.path),
                    bundle_hash=bundle.hash,
                    status=status,
                    execution_time_ms=execution_time_ms,
                    cert_path=cert_path,
                    log_path=log_path,
                    instance_id=instance.id,
                    error_message=None if status == "PASS" else stderr,
                )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                bundle_path=str(bundle.path),
                bundle_hash=bundle.hash,
                status="ERROR",
                execution_time_ms=execution_time_ms,
                error_message=str(e),
            )

    def _generate_summary_report(self):
        """Generate summary report synchronously."""
        self.summary.end_time = None  # Will be set by validator

        report_path = f"{self.config.output_directory}/reports/index.json"
        with open(report_path, "w") as f:
            json.dump(self.summary.dict(), f, indent=2, default=str)

        print("\nExecution Summary:")
        print(f"  Total bundles: {self.summary.total_bundles}")
        print(f"  Successful: {self.summary.successful}")
        print(f"  Failed: {self.summary.failed}")
        print(f"  Timed out: {self.summary.timed_out}")
        print(f"  Success rate: {self.summary.success_rate:.1f}%")
        print(f"  Total time: " f"{self.summary.total_execution_time_ms/1000:.1f}s")
        print(f"  Report saved to: {report_path}")

    async def _generate_summary_report_async(self):
        """Generate summary report asynchronously."""
        self.summary.end_time = None  # Will be set by validator

        report_path = f"{self.config.output_directory}/reports/index.json"
        with open(report_path, "w") as f:
            json.dump(self.summary.dict(), f, indent=2, default=str)

        print("\nExecution Summary:")
        print(f"  Total bundles: {self.summary.total_bundles}")
        print(f"  Successful: {self.summary.successful}")
        print(f"  Failed: {self.summary.failed}")
        print(f"  Timed out: {self.summary.timed_out}")
        print(f"  Success rate: {self.summary.success_rate:.1f}%")
        print(f"  Total time: " f"{self.summary.total_execution_time_ms/1000:.1f}s")
        print(f"  Report saved to: {report_path}")
