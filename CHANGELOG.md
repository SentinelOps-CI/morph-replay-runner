# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-07-24

First public Alpha of the hermetic branch-N backend (MRR-ITE-00 through MRR-ITE-09).

### Added

- Hermetic branch-N backend (`replay-runner branch`) with `LocalFakeProvider` offline path
- ExecutionProfile schema (`mrr.ExecutionProfile.v1`), canonical digest, secret-ref validation
- Provider Protocol: Morph adapter + `LocalFakeProvider`
- Hermeticity modes with fail-closed preflight evidence
- Resource accounting with explicit `unavailable` metrics
- Differential reports with three-valued absence (`absent ≠ equal`)
- PCS `RuntimeReceipt.v0` emission; optional PF-Core gate for elevated claim classes
- PIP `MorphReplayReport.v1` + `TransformationRecord` emission and joint fixtures
- Always-on vendored JSON Schema instance validation (no external CLI required)
- Offline CI (lint / typecheck / tests / schema mirrors); Morph smoke opt-in via `MORPH_API_KEY`
- Security policy, threat model, release checksum script (`scripts/release_bundle.py`)
- Optional `--ovk-check` (fail-closed when flag set and OVK not on PATH)
- Branch CLI fail-closed on partial branches unless `--allow-partial`
- `replay-runner validate` for schema mirrors and vendored instances
- Release documentation: `NON_CLAIMS.md`, `CONTRIBUTING.md`, `docs/release-checklist.md`,
  `fixtures/README.md`, public README / SECURITY / ADR polish

### Changed

- CLI is a Click group; legacy ZIP Morph path is `replay-runner run` (compat argv still works)
- `requires-python` pinned to `>=3.9` (CI matrix 3.9–3.12)
- Removed unused `aiofiles` / `asyncio-mqtt`; deleted `core_fixed.py`
- `ReplayValidated` is claim-class metadata only; receipt status uses PCS enum
  (`RuntimeObserved` / `RuntimeChecked`)
- `HASH_EXCLUDED_FIELDS` aligned with pcs-core; domain digests via `extra_excluded`
- HTTP callback flag rejected fail-closed (unimplemented / out of scope)

### Non-claims

Observational / differential evidence only. No causality, remediation ranking,
environment-semantics generation, or campaign-level verifier assurance.
See [NON_CLAIMS.md](NON_CLAIMS.md).

[Unreleased]: https://github.com/SentinelOps-CI/morph-replay-runner/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SentinelOps-CI/morph-replay-runner/releases/tag/v0.1.0
