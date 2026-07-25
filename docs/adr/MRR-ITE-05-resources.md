# ADR MRR-ITE-05: Resource accounting

## Status

Accepted

## Date

2026-07-24

## Context

Providers may be unable to observe some metrics; fabricating zeros would overclaim.

## Decision

Every metric carries `availability: observed|unavailable|not_applicable`. Unavailable metrics must have `value: null`. Budget enforcement fails closed on observed overruns. Schema: `schemas/mrr/resource_report.v1.json`.

## Consequences

Resource reports are validated before evidence write; unavailable metrics never silently become equal in diffs.
