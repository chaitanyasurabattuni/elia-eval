from typing import List, Optional
from src.eval.client import EliaClient
from src.eval.assertions import AssertionEngine
from src.eval.judge import ResponseJudge
from src.eval.metrics import CaseResult


class EvalRunner:
    def __init__(self, client: EliaClient, judge: Optional[ResponseJudge] = None):
        self._client = client
        self._judge = judge

    def run_case(self, case: dict) -> CaseResult:
        result = self._client.call(
            user_request=case["request"],
            user_id=case.get("user_id", 1),
            user_name=case.get("user_name", "Demo"),
        )

        failures = AssertionEngine.run(result, case)
        passed = len(failures) == 0

        judge_score = None
        if self._judge and result.text:
            judge_result = self._judge.maybe_score(
                user_request=case["request"],
                response_text=result.text,
                case=case,
            )
            if judge_result:
                judge_score = judge_result.score

        return CaseResult(
            case_id=case["id"],
            category=case.get("category", "unknown"),
            passed=passed,
            assertion_failures=failures,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            judge_score=judge_score,
        )

    def run_suite(self, cases: List[dict]) -> List[CaseResult]:
        return [self.run_case(case) for case in cases]
