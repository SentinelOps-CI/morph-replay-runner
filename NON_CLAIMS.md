# Non-claims

This repository emits **observational** and **differential** evidence only.
Claim language is fail-closed: elevated labels require a check that actually ran.

## This project does not claim

- Causality, root-cause attribution, or blame
- Remediation ranking, preferred branch, or policy certification
- Environment-semantics generation inside providers
- Campaign-level verifier assurance
- That Morph Cloud (or any provider control plane) is honest beyond recorded digests and capability probes
- That guest workloads are formally verified
- That `observational` / `RuntimeObserved` evidence is formally verified
- That HTTP callbacks, live SDE operation, or unimplemented surfaces are available

## Status and claim-class boundaries

| Label | Meaning in this repo |
|-------|----------------------|
| Branch `complete` / `partial` | Local observational run status under the scheduler |
| PCS `RuntimeObserved` | Default `RuntimeReceipt.v0` status when no runtime check ran |
| PCS `RuntimeChecked` | Receipt status only after a PF-Core / runtime check actually ran |
| Claim class `ReplayValidated` | Manifest / environment / PF invocation metadata only — **not** a PCS receipt `status` enum member |
| PIP Morph / transformation records | Structural linkage and digests; never promoted into PCS |

Putting `ReplayValidated` on `RuntimeReceipt.status` is schema-invalid and rejected.

## Related

- [docs/adr/MRR-ITE-00-architecture.md](docs/adr/MRR-ITE-00-architecture.md)
- [docs/adr/MRR-ITE-07-pcs-pf.md](docs/adr/MRR-ITE-07-pcs-pf.md)
- [docs/security/threat-model.md](docs/security/threat-model.md)
