import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from src.storage.models import EvalResult, EvalRun

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "results" / "eval.db"


class EvalDB:
    def __init__(self, db_path: str = str(DEFAULT_DB_PATH)):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    run_id TEXT PRIMARY KEY,
                    commit_sha TEXT,
                    branch TEXT,
                    suite TEXT,
                    triggered_by TEXT,
                    timestamp TEXT,
                    intent_accuracy REAL,
                    error_rate REAL,
                    latency_p50_ms INTEGER,
                    latency_p95_ms INTEGER,
                    total_cost_usd REAL,
                    gate_passed INTEGER,
                    gate_failures TEXT,
                    cases_run INTEGER,
                    cases_passed INTEGER,
                    cases_failed INTEGER
                );
                CREATE TABLE IF NOT EXISTS eval_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    case_id TEXT,
                    category TEXT,
                    passed INTEGER,
                    assertion_failures_json TEXT,
                    latency_ms INTEGER,
                    cost_usd REAL,
                    judge_score REAL,
                    judge_reasoning TEXT,
                    commit_sha TEXT,
                    branch TEXT,
                    timestamp TEXT
                );
            """)

    def save_run(self, run: EvalRun):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO eval_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run.run_id, run.commit_sha, run.branch, run.suite, run.triggered_by,
                 run.timestamp, run.intent_accuracy, run.error_rate, run.latency_p50_ms,
                 run.latency_p95_ms, run.total_cost_usd, int(run.gate_passed),
                 json.dumps(run.gate_failures), run.cases_run, run.cases_passed, run.cases_failed)
            )

    def save_result(self, result: EvalResult):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO eval_results
                (run_id,case_id,category,passed,assertion_failures_json,latency_ms,
                 cost_usd,judge_score,judge_reasoning,commit_sha,branch,timestamp)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (result.run_id, result.case_id, result.category, int(result.passed),
                 result.assertion_failures_json, result.latency_ms, result.cost_usd,
                 result.judge_score, result.judge_reasoning, result.commit_sha,
                 result.branch, result.timestamp)
            )

    def get_run(self, run_id: str) -> Optional[EvalRun]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM eval_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        return EvalRun(
            **{k: d[k] for k in d if k not in ("gate_passed", "gate_failures")},
            gate_passed=bool(d["gate_passed"]),
            gate_failures=json.loads(d["gate_failures"]),
        )

    def get_results_for_run(self, run_id: str) -> List[EvalResult]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM eval_results WHERE run_id=?", (run_id,)).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d.pop("id", None)
            results.append(EvalResult(**{**d, "passed": bool(d["passed"])}))
        return results

    def get_case_history(self, case_id: str, limit: int = 20) -> List[EvalResult]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eval_results WHERE case_id=? ORDER BY timestamp DESC LIMIT ?",
                (case_id, limit)
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d.pop("id", None)
            results.append(EvalResult(**{**d, "passed": bool(d["passed"])}))
        return results

    def get_recent_runs(self, limit: int = 20) -> List[EvalRun]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eval_runs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        runs = []
        for row in rows:
            d = dict(row)
            runs.append(EvalRun(
                **{k: d[k] for k in d if k not in ("gate_passed", "gate_failures")},
                gate_passed=bool(d["gate_passed"]),
                gate_failures=json.loads(d["gate_failures"]),
            ))
        return runs
