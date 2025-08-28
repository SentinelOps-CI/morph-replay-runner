"""Main CLI entry point for the Morph Replay Runner."""

import asyncio
import glob
import sys

import click
from rich.console import Console

from .core import ReplayRunner
from .models import RunnerConfig

console = Console()


@click.command()
@click.option(
    "--snapshot",
    required=True,
    help="Base snapshot ID or digest containing sidecar + replay tools",
)
@click.option(
    "--bundles",
    required=True,
    help="Glob pattern for replay bundles (e.g., ./replays/*.zip)",
)
@click.option(
    "--parallel",
    "-p",
    default=4,
    type=int,
    help="Number of parallel instances (default: 4)",
)
@click.option(
    "--timeout",
    "-t",
    default=600,
    type=int,
    help="Execution timeout in seconds (default: 600)",
)
@click.option(
    "--emit-cert/--no-emit-cert",
    default=True,
    help="Emit CERT-V1 JSON certificates (default: True)",
)
@click.option(
    "--out",
    "-o",
    default="./evidence",
    help="Output directory for evidence collection (default: ./evidence)",
)
@click.option(
    "--async", "use_async", is_flag=True, help="Use asynchronous execution mode"
)
@click.option(
    "--http-callback", is_flag=True, help="Enable HTTP callback service for demos"
)
@click.option(
    "--http-port",
    default=8080,
    type=int,
    help="Port for HTTP callback service (default: 8080)",
)
@click.option(
    "--http-auth",
    default="none",
    type=click.Choice(["none", "api_key"]),
    help="HTTP callback authentication mode (default: none)",
)
@click.version_option(version="0.1.0")
def main(
    snapshot,
    bundles,
    parallel,
    timeout,
    emit_cert,
    out,
    use_async,
    http_callback,
    http_port,
    http_auth,
):
    """Morph Replay Runner - Execute TRACE-REPLAY-KIT bundles with branch-N parallelism."""

    # Validate inputs
    if parallel < 1 or parallel > 100:
        console.print("[red]Error: Parallel count must be between 1 and 100[/red]")
        sys.exit(1)

    if timeout < 60:
        console.print("[red]Error: Timeout must be at least 60 seconds[/red]")
        sys.exit(1)

    # Resolve bundle paths
    bundle_paths = glob.glob(bundles)
    if not bundle_paths:
        console.print(f"[red]Error: No bundles found matching pattern: {bundles}[/red]")
        sys.exit(1)

    # Filter for zip files
    bundle_paths = [p for p in bundle_paths if p.endswith(".zip")]
    if not bundle_paths:
        console.print(
            f"[red]Error: No .zip files found matching pattern: {bundles}[/red]"
        )
        sys.exit(1)

    console.print(f"[green]Found {len(bundle_paths)} replay bundles[/green]")
    for path in bundle_paths:
        console.print(f"  [blue]{path}[/blue]")

    # Create configuration
    config = RunnerConfig(
        snapshot_id=snapshot,
        parallel_count=parallel,
        timeout_seconds=timeout,
        emit_cert=emit_cert,
        output_directory=out,
        http_callback={
            "enabled": http_callback,
            "auth_mode": http_auth,
            "port": http_port,
        },
    )

    # Create runner
    runner = ReplayRunner(config)

    # Display configuration
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  Snapshot: [blue]{snapshot}[/blue]")
    console.print(f"  Parallel instances: [blue]{parallel}[/blue]")
    console.print(f"  Timeout: [blue]{timeout}s[/blue]")
    console.print(f"  Emit certificates: [blue]{emit_cert}[/blue]")
    console.print(f"  Output directory: [blue]{out}[/blue]")
    console.print(f"  HTTP callback: [blue]{http_callback}[/blue]")
    if http_callback:
        console.print(f"  HTTP port: [blue]{http_port}[/blue]")
        console.print(f"  HTTP auth: [blue]{http_auth}[/blue]")

    # Execute
    try:
        if use_async:
            console.print("\n[bold]Starting asynchronous execution...[/bold]")
            summary = asyncio.run(runner.run_async(bundle_paths))
        else:
            console.print("\n[bold]Starting synchronous execution...[/bold]")
            summary = runner.run_sync(bundle_paths)

        # Display final results
        console.print("\n[bold green]Execution completed![/bold green]")
        console.print(f"  Total bundles: [blue]{summary.total_bundles}[/blue]")
        console.print(f"  Successful: [green]{summary.successful}[/green]")
        console.print(f"  Failed: [red]{summary.failed}[/red]")
        console.print(f"  Timed out: [yellow]{summary.timed_out}[/yellow]")
        console.print(f"  Success rate: [blue]{summary.success_rate:.1f}%[/blue]")
        console.print(
            f"  Total time: "
            f"[blue]{summary.total_execution_time_ms/1000:.1f}s[/blue]"
        )

        # Check for failures
        if summary.failed > 0 or summary.timed_out > 0:
            console.print(
                "\n[yellow]Some bundles failed or timed out. "
                "Check logs for details.[/yellow]"
            )
            sys.exit(1)
        else:
            console.print("\n[green]All bundles executed successfully![/green]")
            sys.exit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Execution interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Execution failed: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
