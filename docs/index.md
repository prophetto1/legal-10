​
# L10 Agentic

## A Chained Legal Reasoning Benchmark for Large Language Models

### The Problem

Existing legal AI benchmarks evaluate models on **independent, parallel tasks**. A model answers a citation question, gets scored, then answers an unrelated extraction question, gets scored again. Each task exists in isolation.

But legal reasoning doesn't work that way.

A lawyer researching case law performs **sequential, dependent operations**: find relevant authority → verify it's still good law → extract the holding → apply it to new facts → synthesize into analysis. Each step builds on the last. An error at step 2 corrupts everything downstream.

**L10 Agentic** is the first U.S. common law benchmark that evaluates LLMs on **chained legal reasoning**—measuring not just whether models get individual answers right, but whether they can maintain coherent reasoning across a complete legal research workflow.

### The Chain
```
RULE PHASE
  S1  Known Authority
  S2  Unknown Authority
  S3  Validate Authority
        ↓
APPLICATION PHASE
  S4  Fact Extraction
  S5  Distinguish Cases (cb + rag variants)
        ↓
CONCLUSION PHASE
  S6  IRAC Synthesis
  S7  Citation Integrity ← gate: fabrication voids S6
```
### Architecture

```
legal-10/
├── core/                          # Frozen contracts
│   ├── ids/                       # Canonical ID generation
│   ├── schemas/                   # CourtCase, ChainInstance, StepResult
│   └── scoring/                   # Deterministic scorers
│
├── chain/                         # Execution engine
│   ├── datasets/                  # HuggingFace loaders, instance builder
│   ├── backends/                  # LLM backends (Mock, Dahl, etc.)
│   ├── steps/                     # S1-S7 implementations
│   └── runner/                    # ChainExecutor state machine
│
├── scripts/                       # CLI tools
├── tests/                         # 247 tests
└── legal-10-notes/                # Specifications
```

### Chained Steps

The following steps were chained by shifting the framing of the test slightly.

| Step | Name | Task | Ground Truth |
|------|------|------|--------------|
| **S1** | Known Authority | Retrieve citation and metadata for a given case | `cited_case.us_cite`, `term` |
| **S2** | Unknown Authority | Find cases that cite the anchor case | `edge.citing_case_us_cite` (MRR) |
| **S3** | Validate Authority | Determine if case has been overruled | `instance.overrule` |
| **S4** | Fact Extraction | Extract disposition and winning party | SCDB codes (closed enum) |
| **S5:cb** | Distinguish Cases | Determine doctrinal relationship (metadata + holding) | `edge.agree` |
| **S5:rag** | Distinguish Cases | Determine doctrinal relationship (full opinion texts) | `edge.agree` |
| **S6** | IRAC Synthesis | Generate structured legal analysis | Deterministic rubric |
| **S7** | Citation Integrity | Verify no fabricated citations | `fake_cases` + `scdb` |

A model achieving 90% accuracy per step completes only **48% of full chains** (0.9^7). Chained evaluation reveals failure patterns that parallel benchmarks miss.

### Dual-Modality Testing

S5 runs in two modes to measure how much model performance depends on context availability:

| Mode | Input | Purpose |
|------|-------|---------|
| **S5:cb** | Case metadata + S4 extracted holding | Reasoning from minimal context |
| **S5:rag** | Full opinion texts for both cases | Reasoning with complete information |

The difference in accuracy between modes—the **Reasoning Bridge Gap**—quantifies the contribution of retrieval versus reasoning from extracted information alone. Both variants use the same ground truth (`edge.agree`), enabling direct comparison.
### Run a Chain

```python
from chain.datasets.loaders import load_datasets
from chain.datasets.builder import DatasetBuilder
from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps import (
    S1KnownAuthority, S2UnknownAuthority, S3ValidateAuthority,
    S4FactExtraction, S5DistinguishCB, S5DistinguishRAG,
    S6IRACSynthesis, S7CitationIntegrity
)

# Load data
bundle = load_datasets()
builder = DatasetBuilder(bundle)

# Get one instance
instance = next(builder.iter_chain_instances())

# Build chain
steps = [
    S1KnownAuthority(),
    S2UnknownAuthority(),
    S3ValidateAuthority(),
    S4FactExtraction(),
    S5DistinguishCB(),
    S5DistinguishRAG(),
    S6IRACSynthesis(),
    S7CitationIntegrity(),
]

# Execute
backend = MockBackend()  # Or real LLM backend
executor = ChainExecutor(backend=backend, steps=steps)
result = executor.execute(instance)
```

