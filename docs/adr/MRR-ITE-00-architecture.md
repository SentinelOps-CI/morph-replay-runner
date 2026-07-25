# ADR MRR-ITE-00: Hermetic Branch-N Architecture Boundaries

## Status

Accepted

## Date

2026-07-24

## Context

`morph-replay-runner` began as a thin Morph Cloud ZIP-replay CLI. SentinelOps requires a hermetic, immutable, branch-N execution backend that emits observational evidence under PCS and PIP contracts without inventing research semantics inside providers.

## Decision

### Provider boundary

Providers (`MorphCloudProvider`, `LocalFakeProvider`) implement only infrastructure operations: snapshot lookup, clone, execute, measure, extract artifacts, teardown, and hermeticity capability probes. Providers MUST NOT encode incident causality, remediation preference, reward semantics, or verifier policy interpretation.

### Ownership

| Concern | Owner module |
|---------|--------------|
| ExecutionProfile schema, digest, secret refs | `runner/profile/` |
| Hermeticity modes + enforcement evidence | `runner/hermeticity/` |
| BranchReplayManifest + scheduler | `runner/branch/` |
| Resource accounting | `runner/accounting/` |
| Differential reports | `runner/diff/` |
| PCS/PIP emitters, digests, redaction | `runner/evidence/` |
| OVK checker shell-out | `runner/ovk/` |
| Legacy ZIP Morph path | `runner/legacy_core.py` (wrapper over prior `core.py` behavior) |

### Claim classes

| Layer | Allowed claim / label | When |
|-------|----------------------|------|
| Repo-local | observational branch status `complete` \| `partial` | always when written |
| PCS | `RuntimeReceipt.v0` with status `RuntimeObserved` | every complete branch emission |
| PCS | `RuntimeChecked` | only after an actual runtime check ran |
| PF-Core | `ReplayValidated` / five-file emit | only when claim class applies and PF-shaped trace supplied |
| PIP | `MorphReplayReport.v1` status `recorded` \| `mismatch` \| `indeterminate` | when PIP emitter runs |
| OVK | digests/refs of checker results | only when OVK was shell-invoked |

### Explicit non-claims

- No causality or root-cause attribution
- No remediation ranking or “preferred branch”
- No environment semantics generation
- No campaign-level verifier assurance
- HTTP callback stubs are out of scope for hermetic branch-N; re-enabling without a real implementation MUST fail closed
- CERT-V1 guest copies remain optional guest artifacts referenced by digest; they are not PCS substitutes

Product-level text: [NON_CLAIMS.md](../../NON_CLAIMS.md).

### Cleanup completed in later ITEs

Tracked here for history; executed in MRR-ITE-02:

- Removed unused duplicate `runner/core_fixed.py`
- Dropped unused dependencies `aiofiles`, `asyncio-mqtt`
- Simplified `docker/docker-compose.yml` (removed broken HTTP stub service)

### Compatibility

`replay-runner branch` is the primary hermetic path (MRR-ITE-04).
Preserve `replay-runner --snapshot … --bundles …` as the `run` compatibility path.
Default CI MUST run offline via `LocalFakeProvider`; Morph remains opt-in behind secrets.

## Consequences

Later ITEs introduce schemas and runtime behind these boundaries. Violations (providers encoding research semantics, claim upgrades without checks, secret values in profiles) are hard failures.

## Rollback

Revert docs/CI scaffolding introduced in ITE-00; no schema consumers at baseline time.
