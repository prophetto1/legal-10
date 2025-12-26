# Prompt Contract

**Version:** 1.0
**Date:** 2025-12-26
**Status:** Locked

---

## 1. Model Output Authority

**Critical rule:** The executor owns `StepResult.status`, never the model.

### What the Model Emits

```json
{
  "schema_version": "1.0",
  "payload": { ... },
  "errors": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | `"1.0"` | Fixed version string |
| `payload` | `object` | Step-specific output (see §2) |
| `errors` | `string[]` | Model's self-reported issues (audit only, not used for control flow) |

### What the Executor Sets

| `StepResult` Field | Source |
|--------------------|--------|
| `status` | Executor logic (never from model) |
| `parsed` | Model's `payload` |
| `model_errors` | Model's `errors` (informational) |
| `score`, `correct` | Scoring function |

### Parse Failure Handling

| Condition | `status` | `parsed` | `score` | `correct` |
|-----------|----------|----------|---------|-----------|
| Valid JSON, matches schema | `"OK"` | `payload` | computed | computed |
| Valid JSON, wrong schema | `"OK"` | `{}` | `0.0` | `False` |
| Invalid JSON | `"OK"` | `{}` | `0.0` | `False` |
| Empty response | `"OK"` | `{}` | `0.0` | `False` |

**Rationale:** Execution happened (`status="OK"`), but the model failed to produce valid output. This is a model failure, not a skip.

---

## 2. Per-Step Payload Schemas

### S1: Known Authority

```json
{
  "us_cite": "347 U.S. 483",
  "case_name": "Brown v. Board of Education",
  "term": 1954
}
```

| Field | Type | Description |
|-------|------|-------------|
| `us_cite` | `string` | US Reports citation |
| `case_name` | `string` | Full case name |
| `term` | `int` | SCDB term (year) |

### S2: Unknown Authority

```json
{
  "citing_cases": [
    { "us_cite": "349 U.S. 294", "case_name": "..." },
    { "us_cite": "350 U.S. 123", "case_name": "..." }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `citing_cases` | `array` | Ranked list of citing cases (best first) |
| `citing_cases[].us_cite` | `string` | US Reports citation |
| `citing_cases[].case_name` | `string` | Case name |

**Scoring:**
- `StepResult.score` = MRR (Mean Reciprocal Rank)
- `StepResult.correct` = `hit@10` (true if ground truth in top 10)
- Full metrics stored in `parsed.metrics`:
  ```json
  {
    "citing_cases": [...],
    "metrics": {
      "hit_at_1": false,
      "hit_at_5": true,
      "hit_at_10": true,
      "hit_at_20": true,
      "mrr": 0.25,
      "rank": 4
    }
  }
  ```

### S3: Validate Authority

```json
{
  "is_overruled": true,
  "overruling_case": "West Coast Hotel Co. v. Parrish",
  "year_overruled": 1937
}
```

| Field | Type | Description |
|-------|------|-------------|
| `is_overruled` | `bool` | Whether the case has been overruled |
| `overruling_case` | `string \| null` | Name of overruling case (null if not overruled) |
| `year_overruled` | `int \| null` | Year overruled (null if not overruled) |

### S4: Fact Extraction

```json
{
  "disposition": "reversed and remanded",
  "party_winning": "petitioner",
  "holding_summary": "The Court held that..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `disposition` | `string` | **Must be from closed enum (see §3)** |
| `party_winning` | `"petitioner" \| "respondent" \| "unclear"` | Which party prevailed |
| `holding_summary` | `string` | Brief summary of the holding |

### S5: Distinguish (CB and RAG)

```json
{
  "agrees": true,
  "reasoning": "The citing case follows the precedent because..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `agrees` | `bool` | **Matches `edge.agree` ground truth** |
| `reasoning` | `string` | Explanation of the relationship |

**Note:** Field is `agrees`, not `distinguished`. This matches the ground truth field `edge.agree`.

### S6: IRAC Synthesis

```json
{
  "issue": "Whether segregation in public schools...",
  "rule": "The Equal Protection Clause of the Fourteenth Amendment...",
  "application": "Applying this rule to the facts...",
  "conclusion": "Therefore, the Court concludes..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `issue` | `string` | Legal issue statement |
| `rule` | `string` | Applicable legal rule |
| `application` | `string` | Application of rule to facts |
| `conclusion` | `string` | Final conclusion |

### S7: Citation Integrity

```json
{
  "citations_found": [
    { "cite": "347 U.S. 483", "exists": true },
    { "cite": "999 U.S. 999", "exists": false }
  ],
  "all_valid": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `citations_found` | `array` | Citations extracted from S6 output |
| `citations_found[].cite` | `string` | Citation string |
| `citations_found[].exists` | `bool` | Whether citation is real (not in `fake_cases`) |
| `all_valid` | `bool` | True if all citations are real |

---

## 3. Closed Enums

### S4 Disposition Labels

The prompt **must** constrain `disposition` to exactly these values:

| Label | SCDB Code |
|-------|-----------|
| `"stay granted"` | 1 |
| `"affirmed"` | 2 |
| `"reversed"` | 3 |
| `"reversed and remanded"` | 4 |
| `"vacated and remanded"` | 5 |
| `"affirmed and reversed in part"` | 6 |
| `"affirmed and vacated in part"` | 7 |
| `"affirmed and reversed in part and remanded"` | 8 |
| `"vacated"` | 9 |
| `"petition denied"` | 10 |
| `"certification"` | 11 |

**Scoring:** Exact string match required. No fuzzy matching.

### S4 Party Winning

| Label | SCDB Code |
|-------|-----------|
| `"petitioner"` | 1 |
| `"respondent"` | 0 |
| `"unclear"` | 2 |

---

## 4. Prompt Templates

### Prompt Suffix (All Steps)

Every prompt ends with:

```
Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences.
```

### S5:cb Input (Backbone)

S5:cb uses **only**:
- `cited_case` metadata (name, citation, term)
- `citing_case` metadata (name, citation only - **no opinion text**)
- S4 extracted facts (`disposition`, `party_winning`)
- S4 `holding_summary`

S5:cb does **NOT** use:
- `citing_case.majority_opinion`
- Any "citation window" text

### S5:rag Input (Enriched)

S5:rag uses everything in S5:cb, **plus**:
- `citing_case.majority_opinion` (full or windowed)

---

## 5. Prompt Function Signatures

```python
# core/prompts/templates.py

def render_s1(ctx: ChainContext) -> str:
    """Generate S1 Known Authority prompt."""
    ...

def render_s2(ctx: ChainContext) -> str:
    """Generate S2 Unknown Authority prompt."""
    ...

def render_s3(ctx: ChainContext) -> str:
    """Generate S3 Validate Authority prompt."""
    ...

def render_s4(ctx: ChainContext) -> str:
    """Generate S4 Fact Extraction prompt."""
    ...

def render_s5_cb(ctx: ChainContext) -> str:
    """Generate S5:cb Distinguish prompt (backbone, no citing opinion)."""
    ...

def render_s5_rag(ctx: ChainContext) -> str:
    """Generate S5:rag Distinguish prompt (with citing opinion)."""
    ...

def render_s6(ctx: ChainContext) -> str:
    """Generate S6 IRAC Synthesis prompt."""
    ...

def render_s7(ctx: ChainContext) -> str:
    """Generate S7 Citation Integrity prompt."""
    ...
```

---

## 6. Voiding Semantics (S6/S7)

When S7 detects a fabricated citation:

| Field | Before Void | After Void |
|-------|-------------|------------|
| `status` | `"OK"` | `"OK"` (unchanged) |
| `voided` | `False` | `True` |
| `void_reason` | `None` | `"S7 citation integrity failure"` |
| `score` | computed | `0.0` |
| `correct` | computed | `False` |

**Note:** `status` remains `"OK"` because execution happened. The `voided` flag indicates post-hoc invalidation.

---

## Appendix: Resolved Issues

| # | Issue | Resolution |
|---|-------|------------|
| 1 | Model emits `status` but executor owns it | Model emits `payload` only; executor sets `status` |
| 2 | `distinguished` vs `agree` mismatch | Renamed to `agrees` to match ground truth |
| 3 | Disposition free text drift | Closed enum in prompt, exact match scoring |
| 4 | S2 multi-metric vs single `score`/`correct` | `score=MRR`, `correct=hit@10`, full metrics in `parsed` |
| 5 | `VOIDED` as status vs flag | Keep `status="OK"` + `voided=True` flag |
| 6 | CB "citation window" needs citing text | CB = metadata + S4 only; no citing text required |