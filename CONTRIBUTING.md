# Contributing

## Prerequisites

- Python 3.9–3.12 (CI matrix; 3.9 is the typed floor)
- Git
- Optional: `MORPH_API_KEY` only for live Morph (`replay-runner run` / `--provider morph`)
- Optional: `pcs` / `post-incident` CLIs for deeper external validation extras

## Install

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Refresh generated fixtures/examples when you change generators:

```bash
python scripts/generate_fixtures.py
```

## Local quality gates

Run the same offline path CI uses:

```bash
black --check runner tests scripts
isort --check-only runner tests scripts
ruff check runner tests scripts
mypy runner
python scripts/check_schema_mirrors.py
python scripts/validate_vendored_instances.py
pytest tests -q --tb=short
python scripts/optional_external_validate.py
pip-audit --strict
```

Or via the CLI wrapper:

```bash
replay-runner validate
replay-runner validate --external-clis   # only when pcs/post-incident are installed
```

Hermetic example (offline, no Morph):

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

Release checksum bundle:

```bash
python scripts/release_bundle.py
```

Full command list: [docs/release-checklist.md](docs/release-checklist.md).

## Standards

- Prefer fail-closed behavior; never invent elevated claim classes or coerce absent values to equal.
- Do not commit secrets, API keys, `.env` files, or partner plaintext.
- Keep providers infrastructure-only (no causality / remediation / reward semantics).
- Update ADRs under `docs/adr/` when contracts or claim boundaries change.
- Keep [NON_CLAIMS.md](NON_CLAIMS.md) and README claim language aligned with implemented behavior.
- Do not edit vendored `schemas/pcs/` or `schemas/pip/` in place; bump the pin and re-vendor (see [schemas/README.md](schemas/README.md)).

## Pull requests

- Describe intent and link the relevant MRR-ITE ADR when semantics change.
- Include or update fixtures under `fixtures/` for new validation paths.
- Keep default CI offline; Morph remains opt-in behind `MORPH_API_KEY`.
