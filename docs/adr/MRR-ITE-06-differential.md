# ADR MRR-ITE-06: Differential reports

## Status

Accepted

## Date

2026-07-24

## Context

Pairwise branch comparison must not invent equality when a side is missing, and must not encode preferred-branch semantics.

## Decision

Pairwise reports with three-valued absence semantics (`equal | different | absent_left | absent_right | absent_both`). Ban preferred-branch / causality / remediation language in outputs. Schema: `schemas/mrr/differential_report.v1.json`. CLI: `replay-runner diff`.

## Consequences

Injected causal / remediation claim text outside `non_claims` fails validation. See [NON_CLAIMS.md](../../NON_CLAIMS.md).
