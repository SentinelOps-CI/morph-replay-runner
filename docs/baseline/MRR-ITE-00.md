# MRR-ITE-00 Baseline

## Status

**Historical baseline measurement** for MRR-ITE-00 (2026-07-24).
The gap inventory below describes the repository **at the base commit**, before
subsequent ITEs. Implemented capabilities after 0.1.0 are documented in
[docs/adr/](../adr/), [README.md](../../README.md), and [CHANGELOG.md](../../CHANGELOG.md).
Do not treat the Pre-ITE inventory as current product status.

## Identity

| Field | Value |
|-------|-------|
| Base commit | `b3018d790e3e7c622b28641c0230a61bb3b78955` |
| Base message | Update README with ASCII art and project details |
| Measurement date | 2026-07-24 |
| Host OS | Windows 10.0.26200 |
| Python | 3.13.11 (local measurement host); package/`requires-python` and CI target **3.9–3.12** |
| Package version | 0.1.0 (Alpha) |

## Locked pins (sibling repos on measurement host)

| Layer | Pin | Path / artifact |
|-------|-----|-----------------|
| PCS | `pcs-core` tag `v0.1.0` (`2f0ce059652408bce19bc89ba6660030020d5ea0`) | `C:\Users\mateo\pcs-core` |
| PIP | `post-incident-proofs` commit `3cdfdf09c20f08ad5221d29607b5a9726295ad10` | `C:\Users\mateo\post-incident-proofs` |
| OVK | wheel `1.2.1` | `C:\Users\mateo\ovk-v1.2.1-dist\open_verification_kernel-1.2.1-py3-none-any.whl` |
| Morph | `morphcloud>=0.1.91` (optional live) | PyPI / Morph Cloud |

## Tool versions (measurement host)

| Tool | Version |
|------|---------|
| pydantic | 2.12.5 |
| click | 8.2.1 |
| jsonschema | 4.23.0 |
| morphcloud | not installed on measurement host (live Morph remains opt-in) |

## Baseline commands and results

```text
python --version
# Python 3.13.11

git rev-parse HEAD
# b3018d790e3e7c622b28641c0230a61bb3b78955

python -c "import runner; print(runner.__version__)"
# 0.1.0 (after editable install)

pytest tests/unit/test_import_smoke.py -q
# (introduced in this ITE; must pass offline)
```

## Pre-ITE inventory (gaps at base commit — superseded by later ITEs)

At `b3018d79…` the tree had:

- Single Click command hard-wired to `MorphCloudClient` in `runner/core.py`
- No provider abstraction, ExecutionProfile, hermeticity, branch-N scheduler, PCS, PIP, or resource accounting
- No unit tests; CI is live Morph smoke only
- `--timeout` / `--http-callback` are config-only stubs
- Sync path reuses dirty Morph branches without reset
- Dead file `runner/core_fixed.py`; unused deps `aiofiles`, `asyncio-mqtt`
- Broken docker-compose reference to missing `test-http.conf`

These gaps were addressed across MRR-ITE-01–09. Current behavior: hermetic `branch` + offline CI; `--http-callback` fail-closed.

## Non-claims (baseline)

This repository at the base commit does **not** claim:

- Causality, remediation ranking, or environment-semantics generation
- Campaign-level verifier assurance
- Hermetic branch-N isolation
- PCS `RuntimeReceipt` / PIP Morph report emission
- Offline deterministic CI

Evidence labels `runtime_observed` / `RuntimeChecked` / `ReplayValidated` are forbidden until the corresponding check actually runs (later ITEs).
Current product non-claims: [NON_CLAIMS.md](../../NON_CLAIMS.md).

## Quality scaffolding introduced here

- Apache-2.0 `LICENSE`
- `.gitignore`
- Offline CI job (lint/typecheck/unit without Morph)
- `requires-python >=3.9` aligned with README/CI
- Import smoke tests
- Architecture ADR
