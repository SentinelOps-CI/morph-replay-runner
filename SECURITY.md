# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Do not open a public issue for secret leakage, isolation bypasses, or claim-upgrade bugs.

Preferred channels (in order):

1. GitHub Security Advisories for this repository (Security tab → Advisories → Report a vulnerability), when enabled
2. Email **security@sentinelops.ci** with affected commit/tag, reproduction steps, and impact

Include a minimal reproduction when possible. Do not attach production credentials, partner plaintext, or live Morph API keys.

Target response:

- Acknowledgement within 2 business days
- Triage update within 7 business days

## Secret handling

- Live Morph credentials are read from the environment variable `MORPH_API_KEY` only
- ExecutionProfile accepts `secret_ref` identifiers; secret **values** in profiles are rejected fail-closed
- Evidence emitters redact known secret material from logs and status payloads
- Never commit `.env`, key files, or credentials; `.env` is gitignored
- Default CI is offline (`LocalFakeProvider`); the `morph-opt-in` workflow job runs only when `MORPH_API_KEY` is configured as a repository secret

## Threat model

See [docs/security/threat-model.md](docs/security/threat-model.md) for assets, adversaries, trust boundaries, and non-claims.
Architecture claim boundaries: [NON_CLAIMS.md](NON_CLAIMS.md).
