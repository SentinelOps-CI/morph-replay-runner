# ADR MRR-ITE-03: Hermeticity modes

## Status

Accepted

## Date

2026-07-24

## Context

Network and dependency assumptions must be explicit and enforceable before clone, with recorded evidence of enforcement or denial.

## Decision

Five modes (`no_network`, `allowlisted_network`, `recorded_response`, `partner_local`, `synthetic_dependency`) with `supports()` preflight. Unsupported modes fail before clone; evidence distinguishes `enforced` vs `unsupported`. Implementation: `runner/hermeticity/`.

## Consequences

Hermeticity evidence is written at the run root (`hermeticity_evidence.json`). Bypass attempts are hard failures, not warnings.
