# ADR MRR-ITE-09: Security and release

## Status

Accepted

## Date

2026-07-24

## Context

Public release requires an honest secret model, isolation tests, disclosure route, and checksummed release artifacts — without overclaiming Morph trust or unimplemented surfaces.

## Decision

Isolation / cleanup / secret-erasure tests are mandatory gates. `SECURITY.md` + threat model published. Release checksum script covers schemas and example evidence (`scripts/release_bundle.py`). README and `NON_CLAIMS.md` claims match implemented behavior only. Default CI remains offline; Morph opt-in behind `MORPH_API_KEY`.

## Consequences

Release checklist: [docs/release-checklist.md](../release-checklist.md). Disclosure: [SECURITY.md](../../SECURITY.md).
