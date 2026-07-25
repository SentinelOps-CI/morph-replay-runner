# Vendored / mirrored schemas

Pinned PCS and PIP contracts live here so offline CI can validate instances
without requiring `pcs` or `post-incident` CLIs. Digests are recorded in each
directory's `SCHEMA_MIRROR.json` and checked by `scripts/check_schema_mirrors.py`.

## Layout

| Path | Source | Role |
|------|--------|------|
| `mrr/` | this repo | ExecutionProfile, BranchReplayManifest, DifferentialReport, ResourceReport |
| `pcs/` | [pcs-core](https://github.com/SentinelOps-CI/pcs-core) tag `v0.1.0` | `RuntimeReceipt.v0`, `common.defs`, ArtifactIntegrity |
| `pip/` | [post-incident-proofs](https://github.com/SentinelOps-CI/post-incident-proofs) | MorphReplayReport, TransformationRecord, LineageBundle |
| `cert_v1.json` / `trace_replay_kit.json` / `replay_runner.json` | legacy guest/docs | Optional guest CERT / historical TRACE; not PCS substitutes |

## Current pins

| Mirror | Manifest | Pin |
|--------|----------|-----|
| PCS | `pcs/SCHEMA_MIRROR.json` | tag `v0.1.0`, commit `2f0ce059652408bce19bc89ba6660030020d5ea0` |
| PIP | `pip/SCHEMA_MIRROR.json` | commit `3cdfdf09c20f08ad5221d29607b5a9726295ad10` |

Do **not** edit vendored files under `pcs/` or `pip/` in place. Bump the pin, re-copy, and update `local_digests`.

## Validation

1. Mirror digests: `python scripts/check_schema_mirrors.py`
2. Instance conformance (always-on): `python scripts/validate_vendored_instances.py`
3. Optional deeper CLI gates when installed: `python scripts/optional_external_validate.py`

Emitters call `runner.evidence.validate.validate_instance` fail-closed before writing evidence.

## How to refresh a mirror

From a checked-out sibling checkout at the desired pin:

```bash
# PCS (example paths; adjust to your local checkout)
cp /path/to/pcs-core/schemas/RuntimeReceipt.v0.schema.json schemas/pcs/
cp /path/to/pcs-core/schemas/common.defs.json schemas/pcs/
cp /path/to/pcs-core/schemas/ArtifactIntegrity.v1.schema.json schemas/pcs/

# PIP Morph / lineage schemas used by this runner
cp /path/to/post-incident-proofs/schemas/pip/v1/LineageBundle.schema.json schemas/pip/
cp /path/to/post-incident-proofs/schemas/pip/v1/MorphReplayReport.schema.json schemas/pip/
cp /path/to/post-incident-proofs/schemas/pip/v1/TransformationRecord.schema.json schemas/pip/
```

Then recompute digests and update the corresponding `SCHEMA_MIRROR.json`:

```bash
python - <<'PY'
import hashlib, json, pathlib
root = pathlib.Path("schemas/pcs")  # or schemas/pip
files = json.loads((root / "SCHEMA_MIRROR.json").read_text())["vendored_files"]
digests = {
    name: "sha256:" + hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in files
}
print(json.dumps(digests, indent=2))
PY
```

Update `source_tag` / `pinned_commit` / `pin_rationale` in the manifest, then:

```bash
python scripts/check_schema_mirrors.py
python scripts/validate_vendored_instances.py
```

Mirroring schemas does not imply PF-Core / OVK runtime integration on the default path.
See [NON_CLAIMS.md](../NON_CLAIMS.md).
