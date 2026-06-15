from src.eval.case_loader import load_case, load_suite, load_all_cases
from pathlib import Path
import pytest

DATASET_ROOT = Path(__file__).parent.parent / "dataset"

def test_load_single_case():
    case = load_case(DATASET_ROOT / "cases/meal_logging/ml-001.yaml")
    assert case["id"] == "ml-001"
    assert case["category"] == "meal_logging"
    assert "expected" in case
    assert case["expected"]["semantic"]["intent"] == "log"

def test_load_smoke_suite():
    cases = load_suite("smoke")
    assert len(cases) == 7
    ids = [c["id"] for c in cases]
    assert "ml-001" in ids
    assert "rec-001" in ids

def test_load_full_suite():
    cases = load_suite("full")
    assert len(cases) == 42

def test_all_cases_valid():
    cases = load_all_cases()
    assert len(cases) == 42
    for case in cases:
        assert "id" in case
        assert "expected" in case
        assert "semantic" in case["expected"]

def test_case_schema_validation_rejects_bad_case(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: bad\ncategory: unknown_category\n")
    with pytest.raises(Exception):
        from src.eval.case_loader import load_case as lc
        lc(bad)
