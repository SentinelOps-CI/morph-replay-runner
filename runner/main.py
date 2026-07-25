"""CLI entry point: run (compat), branch, profile, diff, validate."""

from __future__ import annotations

import asyncio
import glob
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import click
from rich.console import Console

from runner.diff import diff_branch_dirs, parse_pairs
from runner.hermeticity import HermeticityError
from runner.legacy_core import ReplayRunner
from runner.models import HttpCallbackConfig, RunnerConfig
from runner.profile import ProfileValidationError, load_profile, profile_digest
from runner.providers import ProviderError, get_provider

console = Console()


def _compat_argv(argv: list[str]) -> list[str]:
    """Preserve ``replay-runner --snapshot …`` by inserting ``run`` when needed."""
    if not argv:
        return argv
    commands = {
        "run",
        "branch",
        "profile",
        "diff",
        "validate",
        "--help",
        "-h",
        "--version",
    }
    if argv[0] in commands:
        return argv
    if argv[0].startswith("-"):
        return ["run", *argv]
    return argv


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Hermetic branch-N replay runner (observational evidence only)."""


@cli.command("run")
@click.option("--snapshot", required=True, help="Base snapshot ID or digest")
@click.option("--bundles", required=True, help="Glob for replay bundles (*.zip)")
@click.option("--parallel", "-p", default=4, type=int)
@click.option("--timeout", "-t", default=600, type=int)
@click.option("--emit-cert/--no-emit-cert", default=True)
@click.option("--out", "-o", default="./evidence")
@click.option("--async", "use_async", is_flag=True)
@click.option("--http-callback", is_flag=True)
@click.option("--http-port", default=8080, type=int)
@click.option(
    "--http-auth",
    default="none",
    type=click.Choice(["none", "api_key"]),
)
@click.option(
    "--provider",
    default="morph",
    type=click.Choice(["morph", "local-fake"]),
    help="Execution provider (default morph for legacy run path)",
)
def run_cmd(
    snapshot: str,
    bundles: str,
    parallel: int,
    timeout: int,
    emit_cert: bool,
    out: str,
    use_async: bool,
    http_callback: bool,
    http_port: int,
    http_auth: str,
    provider: str,
) -> None:
    """Compatibility ZIP-bundle Morph path (legacy)."""
    if http_callback:
        console.print(
            "[red]HTTP callback is out of scope for hermetic branch-N and "
            "is not implemented; refusing to run (fail-closed).[/red]"
        )
        sys.exit(2)

    if provider != "morph":
        console.print(
            "[red]Legacy run path requires --provider morph; "
            "use `replay-runner branch` for local-fake.[/red]"
        )
        sys.exit(2)

    if parallel < 1 or parallel > 100:
        console.print("[red]Error: Parallel count must be between 1 and 100[/red]")
        sys.exit(1)
    if timeout < 60:
        console.print("[red]Error: Timeout must be at least 60 seconds[/red]")
        sys.exit(1)

    bundle_paths = [p for p in glob.glob(bundles) if p.endswith(".zip")]
    if not bundle_paths:
        console.print(f"[red]Error: No .zip bundles matching {bundles}[/red]")
        sys.exit(1)

    config = RunnerConfig(
        snapshot_id=snapshot,
        parallel_count=parallel,
        timeout_seconds=timeout,
        emit_cert=emit_cert,
        output_directory=out,
        http_callback=HttpCallbackConfig(
            enabled=False, auth_mode=http_auth, port=http_port
        ),
    )
    runner = ReplayRunner(config)
    try:
        if use_async:
            summary = asyncio.run(runner.run_async(bundle_paths))
        else:
            summary = runner.run_sync(bundle_paths)
        console.print(
            f"successful={summary.successful} failed={summary.failed} "
            f"timed_out={summary.timed_out}"
        )
        if summary.failed or summary.timed_out:
            sys.exit(1)
    except Exception as exc:
        console.print(f"[red]Execution failed: {exc}[/red]")
        sys.exit(1)


@cli.command("branch")
@click.option("--incident", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--interventions",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--execution-profile",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--manifest", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--parallel", default=16, type=int)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option(
    "--provider",
    default="local-fake",
    type=click.Choice(["local-fake", "morph"]),
)
@click.option("--provider-root", type=click.Path(path_type=Path), default=None)
@click.option(
    "--snapshot-payload",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Raw snapshot bytes whose sha256 must match snapshot_digest",
)
@click.option(
    "--allow-partial/--fail-on-partial",
    default=False,
    help="Exit 0 when any branch is partial (default: fail closed)",
)
@click.option(
    "--ovk-check",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="If set, shell out to OVK checker on PATH (fail-closed if missing)",
)
def branch_cmd(
    incident: Path,
    snapshot: Path,
    interventions: Path,
    execution_profile: Path,
    manifest: Path | None,
    parallel: int,
    out: Path,
    provider: str,
    provider_root: Path | None,
    snapshot_payload: Path | None,
    allow_partial: bool,
    ovk_check: Path | None,
) -> None:
    """Hermetic isolated branch-N execution."""
    from runner.branch import run_branch_job

    tmp: tempfile.TemporaryDirectory[str] | None = None
    try:
        if provider == "local-fake":
            root = provider_root
            if root is None:
                tmp = tempfile.TemporaryDirectory(prefix="mrr-fake-")
                root = Path(tmp.name)
            snap_doc = json.loads(snapshot.read_text(encoding="utf-8"))
            payload_path = snapshot_payload or snapshot.with_name(
                snapshot.stem + ".payload"
            )
            if not payload_path.is_file():
                raise ProviderError(
                    f"snapshot payload required at {payload_path} "
                    "(bytes must hash to snapshot_digest)"
                )
            raw = payload_path.read_bytes()
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            if digest != snap_doc["snapshot_digest"]:
                raise ProviderError(
                    f"snapshot payload digest {digest} != pinned "
                    f"{snap_doc['snapshot_digest']}"
                )
            provider_obj = get_provider("local-fake", root=str(root))
            provider_obj.register_snapshot(  # type: ignore[attr-defined]
                snap_doc["snapshot_id"], raw, digest=digest
            )
        else:
            provider_obj = get_provider("morph")

        summary = run_branch_job(
            provider=provider_obj,
            profile_path=execution_profile,
            manifest_path=manifest,
            incident_path=incident,
            snapshot_path=snapshot,
            interventions_dir=interventions,
            parallel=parallel,
            out_dir=out,
        )
        if ovk_check is not None:
            from runner.ovk import OvkError, run_ovk_check

            try:
                run_ovk_check(target=ovk_check, out_dir=out / "ovk")
            except OvkError as exc:
                console.print(f"[red]OVK check failed: {exc}[/red]")
                sys.exit(2)

        branches = summary.get("branches", {})
        incomplete = [
            bid
            for bid, result in branches.items()
            if result.get("status") != "complete"
        ]
        console.print(
            json.dumps(
                {
                    "branches": list(branches.keys()),
                    "complete": len(branches) - len(incomplete),
                    "partial": len(incomplete),
                }
            )
        )
        if incomplete and not allow_partial:
            console.print(
                f"[red]fail-closed: {len(incomplete)} branch(es) not complete "
                f"({', '.join(sorted(incomplete))}); "
                "pass --allow-partial to accept explicit partial records[/red]"
            )
            sys.exit(3)
    except (HermeticityError, ProviderError, ProfileValidationError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)
    except Exception as exc:
        console.print(f"[red]branch failed: {exc}[/red]")
        sys.exit(1)
    finally:
        if tmp is not None:
            tmp.cleanup()


@cli.group("profile")
def profile_group() -> None:
    """ExecutionProfile utilities."""


@profile_group.command("validate")
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
def profile_validate(file_path: Path) -> None:
    try:
        profile = load_profile(file_path)
    except ProfileValidationError as exc:
        console.print(f"[red]invalid: {exc}[/red]")
        sys.exit(2)
    console.print(f"valid digest={profile.profile_digest}")


@profile_group.command("digest")
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
def profile_digest_cmd(file_path: Path) -> None:
    try:
        profile = load_profile(file_path)
    except ProfileValidationError as exc:
        console.print(f"[red]invalid: {exc}[/red]")
        sys.exit(2)
    console.print(profile.profile_digest or profile_digest(profile))


@cli.command("diff")
@click.option(
    "--branches",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option("--pairs", required=True, help="Pairs as a,b;c,d")
@click.option("--out", type=click.Path(path_type=Path), required=True)
def diff_cmd(branches: Path, pairs: str, out: Path) -> None:
    try:
        parsed = parse_pairs(pairs)
        reports = diff_branch_dirs(branches, parsed, out)
    except Exception as exc:
        console.print(f"[red]diff failed: {exc}[/red]")
        sys.exit(2)
    console.print(f"wrote {len(reports)} differential report(s) to {out}")


@cli.command("validate")
@click.option("--schema-mirrors/--no-schema-mirrors", default=True)
@click.option(
    "--fixtures/--no-fixtures",
    default=True,
    help="Validate fixture/example instances against vendored schemas",
)
@click.option(
    "--external-clis/--no-external-clis",
    default=False,
    help="Also run pcs/post-incident CLIs when installed (skip-only-when-absent)",
)
def validate_cmd(schema_mirrors: bool, fixtures: bool, external_clis: bool) -> None:
    import runpy
    import subprocess

    root = Path(__file__).resolve().parents[1]
    if schema_mirrors:
        script = root / "scripts" / "check_schema_mirrors.py"
        sys.argv = [str(script)]
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (0, None):
                raise
    if fixtures:
        fixture_script = root / "scripts" / "validate_vendored_instances.py"
        sys.argv = [str(fixture_script)]
        try:
            runpy.run_path(str(fixture_script), run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (0, None):
                raise
    if external_clis:
        optional = root / "scripts" / "optional_external_validate.py"
        completed = subprocess.run(
            [sys.executable, str(optional)], check=False, capture_output=True, text=True
        )
        console.print(completed.stdout or "")
        if completed.stderr:
            console.print(completed.stderr)
        if completed.returncode not in (0,):
            sys.exit(completed.returncode)
    console.print("ok")


def main() -> None:
    sys.argv = [sys.argv[0], *_compat_argv(sys.argv[1:])]
    cli.main(prog_name="replay-runner")


if __name__ == "__main__":
    main()
