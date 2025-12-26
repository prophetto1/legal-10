# HELM Framework Analysis for Legal-10 Integration

**Package:** `crfm-helm` v0.5.11
**Source:** [stanford-crfm/helm](https://github.com/stanford-crfm/helm)
**Docs:** [crfm-helm.readthedocs.io](https://crfm-helm.readthedocs.io/)
**Generated:** 2025-12-25

---

## 1. HELM as a Library (Not a Fork)

HELM can be used as a Python library via `pip install crfm-helm`. No fork required.

### CLI Entry Points
```bash
helm-run          # Execute benchmark runs
helm-summarize    # Generate results summaries
helm-server       # Launch web UI (localhost:8000)
helm-create-plots # Create visualizations
```

### Programmatic API
```python
from helm.common.authentication import Authentication
from helm.proxy.services.remote_service import RemoteService
from helm.common.request import Request

# Direct model access (not benchmark runs)
service = RemoteService("https://crfm-models.stanford.edu")
auth = Authentication(api_key="...")
request = Request(model="openai/gpt-4o-mini-2024-07-18", prompt="...")
result = service.make_request(auth, request)
```

---

## 2. Core Extension Points

### 2.1 Scenario (Data Loading)

```python
from dataclasses import dataclass, field
from typing import List
from abc import ABC, abstractmethod

@dataclass
class Scenario(ABC):
    name: str = field(init=False)
    description: str = field(init=False)
    tags: List[str] = field(init=False)

    @abstractmethod
    def get_instances(self, output_path: str) -> List[Instance]:
        """Load and return benchmark instances."""
        pass
```

### 2.2 Instance (Data Unit)

```python
@dataclass(frozen=True)
class Input:
    text: str = ""
    multimedia_content: Optional[MultimediaObject] = None

@dataclass(frozen=True)
class Output:
    text: str = ""

@dataclass(frozen=True)
class Reference:
    output: Output
    tags: List[str]  # Include CORRECT_TAG for correct answers

@dataclass(frozen=True)
class Instance:
    input: Input
    references: List[Reference]
    split: Optional[str] = None      # TRAIN_SPLIT, TEST_SPLIT
    id: Optional[str] = None
    extra_data: Optional[Dict] = None
```

### 2.3 Constants

```python
TRAIN_SPLIT = "train"
TEST_SPLIT = "test"
VALID_SPLIT = "valid"
CORRECT_TAG = "correct"
```

### 2.4 RunSpec (Benchmark Configuration)

```python
@dataclass(frozen=True)
class RunSpec:
    name: str
    scenario_spec: ScenarioSpec      # Points to Scenario class
    adapter_spec: AdapterSpec        # Prompt formatting
    metric_specs: List[MetricSpec]   # Evaluation metrics
    groups: List[str] = field(default_factory=list)

# Registration decorator
@run_spec_function("my_benchmark")
def get_my_spec() -> RunSpec:
    ...
```

---

## 3. Existing Legal Scenarios in HELM

| Scenario | Run Spec | Task Type | Adapter |
|----------|----------|-----------|---------|
| **CaseHOLD** | `casehold` | 5-way MC | `ADAPT_MULTIPLE_CHOICE_JOINT` |
| **LegalBench** | `legalbench:subset=X` | Various | Varies by subset |
| **Legal Support** | `legal_support` | Binary MC | `ADAPT_MULTIPLE_CHOICE_JOINT` |
| **Legal Contract Summarization** | `legal_contract_summarization` | Generation | `get_generation_adapter_spec` |
| **Legal Opinion Sentiment** | `legal_opinion_sentiment_classification` | 3-class | Generation |
| **LexGLUE** | `lex_glue:subset=X` | Multi-label | Varies |
| **ECHR Judgment** | `echr_judgment_classification` | Binary | Generation |

---

## 4. CaseHOLD Implementation Pattern

```python
# From enterprise_run_specs.py
@run_spec_function("casehold")
def get_casehold_spec() -> RunSpec:
    scenario_spec = ScenarioSpec(
        class_name="helm.benchmark.scenarios.casehold_scenario.CaseHOLDScenario",
        args={}
    )

    adapter_spec = get_multiple_choice_adapter_spec(
        method=ADAPT_MULTIPLE_CHOICE_JOINT,
        instructions="Give a letter answer among A, B, C, D, or E.",
        input_noun="Passage",
        output_noun="Answer",
        max_train_instances=2,
    )

    return RunSpec(
        name="casehold",
        scenario_spec=scenario_spec,
        adapter_spec=adapter_spec,
        metric_specs=get_exact_match_metric_specs(),
        groups=["casehold"],
    )
```

---

## 5. Common Adapter Patterns

### Multiple Choice (5-way like CaseHOLD)
```python
adapter_spec = get_multiple_choice_adapter_spec(
    method=ADAPT_MULTIPLE_CHOICE_JOINT,
    instructions="Which holding is correct? Answer A, B, C, D, or E.",
    input_noun="Passage",
    output_noun="Answer",
    max_train_instances=2,  # Few-shot examples
)
```

### Generation (Open-ended)
```python
adapter_spec = get_generation_adapter_spec(
    instructions="Extract the legal holding from this opinion.",
    input_noun="Case",
    output_noun="Holding",
    max_tokens=512,
    stop_sequences=["\n\n"],
)
```

### Binary Classification
```python
adapter_spec = get_generation_adapter_spec(
    instructions="Is this case still good law? Answer yes or no.",
    input_noun="Citation",
    output_noun="Answer",
    max_tokens=3,
)
```

---

## 6. Common Metric Patterns

```python
from helm.benchmark.metrics.common_metric_specs import (
    get_exact_match_metric_specs,     # For MC, classification
    get_f1_metric_specs,              # Token-level F1
    get_basic_metric_specs,           # ROUGE, BLEU, etc.
)

# Exact match (MC, classification)
metric_specs = get_exact_match_metric_specs()

# Summarization
metric_specs = get_basic_metric_specs(["rouge_1", "rouge_2", "rouge_l"])

# Combined
metric_specs = get_exact_match_metric_specs() + get_f1_metric_specs()
```

---

## 7. Dataset Loading Patterns

### HuggingFace (Recommended)
```python
from datasets import load_dataset

def get_instances(self, output_path: str) -> List[Instance]:
    cache_dir = os.path.join(output_path, "data")
    ensure_directory_exists(cache_dir)

    dataset = load_dataset(
        "your-org/dataset-name",
        cache_dir=cache_dir,
        revision="main"  # Pin for reproducibility
    )

    instances = []
    for example in dataset["test"]:
        instance = Instance(
            input=Input(text=example["question"]),
            references=[Reference(Output(text=example["answer"]), tags=[CORRECT_TAG])],
            split=TEST_SPLIT,
            id=example["id"]
        )
        instances.append(instance)
    return instances
```

### Direct URL
```python
from helm.common.general import ensure_file_downloaded

def get_instances(self, output_path: str) -> List[Instance]:
    data_path = os.path.join(output_path, "data")
    ensure_file_downloaded(
        source_url="https://example.com/data.zip",
        target_path=data_path,
        unpack=True,
        unpack_type="zip"
    )
    # Then read local files...
```

---

## 8. Legal-10 Integration Options

### Option A: Register Custom Scenarios (Cleanest)

Create scenarios that HELM can discover:

```
your_package/
├── helm_scenarios/
│   ├── __init__.py
│   ├── legal_10_dahl_scenario.py
│   └── legal_10_chain_scenario.py
└── helm_run_specs/
    ├── __init__.py
    └── legal_10_run_specs.py
```

Register via entry points in `pyproject.toml`:
```toml
[project.entry-points."helm.benchmark.scenarios"]
legal_10 = "your_package.helm_scenarios"

[project.entry-points."helm.benchmark.run_specs"]
legal_10 = "your_package.helm_run_specs"
```

### Option B: Call HELM Directly

```python
import subprocess

# Run HELM as subprocess
subprocess.run([
    "helm-run",
    "--run-specs", "legal_10_s5_distinguish",
    "--models-to-run", "openai/gpt-4",
    "--max-eval-instances", "100",
    "--output-path", "benchmark_output/"
])
```

### Option C: Import HELM Internals

```python
from helm.benchmark.scenarios.scenario import Scenario, Instance
from helm.benchmark.run_spec import RunSpec, ScenarioSpec
from helm.benchmark.adaptation.common_adapter_specs import get_generation_adapter_spec
from helm.benchmark.metrics.common_metric_specs import get_exact_match_metric_specs

# Build run spec programmatically
run_spec = RunSpec(
    name="legal_10_s5",
    scenario_spec=ScenarioSpec(
        class_name="legal_10.scenarios.S5DistinguishScenario",
        args={"mode": "rag"}
    ),
    adapter_spec=get_generation_adapter_spec(...),
    metric_specs=get_exact_match_metric_specs(),
    groups=["legal_10"]
)
```

---

## 9. What HELM Does NOT Do (Critical for L10 Agentic)

**HELM's contract:**
```
Scenario → Instances → Adapter → ONE request per instance → Metrics
```

**HELM does NOT:**
- Chain outputs from one skill to input of next skill
- Maintain state across instances
- Support agentic multi-step workflows
- Do retrieval (RAG must be embedded in instance input)

**For L10 Agentic Chain:**
- Option 1: Keep chain orchestration **outside HELM** (use Dahl codebase)
- Option 2: Build chain as **single scenario** where each instance = entire chain
- Option 3: Run skills as **separate HELM runs** with external context passing

---

## 10. Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  L10 Agentic Chain Orchestrator (Your Python Code)         │
│  - Load ChainInstances from Dahl data                       │
│  - Execute S1→S2→S3→S4→S5→S6→S7 sequence                   │
│  - Manage context passing between skills                    │
│  - Apply S7 gating logic                                    │
│  - Compute chain metrics                                    │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ HELM Scenario   │  │ HELM Scenario   │  │ HELM Scenario   │
│ (S5 Atomic)     │  │ (CaseHOLD)      │  │ (Future: CUAD)  │
│                 │  │                 │  │                 │
│ For comparison  │  │ Already exists  │  │ Optional        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Rationale:**
- Chain logic stays in your codebase (Dahl-derived)
- HELM used for atomic skill benchmarks (optional comparability)
- Avoids fighting HELM's instance-based architecture

---

## 11. Key Imports Reference

```python
# Scenario definition
from helm.benchmark.scenarios.scenario import (
    Scenario, Instance, Input, Output, Reference,
    TRAIN_SPLIT, TEST_SPLIT, CORRECT_TAG
)

# Run spec definition
from helm.benchmark.run_spec import RunSpec, run_spec_function
from helm.benchmark.scenarios.scenario import ScenarioSpec

# Adapters
from helm.benchmark.adaptation.adapter_spec import AdapterSpec
from helm.benchmark.adaptation.common_adapter_specs import (
    get_generation_adapter_spec,
    get_multiple_choice_adapter_spec,
)

# Metrics
from helm.benchmark.metrics.metric_spec import MetricSpec
from helm.benchmark.metrics.common_metric_specs import (
    get_exact_match_metric_specs,
    get_basic_metric_specs,
    get_f1_metric_specs,
)

# Utilities
from helm.common.general import ensure_directory_exists, ensure_file_downloaded
```

---

## 12. Running HELM

```bash
# Install
pip install crfm-helm

# Run a legal benchmark
helm-run \
  --run-specs casehold \
  --models-to-run openai/gpt-4 \
  --max-eval-instances 50 \
  --output-path ./output

# Summarize results
helm-summarize --output-path ./output

# View results
helm-server --output-path ./output
# Open http://localhost:8000
```

---

## Summary

| Aspect | HELM Capability | L10 Agentic Need | Resolution |
|--------|-----------------|------------------|------------|
| Data loading | HuggingFace / URL | Dahl CSVs | Load in scenario or externally |
| Single-step eval | Native | N/A | Use as-is |
| Multi-step chain | NOT supported | Required | Build chain orchestrator externally |
| RAG context | Must embed in input | S1-S6 need RAG | Pre-compute RAG, embed in instance |
| Metrics | Built-in library | Custom S6/S7 | Extend Metric class or compute externally |
| Comparison | CaseHOLD exists | S5 comparison | Use CaseHOLD as baseline for S5-CB |
