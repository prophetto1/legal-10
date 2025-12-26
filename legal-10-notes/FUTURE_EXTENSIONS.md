# Potential Future Extensions for Legal-10

**Generated:** 2025-12-25

---

## 1. CLERC (Citation/Retrieval)

**HuggingFace:** [jhu-clsp/CLERC](https://huggingface.co/datasets/jhu-clsp/CLERC)
**Size:** ~106,000 examples
**Task:** Legal citation retrieval / passage ranking

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `query_id` | string | Unique query identifier |
| `query` | string | Legal query (75-2.1K chars) |
| `positive_passages` | list | Relevant document passages |
| `negative_passages` | list | Non-relevant passages |

**Passage structure:**
```json
{
  "docid": "22437426",
  "title": "",
  "text": "Legal text..."
}
```

### Potential L10 Mapping

| L10 Skill | CLERC Usage | Notes |
|-----------|-------------|-------|
| S2 (Unknown Authority) | Query → rank positive passages | Natural fit |
| S3 (Known Authority) | Verify query cites passage | Need reformatting |

### Loading Pattern

```python
from datasets import load_dataset

dataset = load_dataset(
    "jhu-clsp/CLERC",
    data_files={"data": "generation/test.jsonl"}
)["data"]
```

### Considerations

- **Good:** Large dataset, retrieval-focused, legal domain
- **Bad:** Different task structure than Dahl (retrieval vs factual QA)
- **Integration:** Would need separate HELM scenario, not direct chain integration

---

## 2. CUAD (Contract Understanding)

**HuggingFace:** [theatticusproject/cuad-qa](https://huggingface.co/datasets/theatticusproject/cuad-qa)
**Size:** 26,632 samples (22,450 train / 4,182 test)
**Task:** Extractive QA over commercial contracts

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `title` | string | Contract title |
| `context` | string | Full contract text |
| `question` | string | Question about clause category |
| `answers.text` | list[string] | Extracted answer text(s) |
| `answers.answer_start` | list[int] | Character positions |

### Example

```json
{
  "id": "LIMEENERGYCO_..._Document Name_0",
  "title": "DISTRIBUTOR AGREEMENT",
  "context": "EXHIBIT 10.6\n\nDISTRIBUTOR AGREEMENT...",
  "question": "Highlight the parts related to 'Document Name'...",
  "answers": {
    "text": ["DISTRIBUTOR AGREEMENT"],
    "answer_start": [44]
  }
}
```

### 41 Clause Categories

Includes: Document Name, Parties, Agreement Date, Effective Date, Expiration Date, Renewal Term, Termination for Convenience, Anti-Assignment, Revenue/Profit Sharing, IP Ownership Assignment, etc.

### Potential L10 Mapping

| L10 Skill | CUAD Usage | Notes |
|-----------|------------|-------|
| S4 (Fact Extraction) | Extract clause from contract | Natural fit |
| S6 (IRAC Synthesis) | Summarize contract provisions | Possible extension |

### Loading Pattern

```python
from datasets import load_dataset

dataset = load_dataset("theatticusproject/cuad-qa")
# dataset["train"], dataset["test"]
```

### Considerations

- **Good:** High-quality expert annotations, extractive QA (like S4)
- **Bad:** Contract domain (not case law), different from SCOTUS focus
- **Integration:** Could add as S4 variant for contracts domain

---

## 3. LEXam (Bar Exam)

**HuggingFace:** [LEXam-Benchmark/LEXam](https://huggingface.co/datasets/LEXam-Benchmark/LEXam)
**Task:** Legal exam questions

### Potential L10 Mapping

| L10 Skill | LEXam Usage | Notes |
|-----------|-------------|-------|
| S6 (IRAC Synthesis) | Answer bar exam questions | IRAC output format |
| S8 (Synthesize Results) | Multi-step reasoning | If original skill list |

---

## 4. FairLex (Multilingual)

**HuggingFace:** [coastalcph/fairlex](https://huggingface.co/datasets/coastalcph/fairlex)
**Task:** Multilingual legal judgment prediction
**Languages:** EN, DE, FR, IT, etc.

### Considerations

- Extension for non-US jurisdictions
- Fairness/bias evaluation in legal AI
- Different legal systems (civil vs common law)

---

## 5. Integration Priority Matrix

| Dataset | Effort | Value for L10 Chain | Recommendation |
|---------|--------|---------------------|----------------|
| **Dahl** | Done | Core (S1-S7) | **Use as-is** |
| **CaseHOLD** | Done (HELM) | S5 baseline | **Use existing HELM** |
| **CLERC** | Medium | S2 alternative | Later extension |
| **CUAD** | Medium | S4 contracts variant | Later extension |
| **LEXam** | Medium | S6 grading reference | Later extension |
| **FairLex** | High | Multilingual extension | Future work |

---

## 6. Recommended Approach

### Phase 1: Core (Now)
- Use Dahl data for L10 Agentic chain (S1-S7)
- Use CaseHOLD via HELM for S5-CB baseline comparison

### Phase 2: Extensions (Later)
- Add CLERC scenario for retrieval benchmarking
- Add CUAD scenario for contract fact extraction
- Keep as **separate HELM scenarios**, not chain components

### Phase 3: Research Extensions (Future)
- LEXam for synthesis quality comparison
- FairLex for multilingual/fairness studies

---

## 7. Why Keep Extensions Separate from Chain

The L10 Agentic chain is designed around:
1. **Unified data source** (Dahl/SCDB/Shepards)
2. **Case law domain** (SCOTUS)
3. **Dependent skill sequence** (S1 output → S2 input → ...)

External datasets like CLERC and CUAD:
- Have **different schemas**
- Cover **different domains** (retrieval, contracts)
- Don't have **chain relationships** encoded

**Best architecture:**
- L10 Agentic = chain evaluation (Dahl data only)
- Legal-10 Suite = atomic skill benchmarks (multiple datasets via HELM)
- Compare chain vs atomic performance in analysis
