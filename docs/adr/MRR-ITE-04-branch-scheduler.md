# ADR MRR-ITE-04: Branch-N scheduler

## Status

Accepted

## Date

2026-07-24

## Context

Parallel branch execution must not share dirty sibling state; retries must reclone from the canonical snapshot.

## Decision

`BranchReplayManifest.v1` + scheduler clones each branch from the canonical snapshot, never from dirty siblings. Retries teardown and reclone. Independence unless cancellation policy says otherwise. `branch` CLI is the primary hermetic path; `run` remains compatibility. Implementation: `runner/branch/`.

## Consequences

Per-branch evidence packs are immutable once written. Process exits non-zero on any `partial` branch unless `--allow-partial`.
