import pytest
from src.eval.metrics import MetricsEngine, CaseResult, RunMetrics
from src.eval.assertions import AssertionFailure


def _make_case_result(passed=True, semantic_passed=None, latency_ms=300, cost_usd=0.001, category="meal_logging", failures=None):
    return CaseResult(
        case_id="test-001",
        category=category,
        passed=passed,
        semantic_passed=semantic_passed if semantic_passed is not None else passed,
        assertion_failures=failures or [],
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        judge_score=None,
    )


def test_perfect_run():
    results = [_make_case_result(passed=True, latency_ms=300) for _ in range(10)]
    metrics = MetricsEngine.compute(results)
    assert metrics.intent_accuracy == 1.0
    assert metrics.error_rate == 0.0
    assert metrics.latency_p50 == 300
    assert metrics.latency_p95 == 300
    assert metrics.total_cost_usd == pytest.approx(0.01)


def test_partial_failures():
    results = [_make_case_result(passed=True)] * 8 + [_make_case_result(passed=False)] * 2
    metrics = MetricsEngine.compute(results)
    assert metrics.intent_accuracy == pytest.approx(0.8)


def test_latency_percentiles():
    latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 2000]
    results = [_make_case_result(latency_ms=l) for l in latencies]
    metrics = MetricsEngine.compute(results)
    assert metrics.latency_p50 == 550
    # p95_idx = max(0, int(0.95*10)-1) = 8, sorted[8] = 900
    assert metrics.latency_p95 == 900


def test_per_category_accuracy():
    results = [
        _make_case_result(passed=True, category="meal_logging"),
        _make_case_result(passed=True, category="meal_logging"),
        _make_case_result(passed=False, category="recommendations"),
    ]
    metrics = MetricsEngine.compute(results)
    assert metrics.accuracy_by_category["meal_logging"] == 1.0
    assert metrics.accuracy_by_category["recommendations"] == 0.0


def test_error_rate():
    error_failure = AssertionFailure(field="error", message="Connection refused")
    results = [
        _make_case_result(passed=False, failures=[error_failure]),
        _make_case_result(passed=True),
    ]
    metrics = MetricsEngine.compute(results)
    assert metrics.error_rate == pytest.approx(0.5)
