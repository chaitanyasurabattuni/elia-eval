from src.eval.assertions import AssertionEngine, AssertionFailure
from src.eval.client import EliaCallResult


def _make_result(semantic=None, actions_taken=None, text="OK", token_usage=None, error=None):
    raw = {"semantic": semantic, "actions_taken": actions_taken, "text": text}
    if token_usage:
        raw["token_usage"] = token_usage
    return EliaCallResult(raw=raw, latency_ms=100, error=error)


def test_passes_when_all_match():
    result = _make_result(
        semantic={"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
        actions_taken={"what": ["eggs"], "meal_type": "breakfast"}
    )
    case = {
        "expected": {
            "semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
            "actions_taken": {"type": "dict", "has_keys": ["what", "meal_type"]}
        }
    }
    failures = AssertionEngine.run(result, case)
    assert failures == []


def test_fails_on_wrong_domain():
    result = _make_result(
        semantic={"domain": "sleep", "intent": "declarative", "intent_subtype": None},
        actions_taken={}
    )
    case = {"expected": {"semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None}}}
    failures = AssertionEngine.run(result, case)
    assert any("domain" in f.field for f in failures)


def test_fails_on_wrong_intent():
    result = _make_result(
        semantic={"domain": "nutrition", "intent": "interrogative", "intent_subtype": None},
        actions_taken={}
    )
    case = {"expected": {"semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None}}}
    failures = AssertionEngine.run(result, case)
    assert any("intent" in f.field for f in failures)


def test_fails_on_missing_actions_key():
    result = _make_result(
        semantic={"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
        actions_taken={"what": ["eggs"]}
    )
    case = {
        "expected": {
            "semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
            "actions_taken": {"type": "dict", "has_keys": ["what", "meal_type"]}
        }
    }
    failures = AssertionEngine.run(result, case)
    assert any("meal_type" in f.message for f in failures)


def test_fails_when_actions_should_be_null_but_isnt():
    result = _make_result(
        semantic={"domain": "nutrition", "intent": "action_request", "intent_subtype": None},
        actions_taken={"some": "data"}
    )
    case = {
        "expected": {
            "semantic": {"domain": "nutrition", "intent": "action_request", "intent_subtype": None},
            "actions_taken": {"type": "null"}
        }
    }
    failures = AssertionEngine.run(result, case)
    assert any("actions_taken" in f.field for f in failures)


def test_fails_on_error_response():
    result = _make_result(error="Connection refused")
    case = {"expected": {"semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None}}}
    failures = AssertionEngine.run(result, case)
    assert any("error" in f.field for f in failures)


def test_quality_must_not_contain():
    result = _make_result(
        semantic={"domain": "nutrition", "intent": "declarative", "intent_subtype": None},
        text="I cannot process your request due to an error."
    )
    case = {
        "expected": {"semantic": {"domain": "nutrition", "intent": "declarative", "intent_subtype": None}},
        "quality": {"must_not_contain": ["cannot", "error"]}
    }
    failures = AssertionEngine.run(result, case)
    assert any("cannot" in f.message or "error" in f.message for f in failures)


def test_actions_taken_list_type():
    result = _make_result(
        semantic={"domain": "nutrition", "intent": "interrogative", "intent_subtype": "recommendation"},
        actions_taken=["chicken salad", "grilled fish"]
    )
    case = {
        "expected": {
            "semantic": {"domain": "nutrition", "intent": "interrogative", "intent_subtype": "recommendation"},
            "actions_taken": {"type": "list"}
        }
    }
    failures = AssertionEngine.run(result, case)
    assert failures == []
