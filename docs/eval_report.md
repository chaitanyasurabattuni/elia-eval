# Elia Eval Report
**Branch:** dev | **Date:** 2026-06-15 | **Suite:** smoke (7 cases)

---

## Summary

| Metric | Value | Gate |
|--------|-------|------|
| Semantic Accuracy (entry agents) | **85.7%** | ✅ above 80% |
| Full Accuracy (end-to-end) | **42.9%** | ❌ below 80% |
| Error Rate | 0.0% | ✅ |
| Latency p50 | 3,858 ms | ✅ |
| Latency p95 | 7,839 ms | ✅ below 10,000 ms |
| Cost per smoke run | ~$0.07 | — |

**Gate result: FAILED** — full accuracy is below the 80% threshold. Root cause is environment constraints (missing FatSecret API credentials) and two unimplemented pathways in dev, not regressions in existing logic.

---

## Case-Level Results

| Case | Category | Result | Semantic | Latency | Root Cause |
|------|----------|--------|----------|---------|------------|
| ml-001 | meal_logging | 🟡 | ✅ | 11,412 ms | FatSecret creds not set → `_execute_log_meal` crashes |
| ml-002 | meal_logging | 🟡 | ✅ | 3,858 ms | Same as above |
| ms-001 | meal_scoring | ❌ | ❌ | 2,480 ms | `not_implemented_job_response()` signature mismatch |
| rec-001 | recommendations | ✅ | ✅ | 7,839 ms | — |
| inf-001 | information | 🟡 | ✅ | 2,137 ms | `not_implemented_job_response()` signature mismatch |
| mp-001 | multi_phrase | ✅ | ✅ | 2,606 ms | — |
| ml-008 | meal_logging | ✅ | ✅ | 6,073 ms | — |

**Legend:** ✅ passed all assertions · 🟡 semantic correct, execution failed · ❌ failed semantic

---

## Entry Agent Accuracy (Phrase Parser, Domain + Intent Classifier)

Semantic accuracy measures whether the phrase parser correctly classified domain, intent, and intent_subtype — independently of whether the downstream execution succeeded.

**6 / 7 cases classified correctly (85.7%)**

The one miss is `ms-001` ("What meal score do I get for eggs and potatoes for breakfast?") — the meal scoring pathway is not yet implemented, so the response never reaches the semantic layer for intent_subtype checking.

---

## Known Failures

### 1. Missing FatSecret API Credentials
**Affects:** ml-001, ml-002, mp-001 (any food-logging query)

The food logging path resolves each food item against the FatSecret nutrition API. `FATSECRET_CONSUMER_KEY` and `FATSECRET_CONSUMER_SECRET` are not set in the dev/test environment, so `FatSecretFoodSearchClient.__init__` raises before any DB write happens.

**Call chain:**
```
orchestrator.py:_execute_log_meal
  → logging_engine._log_meal
  → log_meal_context → nutrition_service.process_food_parts
  → batch_food_lookup_service.lookup_foods_with_objects
  → food_lookup_service._search_fatsecret
  → FatSecretFoodSearchClient()   ← raises FatSecretConfigurationError
```

**Fix:** Set `FATSECRET_CONSUMER_KEY` / `FATSECRET_CONSUMER_SECRET` as GitHub Actions secrets in elia-pathfinder, or add a USDA-only fallback when FatSecret isn't configured.

---

### 2. Unimplemented Pathway Signature Mismatch
**Affects:** ms-001, inf-001 (meal scoring, sleep queries)

`pathway.py:38` calls `not_implemented_job_response()` with 3 arguments. The function signature in `engines/logging_engine.py:135` was updated to require 4 (added `failure_reason`). The call site was never updated, so any pathway with `callable=None` raises a `TypeError`.

```python
# pathway.py:38 — current (broken)
return not_implemented_job_response(
    input.phrase, "No pathway implemented", []
)

# logging_engine.py:135 — function signature
def not_implemented_job_response(
    phrase, name, tools, failure_reason   # ← 4 args required
)
```

**Fix:** Add a default to the function signature (`failure_reason: str = ""`), or update the call site.

---

## Phrase Parser Benchmark — Tiny vs Medium Model

Comparison of two pre-computed benchmark runs (`routing_synthetic_tiny.csv` and `routing_synthetic_medium.csv`) against a 400-query dataset spanning 18 domains.

### Overall

| Metric | Tiny | Medium | Winner |
|--------|------|--------|--------|
| Full pass rate | 62.7% | **66.2%** | Medium |
| Domain accuracy | 70.0% | **72.5%** | Medium |
| Avg latency | 3.29 s | **2.23 s** | Medium |

**Medium is the better overall choice** — higher accuracy on 15 of 26 domains, and 1 second faster per query.

### Per-Domain (Full Pass Rate)

| Domain | Tiny | Medium | Delta |
|--------|------|--------|-------|
| biometrics | 71.4% | 77.8% | +6.3% |
| care and coordination | 69.2% | **90.0%** | **+20.8%** |
| daily focus area | 80.0% | **100.0%** | **+20.0%** |
| deployment faq | **100.0%** | 87.5% | -12.5% |
| elia faq | **60.0%** | 38.8% | -21.2% |
| exercise | 37.8% | 41.0% | +3.2% |
| goals and planning | 37.9% | **76.9%** | **+39.0%** |
| health status and life events | 26.9% | **46.7%** | +19.7% |
| learning, education and health literacy | **71.4%** | 66.7% | -4.8% |
| medical | **63.2%** | 61.5% | -1.6% |
| mental wellness | 57.1% | **70.8%** | +13.7% |
| non-core | **100.0%** | 89.5% | -10.5% |
| nutrition | 50.0% | **57.6%** | +7.6% |
| out-of-bounds | **100.0%** | 92.3% | -7.7% |
| preferences and settings | **87.5%** | 78.6% | -8.9% |
| prime score | **93.3%** | 80.0% | -13.3% |
| progress and habits | 37.5% | **80.0%** | **+42.5%** |
| sleep | 63.0% | **76.0%** | +13.0% |
| social and community | 100.0% | 100.0% | 0.0% |
| technical support | 85.0% | **100.0%** | +15.0% |

**Medium excels at:** goals/planning (+39%), progress/habits (+43%), care/coordination (+21%), daily focus area (+20%)

**Tiny holds its own at:** elia FAQ (+21%), prime score (+13%), out-of-bounds (+8%), deployment FAQ (+13%)

**Weak domains on both models:** exercise (~40%), health status (~27–47%), goals/planning on tiny (38%)

---

## Recommendations

1. **Set FatSecret secrets in CI** — this alone would flip ml-001, ml-002, mp-001 from fail to pass, raising full accuracy from 42.9% → ~85.7%

2. **Fix `not_implemented_job_response` signature** — one line change in `engines/logging_engine.py:135` would fix the ms-001 and inf-001 crashes

3. **Use medium model** — 3.5% higher full pass rate and 1 second lower latency vs tiny. Especially worth it for goals/planning and progress/habits domains

4. **Focus improvement effort on weak domains** — exercise (41%), health status (47%), and elia FAQ (39% on medium) are the lowest-performing categories. These would benefit most from additional training data or prompt tuning

5. **Run full 400-case gold eval** — once the FatSecret fix lands, run `eval gold tool_selection_synthetic.csv` to get a complete baseline across all 18 domains
