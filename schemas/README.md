# Vendored Schemas

This directory contains vendored schemas from external projects, pinned by specific tags for reproducibility.

## CERT-V1 Schema

**Source**: [CERT-V1 specification](https://github.com/cert-org/cert-v1)
**Pinned Version**: v1.0.0
**Purpose**: Defines the certificate format for replay execution results

## TRACE-REPLAY-KIT Schema

**Source**: [TRACE-REPLAY-KIT](https://github.com/trace-replay-kit/spec)
**Pinned Version**: v2.1.0
**Purpose**: Defines the replay bundle format and execution interface

## Schema Files

- `cert_v1.json` - CERT-V1 JSON schema definition
- `trace_replay_kit.json` - TRACE-REPLAY-KIT bundle schema
- `replay_runner.json` - Internal schema for runner configuration and reports

## Updating Schemas

To update to newer versions:

1. Download the latest schema from the source repository
2. Update the version tag in this README
3. Test compatibility with existing code
4. Update any validation logic if needed
