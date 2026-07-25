"""Legacy ZIP Morph path preserved as compatibility wrapper."""

from __future__ import annotations

# Re-export prior core implementation under a stable name for migration.
from runner.core import ReplayRunner

__all__ = ["ReplayRunner"]
