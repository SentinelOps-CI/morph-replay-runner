# ADR MRR-ITE-08: PIP integration

## Status

Accepted

## Date

2026-07-24

## Context

Morph replay linkage for post-incident-proofs must stay observational and digest-linked to PCS, never promoted into PCS receipts.

## Decision

Emit `pip.MorphReplayReport.v1` and `TransformationRecord.v1` per branch. Cross-link PCS by digest only; never promote Morph reports into PCS. Joint fixtures under `fixtures/pip/valid_replay_linkage/`. Schemas mirrored under `schemas/pip/` with digest CI gate.

## Consequences

PIP emission is structural linkage only. Optional `post-incident` CLI gates skip when absent; vendored schema validation always runs.
