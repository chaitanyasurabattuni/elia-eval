import pytest
from unittest.mock import MagicMock, patch
from src.eval.judge import ResponseJudge, JudgeResult


def _mock_anthropic_response(content: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=content)]
    return msg


def test_judge_returns_score_and_reasoning():
    judge = ResponseJudge(api_key="test-key")
    mock_resp = _mock_anthropic_response('{"score": 0.85, "reasoning": "Good response", "issues": []}')
    with patch.object(judge._client.messages, "create", return_value=mock_resp):
        result = judge.score(
            user_request="What do you recommend I eat for lunch?",
            response_text="I recommend a grilled chicken salad with lots of vegetables.",
            category="recommendations"
        )
    assert isinstance(result, JudgeResult)
    assert result.score == pytest.approx(0.85)
    assert "Good response" in result.reasoning
    assert result.issues == []


def test_judge_handles_low_quality_response():
    judge = ResponseJudge(api_key="test-key")
    mock_resp = _mock_anthropic_response('{"score": 0.2, "reasoning": "Vague, unhelpful", "issues": ["too vague", "no specific foods"]}')
    with patch.object(judge._client.messages, "create", return_value=mock_resp):
        result = judge.score(
            user_request="What should I eat for dinner?",
            response_text="Eat food.",
            category="recommendations"
        )
    assert result.score == pytest.approx(0.2)
    assert len(result.issues) == 2


def test_judge_handles_parse_error_gracefully():
    judge = ResponseJudge(api_key="test-key")
    mock_resp = _mock_anthropic_response("This is not JSON at all")
    with patch.object(judge._client.messages, "create", return_value=mock_resp):
        result = judge.score("q", "a", "meal_logging")
    assert 0.0 <= result.score <= 1.0
    assert result.reasoning
    assert "parse_error" in result.issues


def test_judge_skipped_when_not_requested():
    judge = ResponseJudge(api_key="test-key")
    case = {"quality": {"invoke_judge": False}}
    result = judge.maybe_score(
        user_request="I ate eggs",
        response_text="Got it, logged eggs.",
        case=case
    )
    assert result is None


def test_judge_invoked_when_requested():
    judge = ResponseJudge(api_key="test-key")
    mock_resp = _mock_anthropic_response('{"score": 0.9, "reasoning": "Excellent", "issues": []}')
    case = {"quality": {"invoke_judge": True}, "category": "recommendations"}
    with patch.object(judge._client.messages, "create", return_value=mock_resp):
        result = judge.maybe_score("What to eat?", "Try a salad.", case)
    assert result is not None
    assert result.score == pytest.approx(0.9)
