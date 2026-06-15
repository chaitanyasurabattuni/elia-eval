import pytest
from datetime import datetime
from src.storage.db import EvalDB
from src.storage.models import EvalResult, EvalRun


@pytest.fixture
def db(tmp_path):
    d = EvalDB(str(tmp_path / "test.db"))
    d.init_schema()
    return d


def _run(run_id="run-001", accuracy=0.875):
    return EvalRun(
        run_id=run_id, commit_sha="abc1234", branch="dev", suite="smoke",
        triggered_by="push", timestamp=datetime.utcnow().isoformat(),
        intent_accuracy=accuracy, error_rate=0.0, latency_p50_ms=320,
        latency_p95_ms=980, total_cost_usd=0.0042, gate_passed=True,
        gate_failures=[], cases_run=8, cases_passed=7, cases_failed=1,
    )


def _result(run_id="run-001", case_id="ml-001"):
    return EvalResult(
        run_id=run_id, case_id=case_id, category="meal_logging", passed=True,
        assertion_failures_json="[]", latency_ms=310, cost_usd=0.0005,
        judge_score=0.9, judge_reasoning="Good", commit_sha="abc1234",
        branch="dev", timestamp=datetime.utcnow().isoformat(),
    )


def test_save_and_retrieve_run(db):
    db.save_run(_run())
    retrieved = db.get_run("run-001")
    assert retrieved.intent_accuracy == pytest.approx(0.875)
    assert retrieved.cases_run == 8
    assert retrieved.gate_passed is True


def test_save_and_retrieve_results(db):
    db.save_run(_run())
    db.save_result(_result())
    results = db.get_results_for_run("run-001")
    assert len(results) == 1
    assert results[0].case_id == "ml-001"
    assert results[0].judge_score == pytest.approx(0.9)


def test_get_case_history(db):
    for i in range(3):
        db.save_run(_run(run_id=f"run-00{i}"))
        db.save_result(_result(run_id=f"run-00{i}", case_id="ml-001"))
    history = db.get_case_history("ml-001", limit=10)
    assert len(history) == 3


def test_get_recent_runs(db):
    for i in range(5):
        db.save_run(_run(run_id=f"run-{i:03d}"))
    runs = db.get_recent_runs(limit=3)
    assert len(runs) == 3


def test_run_not_found_returns_none(db):
    assert db.get_run("nonexistent") is None