## Data 

| Source | Size | Contents |
|--------|------|----------|
| `scdb_sample.csv` | 5,000 cases | SCOTUS cases with full opinion text |
| `scotus_shepards_sample.csv` | 5,000 pairs | Case citation relationships |
| `scotus_overruled_db.csv` | 288 records | Overruling relationships |
| `fake_cases.csv` | 999 cases | Fabricated cases for hallucination detection |

#### Coverage Tiers

The two sample files are independently drawn, creating coverage tiers:

| Tier | Requirement | Available Steps |
|------|-------------|-----------------|
| CHAIN_CORE | Cited case has opinion text | S1, S2, S3, S4, S5:cb, S6, S7 |
| CHAIN_RAG_SUBSET | Both cases have opinion text | All steps including S5:rag |

#### Per-Step

| Metric | Definition |
|--------|------------|
| Accuracy | `correct / executed` |
| Mean Score | `mean(score)` for executed steps |
| Coverage | `executed / total instances` |

#### Chain-Level

| Metric | Definition |
|--------|------------|
| Chain Completion Rate | Chains with all steps correct / total |
| Mean Failure Position | Average step index of first error (1-indexed) |
| Void Rate | Chains voided by S7 gate / total |

### S5 Comparison

| Metric | Definition |
|--------|------------|
| Reasoning Bridge Gap | S5:rag accuracy − S5:cb accuracy (aligned subset) |

### Architecture

```
legal-10/
├── core/                          # Frozen contracts
│   ├── ids/                       # Canonical ID generation
│   ├── schemas/                   # CourtCase, ChainInstance, StepResult
│   └── scoring/                   # Deterministic scorers
│
├── chain/                         # Execution engine
│   ├── datasets/                  # HuggingFace loaders, instance builder
│   ├── backends/                  # LLM backends (Mock, Dahl, etc.)
│   ├── steps/                     # S1-S7 implementations
│   └── runner/                    # ChainExecutor state machine
│
├── scripts/                       # CLI tools
├── tests/                         # 247 tests
└── legal-10-notes/                # Specifications
```

### Citation

```bibtex
@article{chung2025l10,
  title={L10 Agentic: A Chained Evaluation Protocol for Legal Reasoning in Large Language Models},
  author={Chung, Jon W.},
  journal={scheduled; info will be released shortly},
  year={2025}
}
```

This project uses data from the Legal Hallucinations study. Please also cite:

```bibtex
@article{dahl2024largelegalfictions,
  title   = {Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models},
  author  = {Matthew Dahl and Varun Magesh and Mirac Suzgun and Daniel E. Ho},
  year    = {2024},
  journal = {Journal of Legal Analysis},
  volume  = {16},
  number  = {1},
  pages   = {64--93},
  doi     = {10.1093/jla/laae003}
}
```
- License: MIT

### Roadmap

**v1.0 (Current) — MVP Complete**

- 7-step chain architecture
- All steps implemented (S1-S7)
- ChainExecutor with dependency resolution
- S5 dual-modality (CB + RAG)
- S7 citation integrity gate
- MockBackend for testing
- Total 247 tests passing
- HuggingFace data integration

**v1.1 — Production Runs**

- Real LLM backend integration
- Pilot run (100 instances)
- Full dataset run (CHAIN_CORE)
- JSONL + Markdown output
- Results visualization
- easoning Bridge Gap measurement

**v2.0 — External Benchmark Integration**

- HELM Integration

- Additional Benchmarks

| Benchmark | Jurisdiction | Integration Point |
|-----------|--------------|-------------------|
| CaseHOLD | US | S5:cb comparison baseline |
| LegalBench | US | S3, S4 task injection |
| LegalAgentBench | Chinese | Tool-calling evaluation |

- Multi-Judge S6

```python
class S6MultiJudge(Step):
    judges = ["gpt-4", "claude-3", "gemini"]

    def score(self, parsed, ctx):
        scores = [judge.evaluate(parsed, RUBRIC) for judge in self.judges]
        return mean(scores), std(scores)

```