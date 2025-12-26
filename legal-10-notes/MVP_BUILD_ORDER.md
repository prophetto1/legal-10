# MVP Build Order

**Version:** 1.1
**Date:** 2025-12-26
**Status:** Locked

**Related Documents:**

- `L10_AGENTIC_SPEC.md` - Full technical specification (v2.2)
- `PROMPT_CONTRACT.md` - Locked prompt schemas, payload formats, scoring rules
- `DATA_SCHEMAS.md` - Source data reference

---

## Overview

| Phase | Deliverable | Parallel? |
|-------|-------------|-----------|
| 1 | Contract Lock | — |
| 2 | Executor Proof | Yes (with 3) |
| 3 | Data Builder | Yes (with 2) |
| 4 | Deterministic Spine (S1 + S7) | After 2+3 |
| 5 | Signal Steps (S4, S5:cb, S5:rag) | After 4 |
| 6 | Remaining Steps (S2, S3) | After 5 |
| 7 | S6 Judge | After 6 |

---

## Phase 1: Contract Lock

**Goal:** Freeze interfaces before any execution code.

### Files

```
core/
├── __init__.py
├── ids/
│   ├── __init__.py
│   └── canonical.py          # case_id(), pair_id()
├── schemas/
│   ├── __init__.py
│   ├── case.py               # CourtCase, ShepardsEdge, OverruleRecord
│   ├── chain.py              # ChainInstance, ChainContext
│   ├── results.py            # StepResult, ChainResult
│   └── ground_truth.py       # S4GroundTruth
└── normalize/
    ├── __init__.py
    └── citations.py          # canonicalize_cite() - minimal
```

### Exit Criteria

- [ ] All dataclasses importable
- [ ] `StepResult.status` is string enum with documented values
- [ ] `ChainContext.get()` / `.set()` work with `step_id` keys
- [ ] `pytest tests/test_schemas.py` passes

---

## Phase 2: Executor Proof

**Goal:** Prove execution semantics with mocks before real steps.

### Files

```
chain/
├── __init__.py
├── steps/
│   ├── __init__.py
│   ├── base.py               # Step ABC
│   └── stub_step.py          # StubStep for testing
├── backends/
│   ├── __init__.py
│   ├── base.py               # Backend ABC
│   └── mock_backend.py       # MockBackend
└── runner/
    ├── __init__.py
    └── executor.py           # ChainExecutor
```

### Exit Criteria (all with MockBackend + StubSteps)

- [ ] `requires()` dependency resolution works
- [ ] `step_id` routing: `s5:cb` and `s5:rag` stored separately
- [ ] `SKIPPED_COVERAGE` fires when `citing_case.majority_opinion` is `None`
- [ ] `SKIPPED_DEPENDENCY` fires when required step missing/not OK
- [ ] S7 gate voids S6 when `correct=False`
- [ ] `pytest tests/test_executor.py` passes

---

## Phase 3: Data Builder

**Goal:** Load real data, compute actual coverage numbers.

**Parallel with:** Phase 2

### Files

```
chain/datasets/
├── __init__.py
├── loaders.py                # load_*() from HuggingFace
└── builder.py                # build_chain_instances(), indexes

scripts/
└── validate_joins.py         # Coverage report CLI
```

### Exit Criteria

- [ ] All 4 CSVs load (`scdb_sample`, `scotus_shepards_sample`, `scotus_overruled_db`, `fake_cases`)
- [ ] `case_by_us_cite` index built
- [ ] Join coverage printed:
  ```
  Total Shepard's edges:     5,000
  cited_case resolved:       X (Y%)
  citing_case resolved:      A (B%)
  CHAIN_CORE:                N
  CHAIN_RAG_SUBSET:          M
  ```
- [ ] 5 sample `ChainInstance` objects printed with correct structure

---

## Phase 4: Deterministic Spine

**Goal:** End-to-end execution with real data on S1 + S7.

**Requires:** Phase 2 + Phase 3 complete

### Files

