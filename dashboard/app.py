import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from src.storage.db import EvalDB

st.set_page_config(page_title="Elia Eval Dashboard", layout="wide")
st.title("Elia LLM Eval Dashboard")

DB_PATH = st.sidebar.text_input("DB Path", value="results/eval.db")


@st.cache_resource
def get_db(path):
    db = EvalDB(path)
    db.init_schema()
    return db


try:
    db = get_db(DB_PATH)
    runs = db.get_recent_runs(limit=50)
except Exception as e:
    st.error(f"Cannot connect to DB: {e}")
    st.stop()

if not runs:
    st.info("No eval runs found. Run `elia-eval run` to generate data.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📈 Trends", "🟥 Category Heatmap", "🔍 Case History", "💰 Cost & Latency"])

# ── Tab 1: Trends ──────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Intent Accuracy Over Time")
    df = pd.DataFrame([{
        "timestamp": r.timestamp[:10],
        "run_id": r.run_id,
        "branch": r.branch,
        "intent_accuracy": r.intent_accuracy,
        "error_rate": r.error_rate,
        "latency_p95_ms": r.latency_p95_ms,
        "total_cost_usd": r.total_cost_usd,
        "gate_passed": r.gate_passed,
        "cases_passed": r.cases_passed,
        "cases_run": r.cases_run,
    } for r in reversed(runs)])

    col1, col2 = st.columns(2)
    with col1:
        st.line_chart(df.set_index("timestamp")[["intent_accuracy"]])
    with col2:
        st.line_chart(df.set_index("timestamp")[["error_rate"]])

    st.dataframe(
        df[["run_id", "branch", "timestamp", "intent_accuracy", "latency_p95_ms", "total_cost_usd", "gate_passed"]],
        use_container_width=True
    )

# ── Tab 2: Category Heatmap ────────────────────────────────────────────────────
with tab2:
    st.subheader("Accuracy by Category — Last 10 Runs")
    recent_runs = runs[:10]
    category_data = []
    for run in recent_runs:
        results = db.get_results_for_run(run.run_id)
        by_cat: dict = {}
        for r in results:
            by_cat.setdefault(r.category, []).append(r.passed)
        for cat, vals in by_cat.items():
            category_data.append({
                "run_id": run.run_id[:8],
                "category": cat,
                "accuracy": sum(vals) / len(vals),
            })

    if category_data:
        df_cat = pd.DataFrame(category_data).pivot(index="category", columns="run_id", values="accuracy")
        st.dataframe(
            df_cat.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=1),
            use_container_width=True
        )
    else:
        st.info("No per-category data yet.")

# ── Tab 3: Case History ────────────────────────────────────────────────────────
with tab3:
    st.subheader("Per-Case History")
    case_id = st.text_input("Case ID", value="ml-001")
    if case_id:
        history = db.get_case_history(case_id, limit=20)
        if history:
            df_hist = pd.DataFrame([{
                "timestamp": r.timestamp[:10],
                "passed": "✅" if r.passed else "❌",
                "latency_ms": r.latency_ms,
                "judge_score": r.judge_score,
                "branch": r.branch,
                "commit": r.commit_sha[:7],
                "failures": r.assertion_failures_json,
            } for r in history])
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.info(f"No history for case `{case_id}`")

# ── Tab 4: Cost & Latency ──────────────────────────────────────────────────────
with tab4:
    st.subheader("Cost & Latency Trends")
    df_cost = pd.DataFrame([{
        "timestamp": r.timestamp[:10],
        "latency_p50_ms": r.latency_p50_ms,
        "latency_p95_ms": r.latency_p95_ms,
        "total_cost_usd": r.total_cost_usd,
    } for r in reversed(runs)])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Latency (ms)")
        st.line_chart(df_cost.set_index("timestamp")[["latency_p50_ms", "latency_p95_ms"]])
    with col2:
        st.subheader("Cost per Run ($)")
        st.line_chart(df_cost.set_index("timestamp")[["total_cost_usd"]])
