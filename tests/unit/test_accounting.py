"""Resource accounting tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.accounting import (
    BudgetExceededError,
    assert_unavailable_not_fabricated,
    enforce_budgets,
    sample_to_report,
)
from runner.profile import load_profile
from runner.providers.base import ExecRequest, MetricValue, ResourceSample
from runner.providers.local_fake import LocalFakeProvider


def test_unavailable_stays_unavailable(tmp_path: Path) -> None:
    provider = LocalFakeProvider(tmp_path)
    snap = provider.register_snapshot("s", b"x")
    handle = provider.clone(snap, branch_id="b")
    provider.execute(handle, ExecRequest(command=["replay"], timeout_ms=1000))
    sample = provider.measure(handle)
    assert_unavailable_not_fabricated(sample)
    report = sample_to_report("b", sample)
    assert report["metrics"]["accelerator_alloc"]["availability"] == "unavailable"
    assert report["metrics"]["accelerator_alloc"]["value"] is None


def test_budget_enforcement_fail_closed() -> None:
    profile = load_profile("fixtures/profile/valid_profile.json")
    sample = ResourceSample(
        metrics={
            "wall_time_ms": MetricValue(
                value=profile.budgets.wall_time_ms + 1,
                unit="ms",
                availability="observed",
                source="provider",
            )
        }
    )
    with pytest.raises(BudgetExceededError):
        enforce_budgets(sample, profile.budgets)


def test_fabricated_unavailable_rejected() -> None:
    sample = ResourceSample(
        metrics={
            "accelerator_alloc": MetricValue(
                value=1,
                unit="count",
                availability="unavailable",
                source="provider",
            )
        }
    )
    with pytest.raises(ValueError):
        assert_unavailable_not_fabricated(sample)
