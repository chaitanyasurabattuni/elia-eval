from typing import List, Optional
from src.eval.metrics import CaseResult
from src.storage.models import EvalRun


def generate_pr_comment(
    run: EvalRun,
    results: List[CaseResult],
    baseline: Optional[dict] = None,
) -> str:
    lines = ["## Elia Eval Results\n"]

    def pct_delta(current, base_key):
        if not baseline or base_key not in baseline:
            return ""
        diff = current - baseline[base_key]
        sign = "+" if diff >= 0 else ""
        return f" ({sign}{diff:.1%})"

    gate_icon = "✅" if run.gate_passed else "❌"
    lines.append(
        f"**Gate:** {gate_icon} {'Passed' if run.gate_passed else 'FAILED'}  |  "
        f"Run `{run.run_id[:8]}`  |  Branch `{run.branch}`  |  Commit `{run.commit_sha[:7]}`\n"
    )

    lines.append("| Metric | Value | Status |")
    lines.append("|--------|-------|--------|")
    lines.append(f"| Intent Accuracy | {run.intent_accuracy:.1%}{pct_delta(run.intent_accuracy, 'intent_accuracy')} | {'✅' if run.intent_accuracy >= 0.80 else '❌'} |")
    lines.append(f"| Error Rate | {run.error_rate:.1%} | {'✅' if run.error_rate <= 0.10 else '❌'} |")
    lines.append(f"| Latency p95 | {run.latency_p95_ms}ms | {'✅' if run.latency_p95_ms <= 10000 else '⚠️'} |")
    lines.append(f"| Cost / run | ${run.total_cost_usd:.4f} | — |")
    lines.append(f"| Cases | {run.cases_passed}/{run.cases_run} passed | — |\n")

    failed_results = [r for r in results if not r.passed]
    if failed_results:
        lines.append(f"### ❌ Failing Cases ({len(failed_results)})\n")
        for r in failed_results[:10]:
            lines.append(f"- **{r.case_id}** ({r.category})")
            for f in r.assertion_failures[:2]:
                lines.append(f"  - `{f.field}`: {f.message}")
        if len(failed_results) > 10:
            lines.append(f"\n_...and {len(failed_results) - 10} more_")

    if run.gate_failures:
        lines.append("\n### ❌ Gate Failures\n")
        for gf in run.gate_failures:
            lines.append(f"- {gf}")

    lines.append("\n---\n_🤖 [elia-eval](https://github.com/chaitanyasurabattuni/elia-eval)_")
    return "\n".join(lines)
