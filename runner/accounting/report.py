"""Resource accounting: never invent unavailable metrics."""

from __future__ import annotations

from typing import Any, Optional

from runner.profile.schema import Budgets
from runner.providers.base import MetricValue, ResourceSample


class BudgetExceededError(RuntimeError):
    """Observed metric exceeds profile budget."""


def metric_to_dict(metric: MetricValue) -> dict[str, Any]:
    return {
        "value": metric.value,
        "unit": metric.unit,
        "availability": metric.availability,
        "source": metric.source,
    }


def sample_to_report(branch_id: str, sample: ResourceSample) -> dict[str, Any]:
    return {
        "schema_version": "mrr.ResourceReport.v1",
        "branch_id": branch_id,
        "metrics": {
            key: metric_to_dict(value) for key, value in sorted(sample.metrics.items())
        },
        "budget_violations": [],
    }


def _observed_number(metric: Optional[MetricValue]) -> Optional[float]:
    if metric is None or metric.availability != "observed":
        return None
    if isinstance(metric.value, (int, float)):
        return float(metric.value)
    return None


def enforce_budgets(sample: ResourceSample, budgets: Budgets) -> list[str]:
    """Return violation messages; raises if any observed metric exceeds budget."""
    violations: list[str] = []
    checks = [
        ("wall_time_ms", budgets.wall_time_ms),
        ("memory_mib", budgets.memory_mib),
        ("model_tokens", budgets.token_budget),
        ("external_api_calls", budgets.api_call_budget),
    ]
    for key, limit in checks:
        metric = sample.metrics.get(key)
        value = _observed_number(metric)
        if value is None:
            continue
        if value > float(limit):
            violations.append(f"{key} observed {value} exceeds budget {limit}")
    storage = _observed_number(sample.metrics.get("storage_bytes"))
    if storage is not None and storage > budgets.storage_mib * 1024 * 1024:
        violations.append(
            f"storage_bytes observed {storage} exceeds budget "
            f"{budgets.storage_mib} MiB"
        )
    if violations:
        raise BudgetExceededError("; ".join(violations))
    return violations


def assert_unavailable_not_fabricated(sample: ResourceSample) -> None:
    for name, metric in sample.metrics.items():
        if metric.availability == "unavailable" and metric.value is not None:
            raise ValueError(
                f"metric {name} marked unavailable but has value {metric.value!r}"
            )
