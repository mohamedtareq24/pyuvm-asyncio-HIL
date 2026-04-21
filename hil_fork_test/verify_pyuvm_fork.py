#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata as md
import json
import os
from pathlib import Path


EXPECTED = os.getenv("EXPECTED_PYUVM_REPO", "mohamedtareq24/pyuvm-asyncio-HIL")


def read_direct_url(dist_name: str) -> dict | None:
    try:
        dist = md.distribution(dist_name)
    except md.PackageNotFoundError:
        return None
    text = dist.read_text("direct_url.json")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def main() -> int:
    try:
        import pyuvm  # pylint: disable=import-outside-toplevel
    except Exception as exc:
        print(f"FAIL: cannot import pyuvm: {exc}")
        return 2

    print(f"pyuvm path   : {Path(pyuvm.__file__).resolve()}")
    try:
        print(f"pyuvm version: {md.version('pyuvm')}")
    except md.PackageNotFoundError:
        print("pyuvm version: unknown")

    direct = read_direct_url("pyuvm")
    if direct is None:
        print("WARN: no direct_url metadata (non-VCS install).")
        return 0

    url = direct.get("url", "")
    vcs = direct.get("vcs_info", {})
    print(f"source url   : {url or 'unknown'}")
    if vcs.get("requested_revision"):
        print(f"source ref   : {vcs['requested_revision']}")
    if vcs.get("commit_id"):
        print(f"source commit: {vcs['commit_id']}")

    if EXPECTED in url:
        print("PASS: pyuvm installed from pyuvm-asyncio-HIL fork")
        return 0

    print("WARN: pyuvm source is not the expected HIL fork")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
