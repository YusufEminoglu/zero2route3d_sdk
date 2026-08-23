#!/usr/bin/env python3
"""Bump the project version and prepend a CHANGELOG entry for a release.

Usage:
    python .github/scripts/prepare_release.py <version>

Run from the repository root. Updates ``pyproject.toml`` and ``CHANGELOG.md``
in place; the changelog entry is populated from commit subjects since the last
git tag.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def bump_version_files(version: str) -> None:
    # 1. pyproject.toml
    path = ROOT / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'(?m)^version\s*=\s*"[^"]*"', f'version = "{version}"', text, count=1
    )
    if count != 1:
        raise SystemExit("error: could not find a version line in pyproject.toml")
    path.write_text(new_text, encoding="utf-8")

    # 2. src/zero2route3d/__init__.py
    init_path = ROOT / "src" / "zero2route3d" / "__init__.py"
    if init_path.exists():
        init_text = init_path.read_text(encoding="utf-8")
        new_init_text, count = re.subn(
            r'(?m)^__version__\s*=\s*"[^"]*"', f'__version__ = "{version}"', init_text, count=1
        )
        if count != 1:
            raise SystemExit("error: could not find __version__ in src/zero2route3d/__init__.py")
        init_path.write_text(new_init_text, encoding="utf-8")


def changelog_bullets() -> list[str]:
    try:
        rng = f"{_git('describe', '--tags', '--abbrev=0')}..HEAD"
    except subprocess.CalledProcessError:
        rng = "HEAD"  # no tags yet
    log = _git("log", rng, "--no-merges", "--pretty=format:- %s")
    return [line for line in log.splitlines() if line.strip()] or ["- (no changes recorded)"]


def update_changelog(version: str, bullets: list[str]) -> None:
    path = ROOT / "CHANGELOG.md"
    today = dt.date.today().isoformat()
    entry = [f"## [{version}] - {today}", "### Changed", *bullets, "", "---"]

    lines = path.read_text(encoding="utf-8").splitlines()
    sep = next((i for i, ln in enumerate(lines) if ln.strip() == "---"), None)
    if sep is None:
        new_lines = [*lines, "", "---", "", *entry]
    else:
        new_lines = [*lines[: sep + 1], "", *entry, *lines[sep + 1 :]]
    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: prepare_release.py <version>", file=sys.stderr)
        return 2
    version = sys.argv[1].lstrip("v")
    bump_version_files(version)
    bullets = changelog_bullets()
    update_changelog(version, bullets)
    print(f"Prepared release {version} with {len(bullets)} changelog line(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
