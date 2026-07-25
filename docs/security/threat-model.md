# Threat Model — morph-replay-runner

Date: 2026-07-24 · Scope: version 0.1.x hermetic branch-N + legacy Morph `run` path

## Assets

- Snapshot bytes and digests
- ExecutionProfile pins and digests
- Per-branch evidence packs (PCS / PIP)
- Secret references (identifiers only)
- Provider credentials (`MORPH_API_KEY` env)
- Vendored schema mirrors (`SCHEMA_MIRROR.json` digests)

## Adversaries

| Adversary | Goal |
|-----------|------|
| Malicious or malformed incident / profile / manifest inputs | Crash parsers, inject secret values, upgrade claim classes without checks |
| Cross-branch pollution | Leak files, resume dirty state, forge equal diffs from absent data |
| Compromised or dishonest Morph control plane | Misreport execute/measure results; treated as untrusted for claim upgrades |
| Supply-chain schema drift | Silently change PCS/PIP contracts without digest gate failure |
| CI / operator misconfiguration | Accidental live Morph spend or credential commit |

## Trust boundaries

1. **CLI / parsers** — untrusted JSON inputs; validated before the scheduler kernel
2. **Scheduler kernel** — receives typed profile / manifest only; owns isolation and retries
3. **Providers** — infrastructure only (clone / execute / measure / teardown / capability probes); Morph is untrusted for claim upgrades
4. **Evidence emitters** — observational labels only unless a check actually ran; vendored schema validation fail-closed before write
5. **External CLIs** (`pcs`, `post-incident`, OVK) — optional deeper gates; never implied by default offline CI

## Threats and mitigations

| Threat | Mitigation |
|--------|------------|
| Cross-branch file bleed | Per-branch FS roots; clone from canonical snapshot only; isolation tests |
| Dirty retry resume | Retry tears down and reclones from original snapshot |
| Secret materialization | Profile rejects secret values; redaction on logs; adversarial tests |
| Hermeticity bypass | `supports(mode)` preflight fail-closed before clone |
| Claim upgrade without check | Elevated claim classes require PF-Core trace + CLI; receipt status never invents `ReplayValidated` |
| Supply-chain schema drift | `SCHEMA_MIRROR.json` digest CI gate + always-on vendored instance validation |
| Live cloud in default CI | Offline `LocalFakeProvider` default; Morph opt-in via secret |
| HTTP callback confusion | `--http-callback` rejected fail-closed (unimplemented / out of scope) |
| Absent coerced to equal | Differential reports use three-valued absence semantics |

## Non-goals / non-claims

- Protecting against a compromised Morph control plane beyond documented assumptions
- Formal verification of guest workloads
- Campaign-level verifier assurance
- Causality, remediation ranking, or environment-semantics generation
- Production-grade non-repudiation or signing beyond recorded digests

Full product non-claims: [NON_CLAIMS.md](../../NON_CLAIMS.md).
Disclosure: [SECURITY.md](../../SECURITY.md).
