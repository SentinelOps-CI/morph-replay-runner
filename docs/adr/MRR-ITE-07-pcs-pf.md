# ADR MRR-ITE-07: PCS / PF-Core outputs

## Status

Accepted (amended)

## Date

2026-07-24

## Context

Branch evidence must link to PCS `RuntimeReceipt.v0` without inventing elevated receipt statuses. PF-Core is optional and fail-closed.

## Decision

Emit `RuntimeReceipt.v0` with `RuntimeObserved` by default.

`RuntimeChecked` is the only elevated **receipt status** used when a PF-Core /
runtime check actually ran. `ReplayValidated` is a **claim class** (manifest /
environment metadata + PF invocation record), not a PCS `artifact_status` enum
member — putting it on `RuntimeReceipt.status` is schema-invalid.

PF-Core via `pcs pf-core replay-trace` shell-out only when claim class is
`RuntimeChecked` or `ReplayValidated`. Missing trace or missing `pcs` CLI fails
closed (branch marked partial / error). CERT-V1 remains optional guest artifact,
not a PCS substitute.

Vendored `schemas/pcs/` instance validation always runs in emitters and CI;
external `pcs validate` is an optional deeper gate when the CLI is installed.

## Consequences

Claim-class metadata may record `ReplayValidated`; receipt `status` never does.
See [NON_CLAIMS.md](../../NON_CLAIMS.md).
