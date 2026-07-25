"""Differential reports with three-valued absent≠equal semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from runner.hashing import canonical_hash

ComparisonResult = Literal[
    "equal", "different", "absent_left", "absent_right", "absent_both"
]

COMPARISON_KEYS = (
    "terminal_state",
    "process_action",
    "authorization",
    "side_effect",
    "reward",
    "verifier_decision",
    "resource",
    "unresolved_external_dependency",
)

NON_CLAIMS = [
    "No preferred branch.",
    "No causality attribution.",
    "No remediation ranking.",
]


def compare_values(left: Any, right: Any) -> dict[str, Any]:
    left_absent = left is None
    right_absent = right is None
    if left_absent and right_absent:
        result: ComparisonResult = "absent_both"
    elif left_absent:
        result = "absent_left"
    elif right_absent:
        result = "absent_right"
    elif left == right:
        result = "equal"
    else:
        result = "different"
    payload: dict[str, Any] = {"result": result}
    if not left_absent:
        payload["left"] = left
    if not right_absent:
        payload["right"] = right
    return payload


def load_branch_view(branch_dir: Path) -> dict[str, Any]:
    status_path = branch_dir / "status.json"
    status = (
        json.loads(status_path.read_text(encoding="utf-8"))
        if status_path.is_file()
        else {}
    )
    terminal_path = branch_dir / "terminal_state.json"
    terminal = (
        json.loads(terminal_path.read_text(encoding="utf-8"))
        if terminal_path.is_file()
        else None
    )
    resources_path = branch_dir / "resource_report.json"
    resources = (
        json.loads(resources_path.read_text(encoding="utf-8"))
        if resources_path.is_file()
        else None
    )
    branch_report_path = branch_dir / "branch_report.json"
    branch_report = (
        json.loads(branch_report_path.read_text(encoding="utf-8"))
        if branch_report_path.is_file()
        else {}
    )
    return {
        "terminal_state": terminal,
        "process_action": branch_report.get("process_action"),
        "authorization": branch_report.get("authorization"),
        "side_effect": branch_report.get("side_effect"),
        "reward": branch_report.get("reward"),
        "verifier_decision": branch_report.get("verifier_decision"),
        "resource": resources,
        "unresolved_external_dependency": branch_report.get(
            "unresolved_external_dependency"
        ),
        "status": status,
    }


def build_differential_report(
    left_id: str,
    right_id: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    comparisons = {
        key: compare_values(left.get(key), right.get(key)) for key in COMPARISON_KEYS
    }
    body = {
        "schema_version": "mrr.DifferentialReport.v1",
        "left_branch_id": left_id,
        "right_branch_id": right_id,
        "comparisons": comparisons,
        "non_claims": list(NON_CLAIMS),
    }
    digest = canonical_hash(
        body,
        enforce_number_policy=True,
        extra_excluded=frozenset({"report_digest"}),
    )
    body["report_digest"] = digest
    from runner.evidence.validate import SchemaValidationError, validate_instance

    try:
        validate_instance("mrr.DifferentialReport.v1", body)
    except SchemaValidationError as exc:
        raise ValueError(str(exc)) from exc
    return body


def diff_branch_dirs(
    branches_root: Path,
    pairs: list[tuple[str, str]],
    out_dir: Path,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []
    for left_id, right_id in pairs:
        left = load_branch_view(branches_root / left_id)
        right = load_branch_view(branches_root / right_id)
        report = build_differential_report(left_id, right_id, left, right)
        # Reject causal / remediation claims if injected outside non_claims.
        comparisons_blob = json.dumps(report.get("comparisons", {})).lower()
        for banned in ("preferred_branch", "root_cause", "remediation_rank"):
            if banned in comparisons_blob:
                raise ValueError(
                    f"differential report contains banned language: {banned}"
                )
        prose = json.dumps(
            {k: v for k, v in report.items() if k != "non_claims"}
        ).lower()
        for banned in ("root cause is", "preferred branch is", "remediate by"):
            if banned in prose:
                raise ValueError(
                    f"differential report contains banned language: {banned}"
                )
        path = out_dir / f"{left_id}__{right_id}.json"
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        reports.append(report)
    return reports


def parse_pairs(raw: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if "," not in part:
            raise ValueError(f"invalid pair {part!r}; expected a,b")
        left, right = part.split(",", 1)
        pairs.append((left.strip(), right.strip()))
    if not pairs:
        raise ValueError("no pairs provided")
    return pairs
