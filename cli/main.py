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


def _print_summary(metrics, run_id, gate_failures):
    table = Table(title=f"\nRun {run_id} Summary")
    table.add_column("Metric")
    table.add_column("Value")
    sem_ok = metrics.semantic_accuracy >= GATE_THRESHOLDS["intent_accuracy_min"]
    full_ok = metrics.intent_accuracy >= GATE_THRESHOLDS["intent_accuracy_min"]
    table.add_row("Semantic Accuracy", f"{metrics.semantic_accuracy:.1%}" + (" ✅" if sem_ok else " ❌"))
    table.add_row("Full Accuracy", f"{metrics.intent_accuracy:.1%}" + (" ✅" if full_ok else " ❌"))
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
    else:
        console.print(f"\n[green bold]✅ Gate passed[/green bold] — run_id={run_id}")


@app.command()
def run(
    suite: str = typer.Option("smoke", "--suite", "-s", help="Suite to run: smoke|full"),
    mode: str = typer.Option("http", "--mode", "-m", help="Client mode: http|testclient"),
    url: str = typer.Option("http://localhost:8001", "--url", help="Elia server URL (http mode)"),
    commit: str = typer.Option("local", "--commit", help="Commit SHA for tracking"),
    branch: str = typer.Option("local", "--branch", help="Branch name for tracking"),
    no_judge: bool = typer.Option(False, "--no-judge", help="Skip LLM judge"),
    layer: str = typer.Option("full", "--layer", help="Assertion layer: full|semantic"),
    db_path: str = typer.Option("results/eval.db", "--db"),
):
    """Run eval suite against Elia."""
    client_mode = EliaClientMode.TESTCLIENT if mode == "testclient" else EliaClientMode.HTTP
    client = EliaClient(mode=client_mode, base_url=url)
    judge = None if no_judge else ResponseJudge()

    runner = EvalRunner(client=client, judge=judge, layer=layer)
    db = EvalDB(db_path)
    db.init_schema()

    cases = load_suite(suite)
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    console.print(f"\n[bold]Elia Eval[/bold] — suite=[cyan]{suite}[/cyan]  cases=[cyan]{len(cases)}[/cyan]  mode=[cyan]{mode}[/cyan]  layer=[cyan]{layer}[/cyan]\n")

    results = []
    for case in cases:
        r = runner.run_case(case)
        results.append(r)
        icon = "✅" if r.passed else ("🟡" if r.semantic_passed else "❌")
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

    _print_summary(metrics, run_id, gate_failures)

    if gate_failures:
        raise typer.Exit(code=1)


@app.command()
def gold(
    csv_path: str = typer.Argument(..., help="Path to tool_selection_synthetic.csv"),
    mode: str = typer.Option("testclient", "--mode", "-m", help="Client mode: http|testclient"),
    url: str = typer.Option("http://localhost:8001", "--url"),
    commit: str = typer.Option("local", "--commit"),
    branch: str = typer.Option("local", "--branch"),
    limit: int = typer.Option(0, "--limit", help="Cap number of cases (0 = all)"),
    db_path: str = typer.Option("results/eval.db", "--db"),
):
    """Evaluate entry agents (phrase parser, domain + intent classifier) against the 400-item gold dataset."""
    from src.eval.gold_loader import load_gold_dataset

    client_mode = EliaClientMode.TESTCLIENT if mode == "testclient" else EliaClientMode.HTTP
    client = EliaClient(mode=client_mode, base_url=url)
    runner = EvalRunner(client=client, judge=None, layer="semantic")

    cases = load_gold_dataset(csv_path)
    if limit:
        cases = cases[:limit]

    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    console.print(f"\n[bold]Gold Dataset Eval[/bold] — cases=[cyan]{len(cases)}[/cyan]  mode=[cyan]{mode}[/cyan]  layer=[cyan]semantic[/cyan]\n")

    results = []
    domain_hits: dict = {}
    domain_totals: dict = {}

    for i, case in enumerate(cases, 1):
        r = runner.run_case(case)
        results.append(r)
        cat = case["category"]
        domain_totals[cat] = domain_totals.get(cat, 0) + 1
        if r.semantic_passed:
            domain_hits[cat] = domain_hits.get(cat, 0) + 1
        if i % 50 == 0:
            pct = sum(r.semantic_passed for r in results) / i
            console.print(f"  [{i}/{len(cases)}] semantic accuracy so far: {pct:.1%}")

    metrics = MetricsEngine.compute(results)

    # Per-domain accuracy table
    domain_table = Table(title=f"\nGold Dataset — Semantic Accuracy by Domain  (run {run_id})")
    domain_table.add_column("Domain")
    domain_table.add_column("Correct", justify="right")
    domain_table.add_column("Total", justify="right")
    domain_table.add_column("Accuracy", justify="right")
    for domain in sorted(domain_totals):
        hits = domain_hits.get(domain, 0)
        total = domain_totals[domain]
        pct = hits / total
        color = "green" if pct >= 0.8 else ("yellow" if pct >= 0.6 else "red")
        domain_table.add_row(domain, str(hits), str(total), f"[{color}]{pct:.1%}[/{color}]")
    console.print(domain_table)

    summary = Table(title="Overall")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Domain + Tool Accuracy", f"{metrics.semantic_accuracy:.1%}")
    summary.add_row("Latency p50", f"{metrics.latency_p50}ms")
    summary.add_row("Latency p95", f"{metrics.latency_p95}ms")
    summary.add_row("Total Cost", f"${metrics.total_cost_usd:.4f}")
    summary.add_row("Cases", f"{metrics.cases_run} evaluated")
    console.print(summary)

    # Show failures grouped by category
    failures = [r for r in results if not r.semantic_passed]
    if failures:
        console.print(f"\n[red]Failed: {len(failures)} cases[/red]")
        shown = 0
        for r in failures:
            if shown >= 20:
                console.print(f"  ... and {len(failures) - shown} more")
                break
            for f in r.assertion_failures:
                console.print(f"  {r.case_id} [{r.category}]: {f.message}")
            shown += 1


