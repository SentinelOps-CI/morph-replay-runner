# ADR MRR-ITE-01: ExecutionProfile

## Status

Accepted

## Date

2026-07-24

## Context

Branch-N runs need a single pinned execution contract (snapshot, images, network, budgets, secret refs) with a stable digest for evidence linkage.

## Decision

Introduce versioned `mrr.ExecutionProfile.v1` with canonical digest (PCS Canonical JSON v1), material pins required, and secrets by `secret_ref` only. Schema: `schemas/mrr/execution_profile.v1.json`. Loader: `runner/profile/`.

## Non-claims

Profile digests do not attest guest correctness or Morph control-plane honesty beyond recorded pins.

## Consequences

Invalid profiles (missing pins, secret values, wrong schema version) fail closed before scheduling.
