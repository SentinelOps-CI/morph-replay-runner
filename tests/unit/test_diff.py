"""Differential report tests."""

from __future__ import annotations

import json
from pathlib import Path

from runner.diff import build_differential_report, compare_values, diff_branch_dirs


def test_absent_not_equal() -> None:
    assert compare_values(None, None)["result"] == "absent_both"
    assert compare_values(None, 1)["result"] == "absent_left"
    assert compare_values(1, None)["result"] == "absent_right"
    assert compare_values(1, 1)["result"] == "equal"
    assert compare_values(1, 2)["result"] == "different"


def test_diff_reproducible(tmp_path: Path) -> None:
    branches = tmp_path / "branches"
    for name, terminal in (("a", {"x": 1}), ("b", {"x": 2})):
        d = branches / name
        d.mkdir(parents=True)
        (d / "status.json").write_text(
            json.dumps({"status": "complete"}), encoding="utf-8"
        )
        (d / "terminal_state.json").write_text(json.dumps(terminal), encoding="utf-8")
        (d / "branch_report.json").write_text("{}", encoding="utf-8")
    out1 = tmp_path / "d1"
    out2 = tmp_path / "d2"
    r1 = diff_branch_dirs(branches, [("a", "b")], out1)[0]
    r2 = diff_branch_dirs(branches, [("a", "b")], out2)[0]
    assert r1["report_digest"] == r2["report_digest"]
    assert r1["comparisons"]["terminal_state"]["result"] == "different"
    assert r1["comparisons"]["reward"]["result"] == "absent_both"
    blob = json.dumps(r1["comparisons"]).lower()
    assert "preferred_branch" not in blob
    assert "remediation_rank" not in blob
    assert "No preferred branch." in r1["non_claims"]


def test_build_report_digest_stable() -> None:
    left = {"terminal_state": {"a": 1}, "reward": None}
    right = {"terminal_state": {"a": 1}, "reward": None}
    r1 = build_differential_report("l", "r", left, right)
    r2 = build_differential_report("l", "r", left, right)
    assert r1["report_digest"] == r2["report_digest"]
    assert r1["comparisons"]["terminal_state"]["result"] == "equal"
    assert r1["comparisons"]["reward"]["result"] == "absent_both"
