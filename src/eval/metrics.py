from dataclasses import dataclass, field
from typing import Dict, List, Optional
import statistics
from src.eval.assertions import AssertionFailure


@dataclass
class CaseResult:
    case_id: str
    category: str
    passed: bool
    assertion_failures: List[AssertionFailure]
    latency_ms: int
    cost_usd: float
    judge_score: Optional[float]


@dataclass
class RunMetrics:
    intent_accuracy: float
    error_rate: float
    latency_p50: int
    latency_p95: int
    total_cost_usd: float
    avg_cost_per_query_usd: float
    avg_judge_score: Optional[float]
    accuracy_by_category: Dict[str, float]
    cases_run: int
    cases_passed: int
    cases_failed: int


class MetricsEngine:
    @staticmethod
    def compute(results: List[CaseResult]) -> RunMetrics:
        if not results:
            raise ValueError("No results to compute metrics from")

        n = len(results)
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        errors = [r for r in results if any(f.field == "error" for f in r.assertion_failures)]

        latencies = sorted(r.latency_ms for r in results)
        p50 = int(statistics.median(latencies))
        p95_idx = max(0, int(0.95 * n) - 1)
        p95 = latencies[p95_idx]

        total_cost = sum(r.cost_usd for r in results)

        judge_scores = [r.judge_score for r in results if r.judge_score is not None]
        avg_judge = statistics.mean(judge_scores) if judge_scores else None

        categories: Dict[str, List[bool]] = {}
        for r in results:
            categories.setdefault(r.category, []).append(r.passed)
        accuracy_by_category = {
            cat: sum(vals) / len(vals) for cat, vals in categories.items()
        }

        return RunMetrics(
            intent_accuracy=len(passed) / n,
            error_rate=len(errors) / n,
            latency_p50=p50,
            latency_p95=p95,
            total_cost_usd=total_cost,
            avg_cost_per_query_usd=total_cost / n,
            avg_judge_score=avg_judge,
            accuracy_by_category=accuracy_by_category,
            cases_run=n,
            cases_passed=len(passed),
            cases_failed=len(failed),
        )
