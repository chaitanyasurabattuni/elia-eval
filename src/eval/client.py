from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
import time
import httpx

# Pricing per 1M tokens (claude-haiku-4-5 defaults)
INPUT_TOKEN_COST_PER_M = 0.80
OUTPUT_TOKEN_COST_PER_M = 4.00


class EliaClientMode(Enum):
    HTTP = "http"
    TESTCLIENT = "testclient"


@dataclass
class EliaCallResult:
    raw: Dict[str, Any]
    latency_ms: int
    error: Optional[str] = None

    @property
    def semantic(self) -> Optional[Dict]:
        return self.raw.get("semantic")

    @property
    def actions_taken(self) -> Any:
        return self.raw.get("actions_taken")

    @property
    def text(self) -> Optional[str]:
        return self.raw.get("text")

    @property
    def token_usage(self) -> Optional[Dict]:
        return self.raw.get("token_usage")

    @property
    def cost_usd(self) -> float:
        if not self.token_usage:
            return 0.0
        inp = self.token_usage.get("input_tokens", 0)
        out = self.token_usage.get("output_tokens", 0)
        return (inp * INPUT_TOKEN_COST_PER_M + out * OUTPUT_TOKEN_COST_PER_M) / 1_000_000


class EliaClient:
    def __init__(self, mode: EliaClientMode = EliaClientMode.HTTP, base_url: str = "http://localhost:8001"):
        self.mode = mode
        self.base_url = base_url
        self._tc = None  # lazy TestClient init

    def _get_testclient(self):
        if self._tc is None:
            from routes.api import app
            from fastapi.testclient import TestClient
            self._tc = TestClient(app)
        return self._tc

    def call(self, user_request: str, user_id: int = 1, user_name: str = "Demo") -> EliaCallResult:
        payload = {"user_request": user_request, "user_name": user_name, "user_id": str(user_id)}
        start = time.monotonic()
        try:
            if self.mode == EliaClientMode.HTTP:
                resp = httpx.post(f"{self.base_url}/process/", json=payload, timeout=30)
                data = resp.json()
            else:
                tc = self._get_testclient()
                resp = tc.post("/process/", json=payload)
                data = resp.json()
            latency_ms = int((time.monotonic() - start) * 1000)
            return EliaCallResult(raw=data, latency_ms=latency_ms)
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            return EliaCallResult(raw={}, latency_ms=latency_ms, error=str(e))
