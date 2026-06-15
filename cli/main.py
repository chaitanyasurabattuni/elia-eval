import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.eval.case_loader import load_suite
from src.eval.client import EliaClient, EliaClientMode
from src.eval.judge import ResponseJudge
from src.eval.runner import EvalRunner
from src.eval.metrics import MetricsEngine
from src.storage.db import EvalDB
from src.storage.models import EvalResult, EvalRun

app = typer.Typer(help="Elia LLM Eval CI/CD Pipeline")
console = Console()

BASELINE_PATH = Path("results/baseline.json")

GATE_THRESHOLDS = {
    "intent_accuracy_min": 0.80,
    "error_rate_max": 0.10,
    "latency_p95_max_ms": 10000,
}


@app.command()
def run(
    suite: str = typer.Option("smoke", "--suite", "-s", help="Suite to run: smoke|full"),
    mode: str = typer.Option("http", "--mode", "-m", help="Client mode: http|testclient"),
    url: str = typer.Option("http://localhost:8001", "--url", help="Elia server URL (http mode)"),
    commit: str = typer.Option("local", "--commit", help="Commit SHA for tracking"),
    branch: str = typer.Option("local", "--branch", help="Branch name for tracking"),
    no_judge: bool = typer.Option(False, "--no-judge", help="Skip LLM judge"),
    db_path: str = typer.Option("results/eval.db", "--db"),
):
    """Run eval suite against Elia."""
    client_mode = EliaClientMode.TESTCLIENT if mode == "testclient" else EliaClientMode.HTTP
    client = EliaClient(mode=client_mode, base_url=url)
    judge = None if no_judge else ResponseJudge()

    runner = EvalRunner(client=client, judge=judge)
    db = EvalDB(db_path)
    db.init_schema()

    cases = load_suite(suite)
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    console.print(f"\n[bold]Elia Eval[/bold] — suite=[cyan]{suite}[/cyan]  cases=[cyan]{len(cases)}[/cyan]  mode=[cyan]{mode}[/cyan]\n")

    results = []
    for case in cases:
        r = runner.run_case(case)
        results.append(r)
        icon = "✅" if r.passed else "❌"
        console.print(f"  {icon} {case['id']:20s}  {r.latency_ms:4d}ms")

    metrics = MetricsEngine.compute(results)

    gate_failures = []
    if metrics.intent_accuracy < GATE_THRESHOLDS["intent_accuracy_min"]:
        gate_failures.append(f"intent_accuracy {metrics.intent_accuracy:.1%} < {GATE_THRESHOLDS['intent_accuracy_min']:.0%} minimum")
    if metrics.error_rate > GATE_THRESHOLDS["error_rate_max"]:
        gate_failures.append(f"error_rate {metrics.error_rate:.1%} > {GATE_THRESHOLDS['error_rate_max']:.0%} maximum")
    if metrics.latency_p95 > GATE_THRESHOLDS["latency_p95_max_ms"]:
        gate_failures.append(f"latency_p95 {metrics.latency_p95}ms > {GATE_THRESHOLDS['latency_p95_max_ms']}ms SLA")

    gate_passed = len(gate_failures) == 0

    for r in results:
        db.save_result(EvalResult(
            run_id=run_id, case_id=r.case_id, category=r.category, passed=r.passed,
            assertion_failures_json=json.dumps([{"field": f.field, "message": f.message} for f in r.assertion_failures]),
            latency_ms=r.latency_ms, cost_usd=r.cost_usd,
            judge_score=r.judge_score, judge_reasoning=None,
            commit_sha=commit, branch=branch, timestamp=timestamp,
        ))

    db.save_run(EvalRun(
        run_id=run_id, commit_sha=commit, branch=branch, suite=suite,
        triggered_by="cli", timestamp=timestamp,
        intent_accuracy=metrics.intent_accuracy, error_rate=metrics.error_rate,
        latency_p50_ms=metrics.latency_p50, latency_p95_ms=metrics.latency_p95,
        total_cost_usd=metrics.total_cost_usd, gate_passed=gate_passed,
        gate_failures=gate_failures, cases_run=metrics.cases_run,
        cases_passed=metrics.cases_passed, cases_failed=metrics.cases_failed,
    ))

    table = Table(title=f"\nRun {run_id} Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Intent Accuracy", f"{metrics.intent_accuracy:.1%}" + (" ✅" if gate_passed or metrics.intent_accuracy >= GATE_THRESHOLDS["intent_accuracy_min"] else " ❌"))
    table.add_row("Error Rate", f"{metrics.error_rate:.1%}")
    table.add_row("Latency p50", f"{metrics.latency_p50}ms")
    table.add_row("Latency p95", f"{metrics.latency_p95}ms")
    table.add_row("Total Cost", f"${metrics.total_cost_usd:.4f}")
    table.add_row("Cases", f"{metrics.cases_passed}/{metrics.cases_run} passed")
    console.print(table)

    if gate_failures:
        console.print("\n[red bold]GATE FAILED:[/red bold]")
        for gf in gate_failures:
            console.print(f"  ❌ {gf}")
        raise typer.Exit(code=1)

    console.print(f"\n[green bold]✅ Gate passed[/green bold] — run_id={run_id}")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run ID to report on"),
    db_path: str = typer.Option("results/eval.db", "--db"),
):
    """Show detailed report for a run."""
    db = EvalDB(db_path)
    run = db.get_run(run_id)
    if not run:
        console.print(f"[red]Run {run_id} not found[/red]")
        raise typer.Exit(1)

    results = db.get_results_for_run(run_id)
    console.print(f"\n[bold]Run {run_id}[/bold]  branch={run.branch}  commit={run.commit_sha[:7]}  suite={run.suite}")
    console.print(f"Accuracy: {run.intent_accuracy:.1%}  Latency p95: {run.latency_p95_ms}ms  Cost: ${run.total_cost_usd:.4f}")

    failed = [r for r in results if not r.passed]
    if failed:
        console.print(f"\n[red]Failed cases ({len(failed)}):[/red]")
        for r in failed:
            failures = json.loads(r.assertion_failures_json)
            for f in failures:
                console.print(f"  {r.case_id}: [{f['field']}] {f['message']}")
    else:
        console.print("\n[green]All cases passed ✅[/green]")


@app.command()
def baseline(
    run_id: str = typer.Argument(..., help="Run ID to set as baseline"),
    db_path: str = typer.Option("results/eval.db", "--db"),
):
    """Set a run as the baseline for regression comparison."""
    db = EvalDB(db_path)
    run = db.get_run(run_id)
    if not run:
        console.print(f"[red]Run {run_id} not found[/red]")
        raise typer.Exit(1)
    BASELINE_PATH.parent.mkdir(exist_ok=True)
    BASELINE_PATH.write_text(json.dumps({
        "run_id": run_id,
        "intent_accuracy": run.intent_accuracy,
        "latency_p95_ms": run.latency_p95_ms,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    console.print(f"[green]Baseline set to run {run_id}[/green]")


if __name__ == "__main__":
    app()
