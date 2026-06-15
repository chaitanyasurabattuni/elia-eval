import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
import anthropic

JUDGE_MODEL = "claude-haiku-4-5-20251001"

JUDGE_PROMPT = """You are evaluating the quality of a health AI assistant's response.

User request: {user_request}
Category: {category}
Assistant response: {response_text}

Rate the response quality on a 0-1 scale:
- 1.0: Excellent — specific, helpful, accurate, appropriate tone
- 0.7: Good — helpful but could be more specific or complete
- 0.4: Mediocre — somewhat relevant but vague or incomplete
- 0.1: Poor — off-topic, unhelpful, or potentially harmful

Respond with ONLY valid JSON:
{{"score": <float 0-1>, "reasoning": "<one sentence>", "issues": [<list of brief issue strings, empty if none>]}}"""


@dataclass
class JudgeResult:
    score: float
    reasoning: str
    issues: List[str] = field(default_factory=list)


class ResponseJudge:
    def __init__(self, api_key: Optional[str] = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def score(self, user_request: str, response_text: str, category: str) -> JudgeResult:
        prompt = JUDGE_PROMPT.format(
            user_request=user_request,
            response_text=response_text,
            category=category,
        )
        try:
            msg = self._client.messages.create(
                model=JUDGE_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            data = json.loads(raw)
            return JudgeResult(
                score=float(data["score"]),
                reasoning=data.get("reasoning", ""),
                issues=data.get("issues", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return JudgeResult(score=0.5, reasoning="Judge parse error — defaulting to neutral score", issues=["parse_error"])

    def maybe_score(self, user_request: str, response_text: str, case: dict) -> Optional[JudgeResult]:
        quality = case.get("quality", {})
        if not quality.get("invoke_judge", False):
            return None
        return self.score(user_request, response_text, case.get("category", "unknown"))
