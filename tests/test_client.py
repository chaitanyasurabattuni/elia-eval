import pytest
from unittest.mock import MagicMock, patch
from src.eval.client import EliaClient, EliaClientMode, EliaCallResult

def test_http_client_builds_payload():
    client = EliaClient(mode=EliaClientMode.HTTP, base_url="http://localhost:8001")
    # We mock httpx.post so no real server needed
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
        "actions_taken": {"what": ["eggs"], "meal_type": "breakfast"},
        "text": "Got it! I logged eggs for breakfast.",
        "token_usage": {"input_tokens": 150, "output_tokens": 40}
    }
    mock_response.status_code = 200
    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = client.call("I ate eggs", user_id=1, user_name="Demo")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["user_request"] == "I ate eggs"
        assert payload["user_id"] == "1"

def test_call_result_extracts_fields():
    result = EliaCallResult(
        raw={"semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
             "actions_taken": {"what": ["eggs"]}, "text": "Logged eggs."},
        latency_ms=320,
        error=None
    )
    assert result.semantic == {"domain": "nutrition", "intent": "declarative", "intent_subtype": None}
    assert result.actions_taken == {"what": ["eggs"]}
    assert result.text == "Logged eggs."
    assert result.latency_ms == 320
    assert result.token_usage is None

def test_call_result_with_token_usage():
    result = EliaCallResult(
        raw={"semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
             "actions_taken": None, "text": "Hi",
             "token_usage": {"input_tokens": 100, "output_tokens": 50}},
        latency_ms=100,
        error=None
    )
    assert result.token_usage == {"input_tokens": 100, "output_tokens": 50}
    assert result.cost_usd > 0

def test_call_result_handles_error():
    result = EliaCallResult(raw={}, latency_ms=0, error="Connection refused")
    assert result.error == "Connection refused"
    assert result.text is None
