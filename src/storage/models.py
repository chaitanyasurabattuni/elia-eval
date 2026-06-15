from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvalResult:
    run_id: str
    case_id: str
    category: str
    passed: bool
    assertion_failures_json: str
    latency_ms: int
    cost_usd: float
    judge_score: Optional[float]
    judge_reasoning: Optional[str]
    commit_sha: str
    branch: str
    timestamp: str


@dataclass
class EvalRun:
    run_id: str
    commit_sha: str
    branch: str
    suite: str
    triggered_by: str
    timestamp: str
    intent_accuracy: float
    error_rate: float
    latency_p50_ms: int
    latency_p95_ms: int
    total_cost_usd: float
    gate_passed: bool
    gate_failures: List[str]
    cases_run: int
    cases_passed: int
    cases_failed: int
