import csv
from pathlib import Path
from typing import List


def load_gold_dataset(csv_path: str) -> List[dict]:
    """Load the 400-item tool_selection_synthetic.csv gold dataset.

    Each row becomes a case dict compatible with EvalRunner.run_case().
    Checks domain and (when not '(none)') the first selected tool.
    """
    cases = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            query = (row.get("query") or "").strip()
            domain = (row.get("domain") or "").strip()
            tool_raw = (row.get("selected_tools") or "").strip()
            if not query or not domain:
                continue

            # Take only the first tool if multiple are listed (e.g. "log any; compute trend")
            first_tool = tool_raw.split(";")[0].strip() if tool_raw else "(none)"

            cases.append({
                "id": f"gold-{i:03d}",
                "category": domain,
                "suite": ["gold"],
                "request": query,
                "user_id": 1,
                "user_name": "Demo",
                "expected": {
                    "semantic": {
                        "domain": domain,
                        "selected_tool": first_tool,
                    }
                },
            })
    return cases
