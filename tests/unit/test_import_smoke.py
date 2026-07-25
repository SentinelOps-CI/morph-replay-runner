"""Import smoke tests for MRR-ITE-00 quality scaffolding."""

from __future__ import annotations

from pathlib import Path


def test_package_imports() -> None:
    import runner
    from runner import hashing

    assert runner.__version__ == "0.1.0"
    assert hashing.CANONICALIZATION_VERSION == "v1"


def test_baseline_doc_fields_present() -> None:
    text = Path("docs/baseline/MRR-ITE-00.md").read_text(encoding="utf-8")
    for field in (
        "Base commit",
        "Python",
        "PCS",
        "PIP",
        "OVK",
        "Non-claims",
        "Baseline commands",
    ):
        assert field in text


def test_architecture_adr_checklist() -> None:
    text = Path("docs/adr/MRR-ITE-00-architecture.md").read_text(encoding="utf-8")
    for needle in (
        "Provider boundary",
        "Claim classes",
        "Explicit non-claims",
        "HTTP callback",
        "LocalFakeProvider",
        "RuntimeObserved",
    ):
        assert needle in text


def test_license_apache() -> None:
    text = Path("LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in text
    assert "Version 2.0" in text
