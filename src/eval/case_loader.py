from pathlib import Path
from typing import Optional
import yaml
import jsonschema

DATASET_ROOT = Path(__file__).parent.parent.parent / "dataset"
SCHEMA_PATH = DATASET_ROOT / "schema.json"

import json

def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)

def load_case(path: Path) -> dict:
    with open(path) as f:
        case = yaml.safe_load(f)
    schema = load_schema()
    jsonschema.validate(case, schema)
    return case

def load_suite(suite_name: str) -> list[dict]:
    suite_path = DATASET_ROOT / "suites" / f"{suite_name}.yaml"
    with open(suite_path) as f:
        suite = yaml.safe_load(f)
    cases = []
    for case_id in suite["cases"]:
        # search all category subdirs
        for case_path in (DATASET_ROOT / "cases").rglob(f"{case_id}.yaml"):
            cases.append(load_case(case_path))
            break
    return cases

def load_all_cases() -> list[dict]:
    cases = []
    for path in sorted((DATASET_ROOT / "cases").rglob("*.yaml")):
        cases.append(load_case(path))
    return cases
