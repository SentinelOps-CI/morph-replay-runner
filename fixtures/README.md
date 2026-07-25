# Fixtures

Offline fixtures for unit, hermetic, adversarial, and schema-conformance tests.
Regenerate shared trees with:

```bash
python scripts/generate_fixtures.py
```

## Layout

| Path | Role |
|------|------|
| `profile/valid_profile.json` | Valid `mrr.ExecutionProfile.v1` |
| `profile/invalid_*.json` | Fail-closed profile validation cases (missing pin, secret value, schema version) |
| `branch/` | Hermetic branch-N inputs: incident, snapshot ref + payload, 16 interventions, manifest |
| `branch/manifest_digest_drift.json` | Negative case for digest drift |
| `pip/valid_replay_linkage/` | Joint PIP lineage + Morph replay report instances |

Empty reserved directories (`diff/`, `hermeticity/`, `pcs/`, `resources/`) may appear locally; authoritative committed fixtures are the paths above.

## Validation

```bash
python scripts/validate_vendored_instances.py
replay-runner profile validate --file fixtures/profile/valid_profile.json
```

Public fixtures use synthetic digests only. Do not add credentials or partner plaintext.