```
chain/steps/
├── s1_known_authority.py
└── s7_citation_integrity.py

core/scoring/
├── __init__.py
└── citation_verify.py        # S7 scorer (fake lookup)

core/reporting/
├── __init__.py
├── jsonl.py                  # JSONL emitter
└── markdown.py               # Markdown report generator

scripts/
├── run_chain.py              # CLI: execute chains
└── summarize_run.py          # CLI: compute metrics, emit MD
```

### Exit Criteria

- [ ] S1 executes on real `ChainInstance`, scores against ground truth
- [ ] S7 detects fake citations from `fake_cases.csv`
- [ ] S7 gate voids work on real instances
- [ ] JSONL output written with all `StepResult` fields
- [ ] Markdown summary generated with accuracy tables
- [ ] `pytest tests/test_s1.py tests/test_s7.py` passes

---

## Phase 5: Signal Steps

**Goal:** S4 fact extraction + S5 distinguish (CB then RAG).

**Requires:** Phase 4 complete

### Files

```
chain/steps/
├── s4_fact_extraction.py
└── s5_distinguish.py         # S5DistinguishCB, S5DistinguishRAG

core/scoring/
└── exact_match.py            # Disposition, party_winning matchers
```

### Exit Criteria

- [ ] S4 extracts disposition, party_winning from opinion text
- [ ] S4 scores against `S4GroundTruth`
- [ ] S5:cb runs on all `CHAIN_CORE` instances
- [ ] S5:rag runs only on `CHAIN_RAG_SUBSET`, others get `SKIPPED_COVERAGE`
- [ ] FRD gap computable on aligned subset
- [ ] `pytest tests/test_s4.py tests/test_s5.py` passes

---

## Phase 6: Remaining Steps

**Goal:** S2 unknown authority + S3 validate authority.

**Requires:** Phase 5 complete

### Files

```
chain/steps/
├── s2_unknown_authority.py
└── s3_validate_authority.py
```

### Exit Criteria

- [ ] S2 generates citing case predictions, scored against Shepard's data
- [ ] S3 checks overruling status, handles `None` (not overruled) correctly
- [ ] `pytest tests/test_s2.py tests/test_s3.py` passes

---

## Phase 7: S6 Judge

**Goal:** IRAC synthesis with rubric-based or LLM judge scoring.

**Requires:** Phase 6 complete

### Files

```
chain/steps/
└── s6_irac_synthesis.py

core/scoring/
└── irac_rubric.py            # MEE-style rubric scorer
```

### Exit Criteria

- [ ] S6 synthesizes outputs from S1-S5
- [ ] Rubric scorer or LLM judge produces 0.0-1.0 scores
- [ ] S6 correctly skipped when dependencies not satisfied
- [ ] S7 void retroactively updates S6 scores
- [ ] `pytest tests/test_s6.py` passes

---

## Dependency Graph

```
Phase 1: Contract Lock
       │
       ▼
┌──────┴──────┐
│             │
▼             ▼
Phase 2       Phase 3
Executor      Data Builder
Proof
│             │
└──────┬──────┘
       │
       ▼
Phase 4: Deterministic Spine (S1 + S7)
       │
       ▼
Phase 5: Signal Steps (S4, S5:cb, S5:rag)
       │
       ▼
Phase 6: Remaining (S2, S3)
       │
       ▼
Phase 7: S6 Judge
```

---

## Post-MVP Extensions

| Extension | Description | Reference |
|-----------|-------------|-----------|
| HELM Integration | CaseHOLD baseline for S5 comparison | `HELM_ANALYSIS.md` |
| CLERC | Citation retrieval benchmark | `FUTURE_EXTENSIONS.md` |
| CUAD | Contract fact extraction | `FUTURE_EXTENSIONS.md` |
| LEXam | Bar exam synthesis | `FUTURE_EXTENSIONS.md` |

---

## Notes

- Phase 2 and Phase 3 can run in parallel
- Phase 4 is the integration point - proves full pipeline works
- S5:cb before S5:rag - CB is the backbone, RAG is enrichment
- S6 is last because it depends on all prior steps and needs judge logic