@app.command()
def routing(
    tiny_csv: str = typer.Argument(..., help="Path to routing_synthetic_tiny.csv"),
    medium_csv: str = typer.Argument(..., help="Path to routing_synthetic_medium.csv"),
):
    """Compare phrase-parser accuracy between the tiny and medium pre-computed benchmark runs."""
    from src.eval.routing_loader import load_routing_results, summarise_routing

    tiny = summarise_routing(load_routing_results(tiny_csv))
    medium = summarise_routing(load_routing_results(medium_csv))

    # Overall comparison
    overview = Table(title="Tiny vs Medium Model — Overall")
    overview.add_column("Metric")
    overview.add_column("Tiny", justify="right")
    overview.add_column("Medium", justify="right")
    overview.add_column("Better", justify="center")

    def _better(t, m, higher_is_better=True):
        if t is None or m is None:
            return "-"
        if higher_is_better:
            return "medium ✅" if m > t else ("tiny ✅" if t > m else "tie")
        return "medium ✅" if m < t else ("tiny ✅" if t < m else "tie")

    metrics = [
        ("Full pass rate", "full_pass", True),
        ("Domain accuracy", "domain_accuracy", True),
        ("Action accuracy", "action_accuracy", True),
        ("Avg latency (s)", "avg_latency_s", False),
    ]
    for label, key, higher in metrics:
        t_val = tiny.get(key)
        m_val = medium.get(key)
        t_str = f"{t_val:.1%}" if isinstance(t_val, float) and key != "avg_latency_s" else f"{t_val:.2f}s" if t_val is not None else "-"
        m_str = f"{m_val:.1%}" if isinstance(m_val, float) and key != "avg_latency_s" else f"{m_val:.2f}s" if m_val is not None else "-"
        overview.add_row(label, t_str, m_str, _better(t_val, m_val, higher))
    console.print(overview)

    # Per-domain breakdown
    all_domains = sorted(set(list(tiny["by_domain"].keys()) + list(medium["by_domain"].keys())))
    domain_table = Table(title="Per-Domain Full Pass Rate")
    domain_table.add_column("Domain")
    domain_table.add_column("Tiny", justify="right")
    domain_table.add_column("Medium", justify="right")
    domain_table.add_column("Delta", justify="right")

    for domain in all_domains:
        t = tiny["by_domain"].get(domain, {})
        m = medium["by_domain"].get(domain, {})
        t_pass = t.get("full_pass")
        m_pass = m.get("full_pass")
        t_str = f"{t_pass:.1%}" if t_pass is not None else "-"
        m_str = f"{m_pass:.1%}" if m_pass is not None else "-"
        if t_pass is not None and m_pass is not None:
            delta = m_pass - t_pass
            color = "green" if delta > 0 else ("red" if delta < 0 else "white")
            delta_str = f"[{color}]{delta:+.1%}[/{color}]"
        else:
            delta_str = "-"
        domain_table.add_row(domain, t_str, m_str, delta_str)
    console.print(domain_table)


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
