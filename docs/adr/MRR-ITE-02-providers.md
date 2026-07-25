# ADR MRR-ITE-02: Provider abstraction

## Status

Accepted

## Date

2026-07-24

## Context

Hard-wiring Morph in the CLI blocked offline CI and mixed infrastructure with research semantics.

## Decision

`ExecutionProvider` Protocol isolates infrastructure. `LocalFakeProvider` is the default offline CI backend. Morph is opt-in and fail-closed when required digests/capabilities are missing.

## Cleanup

Deleted `runner/core_fixed.py`; dropped unused `aiofiles` / `asyncio-mqtt`; simplified docker-compose (removed broken HTTP stub service).

## Consequences

Default `branch` provider is `local-fake`. Legacy `run` still defaults to `morph` and requires Morph credentials.
