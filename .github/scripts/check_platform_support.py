#!/usr/bin/env python3
"""
Check whether a Docker manifest supports a requested platform.

This helper reads the JSON output produced by:

    docker buildx imagetools inspect --format '{{json .}}' <image>

It then reports whether the requested platform (formatted as "os/arch") is
present in the manifest list. The script prints "true" or "false" to stdout so
that workflows can capture the value in shell scripts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_platform(platform: str) -> tuple[str, str]:
    """Parse a platform string into (os, architecture) components."""
    parts = platform.split("/")
    if len(parts) != 2 or any(not part for part in parts):
        raise ValueError(
            f"Unexpected platform format: {platform}. Expected format: "
            "os/architecture (e.g., linux/amd64)."
        )
    return parts[0], parts[1]


def load_manifest(path: Path) -> dict[str, Any]:
    """Load the JSON manifest from the provided file path."""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Manifest JSON not found: {path}") from exc
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest JSON is invalid: {path}") from exc


def extract_platforms(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract platform entries from a manifest list or single manifest."""
    platforms = data.get("platforms") or []
    if not platforms and isinstance(data.get("manifest"), dict):
        manifest_platform = data["manifest"].get("platform")
        if manifest_platform:
            platforms = [manifest_platform]
    if not isinstance(platforms, list):
        return []
    return [entry for entry in platforms if isinstance(entry, dict)]


def is_platform_supported(platforms: list[dict[str, Any]], os_name: str, arch: str) -> bool:
    """Return True when any manifest entry matches the requested platform."""
    return any(
        entry.get("os") == os_name and entry.get("architecture") == arch
        for entry in platforms
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for platform support checks."""
    parser = argparse.ArgumentParser(
        description=(
            "Check if a Docker manifest JSON includes the specified platform."
        )
    )
    parser.add_argument(
        "--platform",
        required=True,
        help="Target platform in os/arch format (e.g., linux/amd64).",
    )
    parser.add_argument(
        "--inspect-json",
        required=True,
        type=Path,
        help=(
            "Path to the manifest JSON captured from "
            "`docker buildx imagetools inspect --format '{{json .}}'`."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Run the platform availability check."""
    args = parse_args()
    os_name, arch = parse_platform(args.platform)
    manifest = load_manifest(args.inspect_json)
    platforms = extract_platforms(manifest)
    supported = is_platform_supported(platforms, os_name, arch)
    print("true" if supported else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
