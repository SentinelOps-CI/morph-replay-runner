# Release checklist

Commands assume the repository root and an editable install (`pip install -e ".[dev]"`).
Default CI is offline; Morph is opt-in.

## 1. Install

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Optional extras (not required for offline release gates):

```bash
pip install -e ".[pcs,pip,ovk]"
```

## 2. Lint and format

```bash
black --check runner tests scripts
isort --check-only runner tests scripts
ruff check runner tests scripts
```

## 3. Typecheck

```bash
mypy runner
```

## 4. Tests

```bash
pytest tests -q --tb=short
```

## 5. Schema mirror digests

```bash
python scripts/check_schema_mirrors.py
```

## 6. Vendored instance validation

Always-on offline gate (no external CLIs required):

```bash
python scripts/validate_vendored_instances.py
```

Equivalent CLI entry:

```bash
replay-runner validate
```

## 7. Optional external validate

Skips only when `pcs` / `post-incident` are absent; fails closed when present and non-zero:

```bash
python scripts/optional_external_validate.py
# or:
replay-runner validate --external-clis
```

## 8. Dependency audit

```bash
pip-audit --strict
```

## 9. Hermetic example smoke (offline)

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

Expect exit 0 with all branches `complete` unless `--allow-partial` is intentional.

## 10. Release checksum bundle

```bash
python scripts/release_bundle.py
```

Writes `release-bundle/checksums.json` (gitignored scratch) covering schemas, the hermetic example tree, and PIP linkage fixtures.

## 11. Docs and claim surface

Confirm before tagging:

- [README.md](../README.md), [NON_CLAIMS.md](../NON_CLAIMS.md), [CHANGELOG.md](../CHANGELOG.md), [SECURITY.md](../SECURITY.md) match implemented behavior
- Version in `pyproject.toml`, `runner.__version__`, and CLI `--version` agree
- No TODOs or aspirational Morph/HTTP-callback marketing in shipped docs
- License Apache-2.0 referenced from README and `pyproject.toml`

## 12. Morph opt-in (optional, not a release blocker)

Requires repository secret / environment `MORPH_API_KEY`. Without it, the GitHub Actions `morph-opt-in` job is skipped.

```bash
export MORPH_API_KEY=...   # never commit
replay-runner run \
  --snapshot morphvm-minimal \
  --bundles "./replays/*.zip" \
  --parallel 1 \
  --provider morph \
  --out ./evidence-morph
```

`--http-callback` is rejected fail-closed (unimplemented / out of scope).
