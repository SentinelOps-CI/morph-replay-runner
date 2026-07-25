#!/usr/bin/env python3
"""Fail closed if vendored schema digests drift from SCHEMA_MIRROR manifests."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_mirror(mirror_path: Path, schema_dir: Path) -> list[str]:
    errors: list[str] = []
    mirror = json.loads(mirror_path.read_text(encoding="utf-8"))
    local = mirror.get("local_digests") or {}
    for name, expected in local.items():
        path = schema_dir / name
        if not path.is_file():
            errors.append(f"missing vendored schema: {path}")
            continue
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            errors.append(f"digest drift for {name}: expected {expected}, got {digest}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(
        check_mirror(ROOT / "schemas/pcs/SCHEMA_MIRROR.json", ROOT / "schemas/pcs")
    )
    errors.extend(
        check_mirror(ROOT / "schemas/pip/SCHEMA_MIRROR.json", ROOT / "schemas/pip")
    )
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print("schema mirrors OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
