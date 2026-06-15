from dataclasses import dataclass, field
from datetime import time as dtime
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
        # Dev branch: semantic lives in debug_data.semantic with domain in phrases[0].health_domain
        debug = self.raw.get("debug_data") or {}
        sem = debug.get("semantic")
        if sem:
            # Extract domain from phrases if top-level domain is null
            if sem.get("domain") is None:
                phrases = sem.get("phrases") or []
                if phrases:
                    health_domain = (phrases[0].get("health_domain") or {})
                    sem = {**sem, "domain": health_domain.get("domain")}
            return sem
        # Fallback: original response shape (HTTP mode against older server)
        return self.raw.get("semantic")

    @property
    def actions_taken(self) -> Any:
        # Dev branch uses metadata_payload; fall back to legacy actions_taken key
        meta = self.raw.get("metadata_payload")
        if meta is not None:
            return meta
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


def _seed_test_data(db) -> None:
    """Inject realistic test data so eval cases that query user history work."""
    try:
        from database.model import LoggedSleep, User
        user = db.session.query(User).filter(User.id == 1).first()
        if user is None:
            return
        existing = db.session.query(LoggedSleep).filter(LoggedSleep.user_id == 1).count()
        if existing > 0:
            return
        sleep = LoggedSleep(
            user_id=1,
            sleep_day_id=1,
            bedtime=dtime(23, 15),
            wake_time=dtime(7, 30),
            time_in_bed_hours=8.25,
            total_sleep_hours=7.5,
            sleep_efficiency=90.9,
            sleep_latency_minutes=10,
            rem_minutes=105,
            deep_minutes=90,
            light_minutes=240,
            awake_minutes=30,
            number_awakenings=3,
            resting_hr_bpm=58,
            hrv_rmssd_ms=42,
            sleep_score=82,
        )
        db.session.add(sleep)
        db.session.commit()
    except Exception:
        pass  # Never crash the eval over missing test data


class EliaClient:
    def __init__(self, mode: EliaClientMode = EliaClientMode.HTTP, base_url: str = "http://localhost:8001"):
        self.mode = mode
        self.base_url = base_url
        self._tc = None  # lazy TestClient init

    def _get_testclient(self):
        if self._tc is None:
            from routes.api import app, db
            from fastapi.testclient import TestClient
            self._tc = TestClient(app)
            _seed_test_data(db)
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
