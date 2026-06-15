import csv
import json
from pathlib import Path
from typing import Dict, List


def _parse_correctness(val: str) -> float | None:
    """'1'->1.0, '0'->0.0, 'N/A'->None (not applicable)."""
    v = (val or "").strip()
    if v == "N/A" or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_routing_results(csv_path: str) -> List[Dict]:
    """Load a routing_synthetic_*.csv pre-computed result file.

    Returns a list of row dicts with numeric correctness fields.
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "id": row.get("id", ""),
                "input": row.get("input", ""),
                "full_pass": _parse_correctness(row.get("full_pass", "")),
                "domain_correct": _parse_correctness(row.get("domain_correct", "")),
                "action_correct": _parse_correctness(row.get("action_correct", "")),
                "subaction_correct": _parse_correctness(row.get("subaction_correct", "")),
                "elapsed_s": float(row.get("elapsed_s") or 0),
                "error": row.get("error", ""),
                "predicted_phrases": json.loads(row["predicted_phrases"]) if row.get("predicted_phrases") else [],
            })
    return rows


def summarise_routing(rows: List[Dict]) -> Dict:
    """Compute overall and per-domain accuracy from a loaded result file."""
    by_domain: Dict[str, Dict] = {}
    for row in rows:
        domain = (row["predicted_phrases"][0].get("domain") if row["predicted_phrases"] else None) or "unknown"
        b = by_domain.setdefault(domain, {"domain": [], "action": [], "subaction": [], "total": 0, "passed": 0})
        b["total"] += 1
        if row["full_pass"] == 1.0:
            b["passed"] += 1
        if row["domain_correct"] is not None:
            b["domain"].append(row["domain_correct"])
        if row["action_correct"] is not None:
            b["action"].append(row["action_correct"])
        if row["subaction_correct"] is not None:
            b["subaction"].append(row["subaction_correct"])

    overall_domain = [r["domain_correct"] for r in rows if r["domain_correct"] is not None]
    overall_action = [r["action_correct"] for r in rows if r["action_correct"] is not None]
    overall_full = [r["full_pass"] for r in rows if r["full_pass"] is not None]
    avg_latency = sum(r["elapsed_s"] for r in rows) / len(rows) if rows else 0

    return {
        "total": len(rows),
        "full_pass": sum(overall_full) / len(overall_full) if overall_full else 0,
        "domain_accuracy": sum(overall_domain) / len(overall_domain) if overall_domain else 0,
        "action_accuracy": sum(overall_action) / len(overall_action) if overall_action else None,
        "avg_latency_s": avg_latency,
        "by_domain": {
            d: {
                "total": v["total"],
                "full_pass": v["passed"] / v["total"],
                "domain": sum(v["domain"]) / len(v["domain"]) if v["domain"] else None,
                "action": sum(v["action"]) / len(v["action"]) if v["action"] else None,
            }
            for d, v in sorted(by_domain.items())
        },
    }
