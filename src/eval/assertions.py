from dataclasses import dataclass
from typing import Any, List
from src.eval.client import EliaCallResult


@dataclass
class AssertionFailure:
    field: str
    message: str
    expected: Any = None
    actual: Any = None


class AssertionEngine:
    @staticmethod
    def run(result: EliaCallResult, case: dict, layer: str = "full") -> List[AssertionFailure]:
        """
        layer="full"     — semantic + actions_taken + must_not_contain
        layer="semantic" — domain / intent / intent_subtype only (entry agents)
        """
        failures = []

        if result.error:
            failures.append(AssertionFailure(
                field="error", message=f"Request failed: {result.error}"
            ))
            return failures

        expected = case.get("expected", {})

        exp_semantic = expected.get("semantic", {})
        got_semantic = result.semantic or {}

        for field in ("domain", "intent", "intent_subtype"):
            exp_val = exp_semantic.get(field)
            if exp_val is None:
                continue  # skip fields not specified in expected
            got_val = got_semantic.get(field)
            if exp_val != got_val:
                failures.append(AssertionFailure(
                    field=f"semantic.{field}",
                    message=f"Expected {field}={exp_val!r}, got {got_val!r}",
                    expected=exp_val,
                    actual=got_val,
                ))

        # Check expected tool selection (gold dataset cases)
        exp_tool = exp_semantic.get("selected_tool")
        if exp_tool is not None:
            phrases = (got_semantic.get("phrases") or [])
            got_tool = phrases[0].get("selected_pathway") if phrases else None
            if exp_tool != "(none)" and got_tool != exp_tool:
                failures.append(AssertionFailure(
                    field="semantic.selected_tool",
                    message=f"Expected selected_tool={exp_tool!r}, got {got_tool!r}",
                    expected=exp_tool,
                    actual=got_tool,
                ))

        if layer == "full":
            exp_actions = expected.get("actions_taken")
            if exp_actions:
                exp_type = exp_actions.get("type")
                got_actions = result.actions_taken

                if exp_type == "null":
                    if got_actions is not None:
                        failures.append(AssertionFailure(
                            field="actions_taken",
                            message=f"Expected actions_taken to be null, got {type(got_actions).__name__}",
                            expected=None, actual=got_actions,
                        ))
                elif exp_type == "list":
                    if not isinstance(got_actions, list):
                        failures.append(AssertionFailure(
                            field="actions_taken",
                            message=f"Expected actions_taken to be list, got {type(got_actions).__name__}",
                            expected="list", actual=type(got_actions).__name__,
                        ))
                elif exp_type == "dict":
                    if not isinstance(got_actions, dict):
                        failures.append(AssertionFailure(
                            field="actions_taken",
                            message=f"Expected actions_taken to be dict, got {type(got_actions).__name__}",
                            expected="dict", actual=type(got_actions).__name__,
                        ))
                    else:
                        for key in exp_actions.get("has_keys", []):
                            if key not in got_actions:
                                failures.append(AssertionFailure(
                                    field="actions_taken",
                                    message=f"Expected key '{key}' in actions_taken, not found",
                                    expected=key, actual=list(got_actions.keys()),
                                ))

            quality = case.get("quality", {})
            text = (result.text or "").lower()
            for phrase in quality.get("must_not_contain", []):
                if phrase.lower() in text:
                    failures.append(AssertionFailure(
                        field="text",
                        message=f"Response contains prohibited phrase: '{phrase}'",
                        expected=f"not contain '{phrase}'", actual=phrase,
                    ))

        return failures
