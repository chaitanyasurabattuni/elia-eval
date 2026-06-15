import pytest
from unittest.mock import MagicMock
from src.eval.runner import EvalRunner
from src.eval.client import EliaCallResult

MOCK_CASE = {
    "id": "ml-001",
    "category": "meal_logging",
    "request": "I ate eggs for breakfast.",
    "user_id": 1,
    "user_name": "Demo",
    "suite": ["smoke", "full"],
    "expected": {
        "semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
        "actions_taken": {"type": "dict", "has_keys": ["what", "meal_type"]}
    },
    "quality": {"must_not_contain": ["error"], "invoke_judge": False}
}

GOOD_RESPONSE = EliaCallResult(
    raw={
        "semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
        "actions_taken": {"what": ["eggs"], "meal_type": "breakfast"},
        "text": "Got it! I logged eggs for breakfast.",
    },
    latency_ms=310,
)

BAD_RESPONSE = EliaCallResult(
    raw={
        "semantic": {"domain": "sleep", "intent": "interrogative", "intent_subtype": None},
        "actions_taken": None,
        "text": "I cannot process this.",
    },
    latency_ms=200,
)


def test_passing_case():
    runner = EvalRunner(client=MagicMock(), judge=None)
    runner._client.call.return_value = GOOD_RESPONSE
    result = runner.run_case(MOCK_CASE)
    assert result.passed is True
    assert result.case_id == "ml-001"
    assert result.latency_ms == 310
    assert result.assertion_failures == []


def test_failing_case():
    runner = EvalRunner(client=MagicMock(), judge=None)
    runner._client.call.return_value = BAD_RESPONSE
    result = runner.run_case(MOCK_CASE)
    assert result.passed is False
    assert len(result.assertion_failures) > 0


def test_run_suite_returns_all_results():
    runner = EvalRunner(client=MagicMock(), judge=None)
    runner._client.call.return_value = GOOD_RESPONSE
    cases = [MOCK_CASE, {**MOCK_CASE, "id": "ml-002"}]
    results = runner.run_suite(cases)
    assert len(results) == 2


def test_judge_invoked_when_requested():
    from src.eval.judge import JudgeResult
    mock_judge = MagicMock()
    mock_judge.maybe_score.return_value = JudgeResult(score=0.9, reasoning="Good", issues=[])
    case_with_judge = {**MOCK_CASE, "quality": {"invoke_judge": True}}
    runner = EvalRunner(client=MagicMock(), judge=mock_judge)
    runner._client.call.return_value = GOOD_RESPONSE
    result = runner.run_case(case_with_judge)
    assert result.judge_score == pytest.approx(0.9)
    mock_judge.maybe_score.assert_called_once()
