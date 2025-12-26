# LegalAgentBench Integration

**Status:** Post-MVP Extension
**Date:** 2025-12-26

**References:**
- [LegalAgentBench Paper (arXiv)](https://arxiv.org/abs/2412.17259)
- [GitHub Repository](https://github.com/CSHaitao/LegalAgentBench)
- [ACL 2025 Proceedings](https://aclanthology.org/2025.acl-long.116/)

---

## 1. Overview

LegalAgentBench is a Chinese legal domain benchmark for evaluating LLM agents with tool use. It complements L10's US case law focus with:

- Multi-hop reasoning tasks (300 annotated)
- 37 tools for external knowledge interaction
- Process rate scoring (intermediate steps)
- ReAct / Plan-and-Solve / Plan-and-Execute agent patterns

---

## 2. Tool Taxonomy (37 tools)

| Category | Count | Purpose |
|----------|-------|---------|
| Database Tools | 28 | Query structured legal databases |
| Text Retrievers | 3 | Search document collections |
| Math Tools | 5 | Arithmetic + sorting |
| System Tools | 1 | Finish/return answer |

### Database Tools (28)

Query 14 Chinese legal databases:

| Domain | Examples |
|--------|----------|
| Company | Registration, shareholders, subsidiaries |
| Cases | Court cases, administrative, restriction orders |
| Courts | Court info, jurisdiction |
| Law firms | Firm info, lawyer lookup |
| Documents | Legal documents, contracts |
| Dishonesty | Enforcement records |
| Address | Geocoding, resolution |

### Text Retrievers (3)

| Tool | Purpose |
|------|---------|
| Legal Knowledge Retriever | Search legal knowledge base |
| Article Retriever | Search legal articles/commentary |
| Guiding Case Retriever | Search precedent cases |

### Math Tools (5)

Sum, Subtract, Multiply, Divide, Rank/Sort

### System Tools (1)

Finish - return final answer

---

## 3. Mapping to L10 Architecture

### Tool Equivalence

| LegalAgentBench | L10 Equivalent |
|-----------------|----------------|
| Guiding Case Retriever | S5:rag (citing opinion retrieval) |
| Database query (case lookup) | `case_by_us_cite` index |
| Database query (overruling) | `overrule_by_us_cite` index |
| Finish | S6 IRAC output |

### Scoring Equivalence

| LegalAgentBench | L10 Equivalent |
|-----------------|----------------|
| Process rate | Per-step `StepResult.score` |
| Final success | `ChainResult.voided == False` and all `correct == True` |
| Intermediate steps | `ChainContext.step_results` |

---

## 4. Integration Options

### Option A: Parallel Benchmark

Run LegalAgentBench alongside L10 as separate evaluation:

```
legal-10/
├── chain/                    # L10 Agentic (US)
└── benchmarks/
    └── legalagentbench/      # CN benchmark (separate)
        ├── tools/
        ├── tasks/
        └── runner.py
```

**Pros:** Clean separation, no spec changes
**Cons:** No unified metrics

### Option B: Unified Tool Backend

Extend L10's `Backend` ABC to support tool calling:

```python
class ToolBackend(Backend):
    """Backend with tool-calling support."""

    tools: dict[str, Callable]

    def complete_with_tools(
        self,
        prompt: str,
        available_tools: list[str]
    ) -> tuple[str, list[ToolCall]]:
        """Return response + tool calls made."""
        pass
```

**Pros:** Unified architecture
**Cons:** Requires executor changes (post-MVP)

### Option C: L10 as LegalAgentBench Tools

Wrap L10 steps as LegalAgentBench-compatible tools:

| L10 Step | As Tool |
|----------|---------|
| S1 | `get_case_metadata(citation)` |
| S2 | `find_citing_cases(citation)` |
| S3 | `check_overruled(citation)` |
| S4 | `extract_disposition(opinion_text)` |
| S5 | `predict_agreement(cited, citing)` |

**Pros:** Cross-benchmark interop
**Cons:** Different task structure

---

## 5. Recommended Path

### Phase 1: MVP (Current)

No LegalAgentBench integration. Focus on L10 Agentic chain.

### Phase 2: Post-MVP Parallel

Add LegalAgentBench as separate benchmark:

1. Clone their repo into `benchmarks/legalagentbench/`
2. Run their eval independently
3. Compare agent patterns (their ReAct vs our sequential chain)

### Phase 3: Unified Tool Architecture

If tool-calling proves valuable:

1. Design `ToolBackend` ABC
2. Wrap L10 indexes as tools
3. Add agentic loop to executor (multi-turn)
4. Unified metrics across benchmarks

---

## 6. Research Questions

| Question | How LegalAgentBench Helps |
|----------|---------------------------|
| Does tool-calling improve legal reasoning? | Compare their ReAct vs L10 sequential |
| Cross-jurisdiction generalization? | CN vs US legal systems |
| Process vs outcome scoring? | Their process rate vs our per-step accuracy |
| Optimal agent pattern? | ReAct vs Plan-and-Solve vs sequential |

---

## 7. Technical Notes

### Running LegalAgentBench

```bash
git clone https://github.com/CSHaitao/LegalAgentBench.git
cd LegalAgentBench
pip install -r requirements.txt
cd src
# Edit utils.py with API key
python react.py --model gpt-4 --date 2025-12-26
```

### License

MIT - compatible with L10

### Data Format

`dataset.json` with annotated tasks. 300 tasks across difficulty levels.

---

## 8. Open Questions

1. **Language barrier:** Their data is Chinese. Do we need translated tasks or just evaluate on their original data?

2. **Tool parity:** Their 37 tools vs our 4 indexes. Should we expand L10's tool surface?

3. **Agent pattern:** Their ReAct loop vs our fixed S1→S7. Is flexibility better?

4. **Unified metrics:** Can we define a cross-benchmark score?