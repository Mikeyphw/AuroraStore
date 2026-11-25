#!/usr/bin/env python3
"""R0: verify that the fork still descends from the source-pinned baseline.

No third-party Python packages or local Android SDK are needed.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import sys

UPSTREAM_SHA = "89933d4a2c138a3452486c5eb6e5c2e0df578470"
ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "gradlew",
    "gradle/wrapper/gradle-wrapper.properties",
    "gradle/libs.versions.toml",
    "app/build.gradle.kts",
    ".github/workflows/aurora-foundation.yml",
    "docs/FORK_ROADMAP.md",
)


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        print(f"R0_CONTRACT_FAIL missing files: {', '.join(missing)}", file=sys.stderr)
        return 1

    wrapper = (ROOT / "gradle/wrapper/gradle-wrapper.properties").read_text()
    if "gradle-9.6.0-bin.zip" not in wrapper:
        print("R0_CONTRACT_NOTE Gradle wrapper changed since baseline")

    versions = (ROOT / "gradle/libs.versions.toml").read_text()
    if 'androidGradlePlugin = "9.4.1"' not in versions:
        print("R0_CONTRACT_NOTE Android Gradle plugin changed since baseline")

    if run_git("cat-file", "-e", f"{UPSTREAM_SHA}^{{commit}}").returncode != 0:
        print("R0_CONTRACT_FAIL initial upstream commit not in Git history", file=sys.stderr)
        return 1

    if run_git("merge-base", "--is-ancestor", UPSTREAM_SHA, "HEAD").returncode != 0:
        print("R0_CONTRACT_FAIL HEAD is not descended from pinned upstream commit", file=sys.stderr)
        return 1

    print(f"R0_SOURCE_CONTRACT_PASS upstream={UPSTREAM_SHA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
