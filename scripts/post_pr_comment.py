#!/usr/bin/env python3
"""Posts eval results as a PR comment via GitHub API."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    token = os.environ.get("GITHUB_TOKEN")
    pr_number = os.environ.get("PR_NUMBER")
    repo = os.environ.get("GITHUB_REPOSITORY", "Prime-Health-Technologies/elia-pathfinder")

    if not token or not pr_number:
        print("Missing GITHUB_TOKEN or PR_NUMBER, skipping comment")
        return

    db_path = Path("results/eval.db")
    if not db_path.exists():
        print("No DB found, skipping comment")
        return

    import httpx
    from src.storage.db import EvalDB
    from src.eval.report import generate_pr_comment
    from src.eval.assertions import AssertionFailure
    from src.eval.metrics import CaseResult

    db = EvalDB(str(db_path))
    runs = db.get_recent_runs(limit=1)
    if not runs:
        return

    run = runs[0]
    db_results = db.get_results_for_run(run.run_id)

    case_results = []
    for r in db_results:
        failures = [
            AssertionFailure(field=f["field"], message=f["message"])
            for f in json.loads(r.assertion_failures_json)
        ]
        case_results.append(CaseResult(
            case_id=r.case_id, category=r.category, passed=r.passed,
            assertion_failures=failures, latency_ms=r.latency_ms,
            cost_usd=r.cost_usd, judge_score=r.judge_score,
        ))

    comment_body = generate_pr_comment(run, case_results)

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    resp = httpx.post(
        url,
        json={"body": comment_body},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    print(f"Posted PR comment: HTTP {resp.status_code}")


if __name__ == "__main__":
    main()
