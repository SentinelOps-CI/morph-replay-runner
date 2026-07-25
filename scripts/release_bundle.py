#!/usr/bin/env python3
"""Build a release checksum bundle for schemas and example evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release-bundle"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    entries: dict[str, str] = {}
    for pattern in (
        "schemas/mrr/*.json",
        "schemas/pcs/*.json",
        "schemas/pip/*.json",
        "examples/hermetic-branch-n/**/*",
        "fixtures/pip/valid_replay_linkage/*",
    ):
        for path in ROOT.glob(pattern):
            if path.is_file():
                rel = path.relative_to(ROOT).as_posix()
                entries[rel] = file_digest(path)
    payload = {
        "schema_version": "mrr.ReleaseChecksums.v1",
        "files": dict(sorted(entries.items())),
    }
    (OUT / "checksums.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'checksums.json'} ({len(entries)} files)")


if __name__ == "__main__":
    main()
