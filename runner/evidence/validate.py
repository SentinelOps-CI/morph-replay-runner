"""Vendored JSON Schema validation (always-on; no external CLI required).

Mirrors pcs-core registry construction so CI can fail closed on instance
conformance without ``pcs validate`` / ``post-incident replay-check``.
External CLIs remain optional deeper semantic gates when installed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ArtifactKind = Literal[
    "RuntimeReceipt.v0",
    "pip.MorphReplayReport.v1",
    "pip.TransformationRecord.v1",
    "pip.LineageBundle.v1",
    "mrr.ExecutionProfile.v1",
    "mrr.BranchReplayManifest.v1",
    "mrr.DifferentialReport.v1",
    "mrr.ResourceReport.v1",
]


class SchemaValidationError(ValueError):
    """Instance failed vendored JSON Schema validation."""


def repo_root() -> Path:
    """Return repository root containing ``schemas/`` (cwd or parents)."""
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], Path.cwd(), *Path.cwd().parents):
        if (candidate / "schemas").is_dir():
            return candidate
    raise SchemaValidationError(
        "schemas/ directory not found; run from repo root or install package data"
    )


def schemas_root() -> Path:
    return repo_root() / "schemas"


SCHEMA_FILES: dict[ArtifactKind, Path] = {
    "RuntimeReceipt.v0": Path("pcs/RuntimeReceipt.v0.schema.json"),
    "pip.MorphReplayReport.v1": Path("pip/MorphReplayReport.schema.json"),
    "pip.TransformationRecord.v1": Path("pip/TransformationRecord.schema.json"),
    "pip.LineageBundle.v1": Path("pip/LineageBundle.schema.json"),
    "mrr.ExecutionProfile.v1": Path("mrr/execution_profile.v1.json"),
    "mrr.BranchReplayManifest.v1": Path("mrr/branch_replay_manifest.v1.json"),
    "mrr.DifferentialReport.v1": Path("mrr/differential_report.v1.json"),
    "mrr.ResourceReport.v1": Path("mrr/resource_report.v1.json"),
}


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SchemaValidationError(f"schema root must be object: {path}")
    return data


@lru_cache(maxsize=1)
def _build_registry() -> Registry:
    root = schemas_root()
    resources: list[tuple[str, Resource[Any]]] = []
    for path in sorted(root.rglob("*.json")):
        if path.name == "SCHEMA_MIRROR.json":
            continue
        schema = _load_json(path)
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        resources.append((path.as_uri(), resource))
        resources.append((path.name, resource))
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            resources.append((schema_id, resource))
        # Relative $ref targets used by PCS (e.g. common.defs.json#/...)
        resources.append((path.name.split("/")[-1], resource))
    return Registry().with_resources(resources)


def _format_checker() -> FormatChecker:
    checker = FormatChecker()
    # Require format assertions when checkers exist (fail closed on uri/date-time).
    required = {"date-time", "uri"}
    missing = required - set(checker.checkers)
    if missing:
        raise SchemaValidationError(
            "jsonschema FormatChecker missing required formats: "
            f"{sorted(missing)}; install jsonschema[format]"
        )
    return checker


@lru_cache(maxsize=16)
def _validator_for(kind: ArtifactKind) -> Draft202012Validator:
    rel = SCHEMA_FILES[kind]
    path = schemas_root() / rel
    if not path.is_file():
        raise SchemaValidationError(f"missing vendored schema: {path}")
    schema = _load_json(path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaValidationError(f"invalid schema {path}: {exc}") from exc
    return Draft202012Validator(
        schema,
        registry=_build_registry(),
        format_checker=_format_checker(),
    )


def validate_instance(kind: ArtifactKind, instance: dict[str, Any]) -> None:
    """Fail closed if ``instance`` does not conform to vendored schema ``kind``."""
    if not isinstance(instance, dict):
        raise SchemaValidationError(f"{kind}: instance must be a JSON object")
    validator = _validator_for(kind)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        messages = "; ".join(
            f"{'/'.join(str(p) for p in err.path) or '$'}: {err.message}"
            for err in errors[:12]
        )
        raise SchemaValidationError(f"{kind} schema validation failed: {messages}")


def validate_json_file(kind: ArtifactKind, path: Path) -> dict[str, Any]:
    data = _load_json(path)
    validate_instance(kind, data)
    return data


def clear_schema_caches() -> None:
    """Test helper to rebuild registry after schema tree changes."""
    _build_registry.cache_clear()
    _validator_for.cache_clear()
