#!/usr/bin/env python3
"""Detects which eval suite to run based on changed files in the PR."""
import json
import os
import subprocess

SUITE_RULES = [
    (["agents/", "health_intelligence/", "engines/", "scoring/"], "full"),
    (["routes/", "app/"], "smoke"),
    (["models/", "services/", "modules/"], "smoke"),
    (["dataset/"], "full"),
]


def get_changed_files() -> list:
    base = os.environ.get("GITHUB_BASE_REF", "main")
    result = subprocess.run(
        ["git", "diff", "--name-only", f"origin/{base}...HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip().splitlines()


def detect_suite(changed_files: list) -> str:
    for prefixes, suite in SUITE_RULES:
        for f in changed_files:
            if any(f.startswith(p) for p in prefixes):
                return suite
    return "smoke"


if __name__ == "__main__":
    changed = get_changed_files()
    suite = detect_suite(changed)
    print(json.dumps({"suite": suite, "changed_files": changed}))
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"suite={suite}\n")
