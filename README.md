# morph-replay-runner

[![CI](https://github.com/SentinelOps-CI/morph-replay-runner/actions/workflows/ci.yml/badge.svg)](https://github.com/SentinelOps-CI/morph-replay-runner/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Hermetic, immutable **branch-N** execution backend for SentinelOps-CI.
Produces observational PCS (`RuntimeReceipt.v0`) and PIP (Morph / transformation) evidence packs.

Default path is offline via `LocalFakeProvider`. Live Morph Cloud is opt-in and requires `MORPH_API_KEY`.

## Status

Version **0.1.0** (Alpha). Primary command: `replay-runner branch`.
Legacy ZIP Morph path: `replay-runner run` (also accepts bare `--snapshot …` argv).

What this release implements:

- Hermetic branch-N scheduler with per-branch isolation and fail-closed hermeticity preflight
- ExecutionProfile schema, canonical digest, secret-ref validation
- Provider protocol: `LocalFakeProvider` (CI default) + Morph adapter (opt-in)
- Resource accounting with explicit `unavailable` metrics
- Differential reports (`absent ≠ equal`)
- Always-on vendored JSON Schema validation; optional external `pcs` / `post-incident` gates

See [NON_CLAIMS.md](NON_CLAIMS.md) for claim boundaries. Architecture: [docs/adr/](docs/adr/README.md).

## Requirements

- Python **3.9+** (CI: 3.9–3.12)
- Optional: `MORPH_API_KEY` for live Morph (`replay-runner run` / `--provider morph`)
- Optional extras: `pcs`, `pip` (`post-incident`), `ovk` for deeper CLI gates

## Install

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Refresh fixtures/examples after generator changes:

```bash
python scripts/generate_fixtures.py
```

## Quick start (hermetic, offline)

```bash
replay-runner branch \
  --incident examples/hermetic-branch-n/incident_bundle.json \
  --snapshot examples/hermetic-branch-n/snapshot_ref.json \
  --snapshot-payload examples/hermetic-branch-n/snapshot.payload \
  --interventions examples/hermetic-branch-n/interventions \
  --execution-profile examples/hermetic-branch-n/execution_profile.json \
  --manifest examples/hermetic-branch-n/manifest.json \
  --parallel 16 \
  --provider local-fake \
  --out ./branches
```

No Morph credentials required. Exit is non-zero if any branch is `partial` unless `--allow-partial` is set.

## Morph opt-in (compatibility path)

Requires `MORPH_API_KEY` in the environment. Without it, the GitHub Actions `morph-opt-in` job is skipped.

```bash
export MORPH_API_KEY=...   # never commit
replay-runner run \
  --snapshot morphvm-minimal \
  --bundles "./replays/*.zip" \
  --parallel 4 \
  --provider morph \
  --out ./evidence
```

Legacy argv without a subcommand (`replay-runner --snapshot …`) still maps to `run`.
`--http-callback` is rejected fail-closed (unimplemented / out of scope for hermetic branch-N).

## CLI reference

| Command | Purpose |
|---------|---------|
| `replay-runner branch` | Hermetic isolated branch-N execution (primary) |
| `replay-runner run` | Legacy ZIP-bundle Morph path |
| `replay-runner profile validate --file …` | Validate ExecutionProfile |
| `replay-runner profile digest --file …` | Print profile digest |
| `replay-runner diff --branches … --pairs a,b --out …` | Pairwise differential reports |
| `replay-runner validate` | Schema mirrors + vendored instance checks |
| `replay-runner validate --external-clis` | Also run pcs/post-incident when installed |

Useful `branch` flags:

- `--provider local-fake|morph` (default `local-fake`)
- `--snapshot-payload` — raw bytes whose sha256 must match `snapshot_digest`
- `--allow-partial` — accept explicit partial branches (default: fail closed)
- `--ovk-check <target>` — shell out to OVK on PATH; fail closed if missing when set

## Evidence layout

Each `branches/<branch_id>/` is an immutable evidence pack:

```text
execution_profile.json
snapshot_ref.json
intervention_record.json
runtime_receipt.json          # PCS RuntimeReceipt.v0
morph_replay_report.json      # PIP
transformation_record.json    # PIP
resource_report.json
terminal_state.json
terminal_commitment.json
branch_report.json
teardown_receipt.json
digests.json
logs.txt
status.json                   # complete | partial
```

Run root also includes `hermeticity_evidence.json` and `summary.json` (with `non_claims`).

## Differential reports

```bash
replay-runner diff --branches ./branches --pairs branch-00,branch-01 --out ./diffs
```

Comparisons use `equal | different | absent_left | absent_right | absent_both`.
Missing data is never coerced to equal. Outputs ban preferred-branch / causality language.

## Offline quality gates

```bash
pytest tests -q
python scripts/check_schema_mirrors.py
python scripts/validate_vendored_instances.py
python scripts/optional_external_validate.py   # skips only when pcs/post-incident absent
python scripts/release_bundle.py
```

Full release command list: [docs/release-checklist.md](docs/release-checklist.md).
Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

```text
runner/           # CLI, profile, hermeticity, branch, accounting, diff, evidence, providers
schemas/mrr/      # repo-local domain schemas
schemas/pcs/      # mirrored pcs-core (RuntimeReceipt.v0 + defs)
schemas/pip/      # mirrored PIP Morph/lineage schemas
fixtures/         # valid/invalid profiles, branch inputs, PIP linkage
examples/hermetic-branch-n/
docs/adr/         # MRR-ITE architecture decisions
docs/security/    # threat model
docs/baseline/    # historical ITE-00 measurement
```

## Pins

| Layer | Pin |
|-------|-----|
| PCS | pcs-core `v0.1.0` schemas under `schemas/pcs/` |
| PIP | post-incident-proofs schemas under `schemas/pip/` |
| OVK | shell-out only; optional extra wheel `1.2.1` |
| Morph | `morphcloud>=0.1.91` (live use opt-in via `MORPH_API_KEY`) |

Mirror digests and refresh procedure: [schemas/README.md](schemas/README.md).

## Documentation

| Doc | Topic |
|-----|-------|
| [NON_CLAIMS.md](NON_CLAIMS.md) | Fail-closed claim boundaries |
| [SECURITY.md](SECURITY.md) | Disclosure and secret handling |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [docs/security/threat-model.md](docs/security/threat-model.md) | Adversaries and trust boundaries |
| [docs/adr/](docs/adr/) | MRR-ITE decisions |
| [docs/baseline/MRR-ITE-00.md](docs/baseline/MRR-ITE-00.md) | Historical baseline |
| [docs/release-checklist.md](docs/release-checklist.md) | Exact release commands |

## License

Apache-2.0. See [LICENSE](LICENSE).
