# L10 Agentic Chain Specification

**Version:** 2.2
**Date:** 2025-12-26
**Status:** Ready for implementation

**Related Documents:**
- `PROMPT_CONTRACT.md` - Locked prompt schemas and output contracts
- `MVP_BUILD_ORDER.md` - Implementation phases and exit criteria
- `DATA_SCHEMAS.md` - Source data reference

---

## 1. Project Structure

```
legal-10/
│
├── core/                               # Shared stable contract
│   ├── __init__.py
│   ├── ids/
│   │   ├── __init__.py
│   │   └── canonical.py                # ID schemes (see §1.1)
│   ├── normalize/
│   │   ├── __init__.py
│   │   ├── citations.py                # Citation canonicalization
│   │   └── courts.py                   # Court/term normalization
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── case.py                     # CourtCase, ShepardsEdge, OverruleRecord
│   │   ├── chain.py                    # ChainInstance, ChainContext
│   │   ├── results.py                  # StepResult, ChainResult
│   │   └── ground_truth.py             # S4GroundTruth, etc.
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── exact_match.py
│   │   ├── citation_extract.py
│   │   └── citation_verify.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── templates.py
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── jsonl.py
│   │   └── metrics.py                  # Chain metrics aggregator
│   └── config/
│       ├── __init__.py
│       └── settings.py
│
├── chain/                              # L10 Agentic chain executor
│   ├── __init__.py
│   ├── third_party/
│   │   └── dahl_harness/               # Vendored Dahl code (minimal edits)
│   │       ├── __init__.py
│   │       ├── api.py
│   │       ├── models.py
│   │       └── correctness_checks.py
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py                     # Backend ABC
│   │   ├── dahl_backend.py             # Wraps Dahl APIBackend
│   │   └── mock_backend.py             # Canned responses for tests
│   ├── steps/
│   │   ├── __init__.py
│   │   ├── base.py                     # Step ABC
│   │   ├── s1_known_authority.py
│   │   ├── s2_unknown_authority.py
│   │   ├── s3_validate_authority.py
│   │   ├── s4_fact_extraction.py
│   │   ├── s5_distinguish.py           # S5DistinguishCB, S5DistinguishRAG
│   │   ├── s6_irac_synthesis.py
│   │   └── s7_citation_integrity.py
│   ├── runner/
│   │   ├── __init__.py
│   │   └── executor.py                 # ChainExecutor (S1→S7 state machine)
│   └── datasets/
│       ├── __init__.py
│       ├── loaders.py                  # HuggingFace dataset loaders
│       └── builder.py                  # ChainInstance builder (joins + coverage)
│
├── scripts/
│   ├── build_dataset.py                # CLI: build chain instances
│   ├── validate_joins.py               # CLI: validate join coverage
│   ├── run_chain.py                    # CLI: execute chains
│   └── summarize_run.py                # CLI: compute metrics
│
├── tests/
│   ├── __init__.py
│   ├── test_ids.py
│   ├── test_normalize.py
│   ├── test_schemas.py
│   ├── test_steps.py
│   └── test_runner.py
│
├── docs/                               # MkDocs documentation
│
└── legal-10-notes/                     # Development notes
```

### 1.1 ID Schemes

| Entity | Format | Example |
|--------|--------|---------|
| SCOTUS Case | `scotus::<usCite>::<term>` | `scotus::347_US_483::1954` |
| Case Pair | `pair::<cited_us_cite>::<citing_us_cite>` | `pair::347_US_483::349_US_294` |

**Canonicalization rules:**
- Replace spaces with underscores in citations
- Remove periods from citation abbreviations
- Lowercase all characters

---

## 2. Data Architecture

### 2.1 Source Data

**HuggingFace Dataset:** `reglab/legal_hallucinations_paper_data`

| File | Path | Size | Rows | Purpose |
|------|------|------|------|---------|
| `scdb_sample.csv` | `/samples/` | 94.6 MB | 5,000 | SCOTUS cases with majority opinions |
| `scotus_shepards_sample.csv` | `/samples/` | 1.32 MB | 5,000 | Case pairs with `agree` field |
| `scotus_overruled_db.csv` | `/samples/` | 36.7 kB | 288 | Overruling relationships |
| `fake_cases.csv` | `/samples/` | 78.6 kB | 999 | Fabricated cases for S7 |
| `fowler_scores.csv` | `/sources/` | 1.76 MB | — | Case importance scores (optional) |

### 2.2 Join Keys

```
scdb_sample.usCite ────────┬──► scotus_shepards_sample.cited_case_us_cite
                           └──► scotus_overruled_db.overruled_case_us_id

scdb_sample.lexisCite ─────────► fowler_scores.lex_id (optional)
```

### 2.3 ChainInstance Unit

One chain instance corresponds to one Shepard's edge:

```
ChainInstance
├── id: str                         # "pair::<cited>::<citing>"
├── cited_case: CourtCase           # Resolved from scdb_sample (required)
├── citing_case: CourtCase | None   # May not resolve from scdb_sample
├── edge: ShepardsEdge              # Contains agree field
└── overrule: OverruleRecord | None # None if cited_case not overruled
```

### 2.4 Indexes

Built once in `builder.py`:

```python
case_by_us_cite: dict[str, CourtCase]           # scdb_sample keyed by usCite
overrule_by_us_cite: dict[str, OverruleRecord]  # scotus_overruled_db keyed by overruled_case_us_id
fake_us_cites: set[str]                         # fake_cases.us_citation
fake_case_names: set[str]                       # fake_cases.case_name (normalized)
```

### 2.5 Coverage Policy

#### Problem

`scotus_shepards_sample` and `scdb_sample` are independently sampled (5,000 rows each). The `supreme_court == 1` flag in Shepard's data indicates both cases are SCOTUS in the **full** SCDB, not that both appear in `scdb_sample`.

Consequence: `citing_case` may not resolve, or may lack `majority_opinion`.

#### Two-Tier Policy

| Tier | Requirement | Enforcement |
|------|-------------|-------------|
| **A** (Required) | `cited_case` exists in `scdb_sample` with `majority_opinion` present | Build-time: exclude instances failing Tier A |
| **B** (Optional) | `citing_case` exists with `majority_opinion` present | Run-time: S5:rag skipped if Tier B fails |

#### Build-Time Flags

Computed in `builder.py` per instance:

```python
has_cited_text: bool = (
    instance.cited_case is not None
    and instance.cited_case.majority_opinion is not None
)

has_citing_text: bool = (
    instance.citing_case is not None
    and instance.citing_case.majority_opinion is not None
)
```

#### Dataset Splits

| Split | Condition | Use |
|-------|-----------|-----|
| `CHAIN_CORE` | `has_cited_text == True` | All chain runs |
| `CHAIN_RAG_SUBSET` | `has_cited_text == True` and `has_citing_text == True` | FRD gap computation |

---

## 3. Core Schemas

### 3.1 CourtCase

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CourtCase:
    us_cite: str                        # "347 U.S. 483"
    case_name: str                      # "Brown v. Board of Education"
    term: int                           # SCDB term (year)
    maj_opin_writer: int | None         # SCDB majOpinWriter code
    case_disposition: int | None        # SCDB caseDisposition code
    party_winning: int | None           # SCDB partyWinning (1=petitioner, 0=respondent, 2=unclear)
    issue_area: int | None              # SCDB issueArea code
    majority_opinion: str | None        # Full opinion text
    lexis_cite: str | None              # LexisNexis citation
    sct_cite: str | None                # Supreme Court Reporter citation
    importance: float | None            # pauth_score from fowler_scores
```

### 3.2 ShepardsEdge

```python
@dataclass(frozen=True)
class ShepardsEdge:
    cited_case_us_cite: str             # US citation of cited case
    citing_case_us_cite: str            # US citation of citing case
    cited_case_name: str | None         # Name of cited case
    citing_case_name: str | None        # Name of citing case
    shepards: str                       # Signal: "followed", "distinguished", etc.
    agree: bool                         # True if followed/parallel, False otherwise
    cited_case_year: int | None         # Year of cited case
    citing_case_year: int | None        # Year of citing case
```

### 3.3 OverruleRecord

```python
@dataclass(frozen=True)
class OverruleRecord:
    overruled_case_us_id: str           # US citation of overruled case
    overruled_case_name: str            # Name of overruled case
    overruling_case_name: str           # Name of case that overruled
    year_overruled: int                 # Year overruled
    overruled_in_full: bool             # True if fully overruled
```

### 3.4 ChainInstance

```python
@dataclass(frozen=True)
class ChainInstance:
    id: str                             # "pair::<cited>::<citing>"
    cited_case: CourtCase               # Always present (Tier A)
    citing_case: CourtCase | None       # May be None (Tier B)
    edge: ShepardsEdge                  # Shepard's relationship data
    overrule: OverruleRecord | None     # None if not overruled
```

### 3.5 ChainContext

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.schemas.results import StepResult

@dataclass
class ChainContext:
    """Mutable state carrier passed through S1→S7."""
    instance: ChainInstance
    step_results: dict[str, "StepResult"] = field(default_factory=dict)

    def get(self, step_id: str) -> "StepResult | None":
        """Get result by step_id (e.g., 's4', 's5:cb')."""
        return self.step_results.get(step_id)

    def set(self, step_id: str, result: "StepResult") -> None:
        """Store result by step_id."""
        self.step_results[step_id] = result

    def has_step(self, step_name: str) -> bool:
        """Check if any variant of a logical step has run."""
        return any(sr.step == step_name for sr in self.step_results.values())

    def get_by_step(self, step_name: str) -> "StepResult | None":
        """Get first result matching logical step name."""
        for sr in self.step_results.values():
            if sr.step == step_name:
                return sr
        return None
```

### 3.6 StepResult

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class StepResult:
    # Identity
    step_id: str                        # Unique key: "s1", "s5:cb", "s5:rag", etc.
    step: str                           # Logical step name: "s1", "s2", ..., "s7"
    variant: str | None                 # "cb", "rag", or None

    # Execution status
    status: str                         # "OK" | "SKIPPED_COVERAGE" | "SKIPPED_DEPENDENCY"

    # Raw I/O
    prompt: str                         # Prompt sent to LLM
    raw_response: str                   # Raw LLM response

    # Parsed output
    parsed: dict[str, Any]              # Structured parse of response

    # Ground truth and scoring
    ground_truth: dict[str, Any]        # Expected values
    score: float                        # 0.0 - 1.0
    correct: bool                       # Binary correctness

    # Voiding (S6 only, triggered by S7 gate)
    voided: bool = False                # True if S7 gate voided this result
    void_reason: str | None = None      # Reason for voiding

    # Provenance
    model: str = ""                     # Model identifier
    timestamp: float = 0.0              # Unix timestamp
    latency_ms: float = 0.0             # Response latency
    tokens_in: int = 0                  # Input token count
    tokens_out: int = 0                 # Output token count
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `"OK"` | Step executed successfully (may still be incorrect) |
| `"SKIPPED_COVERAGE"` | Step skipped due to missing data (e.g., S5:rag without citing text) |
| `"SKIPPED_DEPENDENCY"` | Step skipped because a required prior step did not run |

### 3.7 ChainResult

```python
@dataclass
class ChainResult:
    instance_id: str                    # ChainInstance.id
    step_results: dict[str, StepResult] # Keyed by step_id
    voided: bool                        # True if S7 gate triggered
    void_reason: str | None             # Reason if voided
```

### 3.8 S4GroundTruth

```python
@dataclass(frozen=True)
class S4GroundTruth:
    """Ground truth for S4: Fact Extraction."""
    disposition_code: int | None        # SCDB caseDisposition (raw code)
    disposition: str | None             # Derived text: "affirmed", "reversed", etc.
    party_winning: int | None           # SCDB partyWinning (1/0/2)
    issue_area: int | None              # SCDB issueArea (optional for v1)
```

**Disposition code mapping:**

| Code | Text |
|------|------|
| 1 | stay, petition, or motion granted |
| 2 | affirmed |
| 3 | reversed |
| 4 | reversed and remanded |
| 5 | vacated and remanded |
| 6 | affirmed and reversed in part |
| 7 | affirmed and vacated in part |
| 8 | affirmed and reversed in part and remanded |
| 9 | vacated |
| 10 | petition denied or appeal dismissed |
| 11 | certification to or from a lower court |

---

## 4. Step Contract

### 4.1 Step ABC

```python
from abc import ABC, abstractmethod
from typing import Any

class Step(ABC):
    """Abstract base class for chain steps."""

    name: str                           # Logical name: "s1", "s2", ..., "s7"
    variant: str | None = None          # "cb", "rag", or None

    @property
    def step_id(self) -> str:
        """Unique identifier for this step instance."""
        if self.variant:
            return f"{self.name}:{self.variant}"
        return self.name

    @abstractmethod
    def requires(self) -> set[str]:
        """
        ~~Return set of logical step names this step depends on.~~

        ~~Example: {"s1", "s4"} means this step requires S1 and S4 to have run.~~
        ~~The executor checks if ANY variant of the required step has run.~~

        Return set of step_ids this step depends on.

        Example: {"s1", "s4"} means this step requires S1 and S4.
        For S5 variants, use explicit step_id: {"s5:cb"} not {"s5"}.
        Only steps with status="OK" satisfy dependencies.
        """
        pass

    @abstractmethod
    def prompt(self, ctx: "ChainContext") -> str:
        """Generate prompt from chain context."""
        pass

    @abstractmethod
    def parse(self, response: str) -> dict[str, Any]:
        """Parse raw LLM response into structured output."""
        pass

    @abstractmethod
    def ground_truth(self, ctx: "ChainContext") -> dict[str, Any]:
        """Extract ground truth from ChainInstance."""
        pass

    @abstractmethod
    def score(self, parsed: dict[str, Any], truth: dict[str, Any]) -> tuple[float, bool]:
        """
        Score parsed output against ground truth.

        Returns:
            tuple[float, bool]: (score between 0.0-1.0, binary correctness)
        """
        pass
```

### 4.2 Step Identifiers

| Step | `name` | `variant` | `step_id` |
|------|--------|-----------|-----------|
| S1 | `"s1"` | `None` | `"s1"` |
| S2 | `"s2"` | `None` | `"s2"` |
| S3 | `"s3"` | `None` | `"s3"` |
| S4 | `"s4"` | `None` | `"s4"` |
| S5 (CB) | `"s5"` | `"cb"` | `"s5:cb"` |
| S5 (RAG) | `"s5"` | `"rag"` | `"s5:rag"` |
| S6 | `"s6"` | `None` | `"s6"` |
| S7 | `"s7"` | `None` | `"s7"` |

**Key distinction:**
- `step_id` is the **unique key** in `ChainContext.step_results`
- ~~`step` (logical name) is used for **dependency resolution**~~
- `step_id` is also used for **dependency resolution** (v2.1)

### 4.3 Step Dependencies

~~| Step | `requires()` | Ground Truth Source | Notes |~~
~~|------|--------------|---------------------|-------|~~
~~| S1 | `{}` | `instance.cited_case` | Entry point |~~
~~| S2 | `{"s1"}` | `instance.edge.citing_case_us_cite` | — |~~
~~| S3 | `{"s1"}` | `instance.overrule` | `None` if not overruled (valid result) |~~
~~| S4 | `{"s1"}` | `S4GroundTruth` | Requires `cited_case.majority_opinion` (Tier A) |~~
~~| S5:cb | `{"s4"}` | `instance.edge.agree` | Always runs if S4 ran |~~
~~| S5:rag | `{"s1", "s4"}` | `instance.edge.agree` | Requires `citing_case.majority_opinion` (Tier B) |~~
~~| S6 | `{"s1", "s2", "s3", "s4", "s5"}` | Rubric-based | See §4.5 |~~
~~| S7 | `{"s6"}` | `fake_cases` + `scdb_sample` | Integrity gate |~~

| Step | `requires()` | Ground Truth Source | Notes |
|------|--------------|---------------------|-------|
| S1 | `set()` | `instance.cited_case` | Entry point |
| S2 | `{"s1"}` | `instance.edge.citing_case_us_cite` | — |
| S3 | `{"s1"}` | `instance.overrule` | `None` if not overruled (valid result) |
| S4 | `{"s1"}` | `S4GroundTruth` | Requires `cited_case.majority_opinion` (Tier A) |
| S5:cb | `{"s4"}` | `instance.edge.agree` | Always runs if S4 succeeded |
| S5:rag | `{"s1", "s4"}` | `instance.edge.agree` | Requires `citing_case.majority_opinion` (Tier B) |
| S6 | `{"s1", "s2", "s3", "s4", "s5:cb"}` | Rubric-based | Requires S5:cb explicitly (not S5:rag) |
| S7 | `{"s6"}` | `fake_cases` + `scdb_sample` | Integrity gate |

**Note:** `requires()` returns `step_id` values. Only results with `status="OK"` satisfy dependencies.

### 4.4 S5 Variant Execution

S5:cb and S5:rag are **independent**. Both may execute on the same instance:

- **S5:cb** always runs if S4 succeeded (uses S4 extracted holding only)
- **S5:rag** runs only if S4 succeeded AND `citing_case.majority_opinion` exists

They do not depend on each other. Both results are stored separately:
- `step_results["s5:cb"]`
- `step_results["s5:rag"]`

For FRD gap computation (§7.3), only instances where **both** variants ran with `status="OK"` are included.

### 4.5 S6 Dependency Behavior

~~S6 requires `{"s1", "s2", "s3", "s4", "s5"}`.~~

S6 requires `{"s1", "s2", "s3", "s4", "s5:cb"}`.

~~**Execution policy:** S6 runs if all required steps **executed** (have entries in `step_results`), regardless of whether they succeeded (`correct=True`) or failed (`correct=False`).~~

**Execution policy:** S6 runs if all required steps have `status="OK"`. A step with `status="SKIPPED_*"` or missing does **not** satisfy the dependency.

**Rationale:** S6 synthesizes outputs from prior steps. If a prior step failed to execute (skipped), S6 cannot synthesize from missing input. However, if a prior step executed but produced an incorrect answer (`correct=False`), S6 still runs — the chain measures end-to-end performance including error propagation.

**Key change (v2.1):** S6 explicitly requires `"s5:cb"` (the backbone), not the logical name `"s5"`. S5:rag is optional enrichment and does not gate S6.

**Edge cases:**

- ~~If S2 has `status="SKIPPED_DEPENDENCY"`, S6 still runs but with missing S2 input~~
- If S2 has `status="SKIPPED_DEPENDENCY"`, S6 is also skipped (dependency not satisfied)
- If S3 ran with `status="OK"` but `correct=False`, S6 still runs (uses S3's incorrect output)
- If S3 ground truth is `None` (not overruled), S3 still runs with `status="OK"` and S6 uses that result

---

## 5. Backend Contract

### 5.1 Backend ABC

```python
from abc import ABC, abstractmethod

class Backend(ABC):
    """Abstract base class for LLM backends."""

    model_name: str

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """
        Send prompt to LLM and return raw response text.

        Args:
            prompt: The prompt string to send

        Returns:
            str: Raw response text from the model
        """
        pass
```

### 5.2 DahlBackend

```python
class DahlBackend(Backend):
    """Wraps Dahl's APIBackend for use in chain executor."""

    def __init__(self, api_backend_type, model_name: str, **kwargs):
        self.model_name = model_name
        self.api_backend_type = api_backend_type
        self.kwargs = kwargs

    def complete(self, prompt: str) -> str:
        # Implementation wraps Dahl's api.py
        pass
```

### 5.3 MockBackend

```python
class MockBackend(Backend):
    """Deterministic canned responses for testing."""

    def __init__(self, responses: dict[str, str] | None = None):
        """
        Args:
            responses: Dict mapping prompt substrings to responses.
                       If prompt contains key, return corresponding value.
        """
        self.model_name = "mock"
        self.responses = responses or {}
        self.call_count = 0
        self.call_log: list[str] = []

    def complete(self, prompt: str) -> str:
        self.call_count += 1
        self.call_log.append(prompt)

        for key, response in self.responses.items():
            if key in prompt:
                return response

        return '{"answer": "mock_response"}'
```

---

## 6. Chain Runner

### 6.1 ChainExecutor

```python
import time
from typing import List

class ChainExecutor:
    """Executes S1→S7 chain on a ChainInstance."""

    def __init__(
        self,
        steps: List[Step],
        backend: Backend,
        config: "RunConfig"
    ):
        """
        Args:
            steps: Ordered list of Step instances to execute.
            backend: LLM backend for completions.
            config: Run configuration.
        """
        self.steps = steps                  # Ordered list (not dict)
        self.backend = backend
        self.config = config

    def run(self, instance: ChainInstance) -> ChainResult:
        """Execute chain on a single instance."""
        ctx = ChainContext(instance=instance, step_results={})

        for step in self.steps:
            result = self._execute_step(step, ctx)
            ctx.set(step.step_id, result)

            # S7 gate: if S7 ran and found fabrication, void S6
            if step.name == "s7" and result.status == "OK" and not result.correct:
                self._void_s6(ctx)

        return ChainResult(
            instance_id=instance.id,
            step_results=ctx.step_results,
            voided=self._is_voided(ctx),
            void_reason=self._get_void_reason(ctx)
        )

    def _execute_step(self, step: Step, ctx: ChainContext) -> StepResult:
        """Execute a single step."""

        # ~~Check dependencies (logical step names)~~
        # ~~required = step.requires()~~
        # ~~ran_steps = {sr.step for sr in ctx.step_results.values()}~~
        # ~~missing = required - ran_steps~~

        # Check dependencies (step_ids, only status="OK" satisfies) [v2.1]
        required = step.requires()
        satisfied = {
            sr.step_id
            for sr in ctx.step_results.values()
            if sr.status == "OK"
        }
        missing = required - satisfied

        if missing:
            return self._skipped_dependency(step, missing)

        # Check coverage for S5:rag
        if step.name == "s5" and step.variant == "rag":
            if not self._has_citing_text(ctx.instance):
                return self._skipped_coverage(step, "citing_case.majority_opinion is None")

        # Execute step
        try:
            prompt = step.prompt(ctx)

            start_time = time.time()
            raw_response = self.backend.complete(prompt)
            latency_ms = (time.time() - start_time) * 1000

            parsed = step.parse(raw_response)
            truth = step.ground_truth(ctx)
            score, correct = step.score(parsed, truth)

            return StepResult(
                step_id=step.step_id,
                step=step.name,
                variant=step.variant,
                status="OK",
                prompt=prompt,
                raw_response=raw_response,
                parsed=parsed,
                ground_truth=truth,
                score=score,
                correct=correct,
                model=self.backend.model_name,
                timestamp=time.time(),
                latency_ms=latency_ms
            )

        except Exception as e:
            return self._failed_step(step, str(e))

    def _skipped_dependency(self, step: Step, missing: set[str]) -> StepResult:
        """Create result for step skipped due to missing dependency."""
        return StepResult(
            step_id=step.step_id,
            step=step.name,
            variant=step.variant,
            status="SKIPPED_DEPENDENCY",
            prompt="",
            raw_response=f"Missing dependencies: {missing}",
            parsed={},
            ground_truth={},
            score=0.0,
            correct=False,
            model=self.backend.model_name,
            timestamp=time.time()
        )

    def _skipped_coverage(self, step: Step, reason: str) -> StepResult:
        """Create result for step skipped due to missing data."""
        return StepResult(
            step_id=step.step_id,
            step=step.name,
            variant=step.variant,
            status="SKIPPED_COVERAGE",
            prompt="",
            raw_response=reason,
            parsed={},
            ground_truth={},
            score=0.0,
            correct=False,
            model=self.backend.model_name,
            timestamp=time.time()
        )

    def _failed_step(self, step: Step, error: str) -> StepResult:
        """Create result for step that raised an exception."""
        return StepResult(
            step_id=step.step_id,
            step=step.name,
            variant=step.variant,
            status="OK",  # Execution attempted
            prompt="",
            raw_response=f"ERROR: {error}",
            parsed={},
            ground_truth={},
            score=0.0,
            correct=False,
            model=self.backend.model_name,
            timestamp=time.time()
        )

    def _has_citing_text(self, instance: ChainInstance) -> bool:
        """Check if citing case has majority opinion text."""
        return (
            instance.citing_case is not None
            and instance.citing_case.majority_opinion is not None
        )

    def _void_s6(self, ctx: ChainContext) -> None:
        """Void S6 result due to S7 citation integrity failure."""
        s6_result = ctx.get("s6")
        if s6_result is None:
            return

        s6_result.score = 0.0
        s6_result.correct = False
        s6_result.voided = True
        s6_result.void_reason = "S7 citation integrity failure"

    def _is_voided(self, ctx: ChainContext) -> bool:
        """Check if chain was voided."""
        s6_result = ctx.get("s6")
        return s6_result is not None and s6_result.voided

    def _get_void_reason(self, ctx: ChainContext) -> str | None:
        """Get void reason if chain was voided."""
        s6_result = ctx.get("s6")
        if s6_result is not None and s6_result.voided:
            return s6_result.void_reason
        return None
```

---

## 7. Metrics

### 7.1 Per-Step Metrics

| Metric | Definition | Denominator |
|--------|------------|-------------|
| Accuracy | `count(correct=True) / count(status="OK")` | Executed steps only |
| Mean Score | `mean(score)` where `status="OK"` | Executed steps only |
| Coverage Rate | `count(status="OK") / total_instances` | All instances |
| Skip Rate | `count(status="SKIPPED_*") / total_instances` | All instances |

### 7.2 Chain Metrics

| Metric | Definition |
|--------|------------|
| Chain Completion Rate | Instances where all non-skipped steps have `correct=True` / total |
| Mean Failure Position | Mean index of first step with `correct=False` (1-indexed) |
| Void Rate | Instances with `voided=True` / total |

### 7.3 FRD Metrics

| Metric | Definition |
|--------|------------|
| S5:cb Accuracy | Accuracy of S5:cb on `CHAIN_CORE` |
| S5:rag Accuracy | Accuracy of S5:rag on `CHAIN_RAG_SUBSET` |
| Reasoning Bridge Gap | `S5:rag Accuracy - S5:cb Accuracy` on aligned subset |

**Aligned subset:** Instances where both S5:cb and S5:rag have `status="OK"`.

### 7.4 Coverage Reporting

```
S5:rag coverage = count(has_citing_text=True) / count(CHAIN_CORE)
```

This metric is reported separately from accuracy to distinguish data availability from model performance.

---

## 8. Implementation Phases

### Phase 1: Foundation (`core/`)

| Task | File | Deliverable |
|------|------|-------------|
| 1.1 | `core/ids/canonical.py` | ID canonicalization functions |
| 1.2 | `core/normalize/citations.py` | Citation normalization |
| 1.3 | `core/normalize/courts.py` | Court/term normalization |
| 1.4 | `core/schemas/case.py` | `CourtCase`, `ShepardsEdge`, `OverruleRecord` |
| 1.5 | `core/schemas/chain.py` | `ChainInstance`, `ChainContext` |
| 1.6 | `core/schemas/results.py` | `StepResult`, `ChainResult` |
| 1.7 | `core/schemas/ground_truth.py` | `S4GroundTruth` |

**Tests:** `test_ids.py`, `test_normalize.py`, `test_schemas.py`

### Phase 2: Data Pipeline (`chain/datasets/`)

| Task | File | Deliverable |
|------|------|-------------|
| 2.1 | `chain/datasets/loaders.py` | HuggingFace dataset loaders |
| 2.2 | `chain/datasets/builder.py` | Index building, joins, coverage flags |
| 2.3 | `scripts/build_dataset.py` | CLI to build chain instances |
| 2.4 | `scripts/validate_joins.py` | CLI to validate join coverage |

**Tests:** `test_loaders.py`, `test_builder.py`

### Phase 3: Step Infrastructure (`chain/steps/`, `chain/backends/`)

| Task | File | Deliverable |
|------|------|-------------|
| 3.1 | `chain/steps/base.py` | `Step` ABC |
| 3.2 | `chain/backends/base.py` | `Backend` ABC |
| 3.3 | `chain/backends/dahl_backend.py` | `DahlBackend` |
| 3.4 | `chain/backends/mock_backend.py` | `MockBackend` |
| 3.5 | `chain/runner/executor.py` | `ChainExecutor` skeleton |

**Tests:** `test_backends.py`, `test_executor.py`

### Phase 4: Deterministic Spine (S1, S7)

| Task | File | Deliverable |
|------|------|-------------|
| 4.1 | `chain/steps/s1_known_authority.py` | S1 implementation |
| 4.2 | `chain/steps/s7_citation_integrity.py` | S7 implementation |
| 4.3 | `core/scoring/citation_verify.py` | Citation verification scorer |

**Tests:** `test_s1.py`, `test_s7.py`

### Phase 5: Runner Integration

| Task | File | Deliverable |
|------|------|-------------|
| 5.1 | `chain/runner/executor.py` | Complete `ChainExecutor` |
| 5.2 | `core/reporting/jsonl.py` | JSONL output emitter |
| 5.3 | `scripts/run_chain.py` | CLI to run chains |

**Tests:** `test_runner.py`

### Phase 6: Signal Steps (S4, S5)

| Task | File | Deliverable |
|------|------|-------------|
| 6.1 | `chain/steps/s4_fact_extraction.py` | S4 implementation |
| 6.2 | `chain/steps/s5_distinguish.py` | `S5DistinguishCB`, `S5DistinguishRAG` |
| 6.3 | `core/scoring/exact_match.py` | Exact match scorer |

**Tests:** `test_s4.py`, `test_s5.py`

### Phase 7: Remaining Steps (S2, S3)

| Task | File | Deliverable |
|------|------|-------------|
| 7.1 | `chain/steps/s2_unknown_authority.py` | S2 implementation |
| 7.2 | `chain/steps/s3_validate_authority.py` | S3 implementation |

**Tests:** `test_s2.py`, `test_s3.py`

### Phase 8: IRAC Synthesis (S6)

| Task | File | Deliverable |
|------|------|-------------|
| 8.1 | `chain/steps/s6_irac_synthesis.py` | S6 implementation |
| 8.2 | `core/scoring/irac_rubric.py` | MEE-style rubric scorer |

**Tests:** `test_s6.py`

### Phase 9: Metrics & Reporting

| Task | File | Deliverable |
|------|------|-------------|
| 9.1 | `core/reporting/metrics.py` | Chain metrics aggregator |
| 9.2 | `scripts/summarize_run.py` | CLI to compute and display metrics |

**Tests:** `test_metrics.py`

---

## 9. Skill-to-Data Mapping

| Skill | Ground Truth Source | Key Fields | Scoring Method |
|-------|---------------------|------------|----------------|
| S1 | `scdb_sample` | `usCite`, `caseName`, `term` | Exact match |
| S2 | `scotus_shepards_sample` | `citing_case_us_cite` | Ranked list inclusion |
| S3 | `scotus_overruled_db` | `year_overruled`, `overruled_in_full` | Exact match |
| S4 | `scdb_sample` | `caseDisposition`, `partyWinning` | `S4GroundTruth` match |
| S5 | `scotus_shepards_sample` | `agree` | Binary match |
| S6 | Chain outputs | Rubric criteria | Hybrid (deterministic + LLM judge) |
| S7 | `fake_cases` + `scdb_sample` | Citation existence | Deterministic lookup |

---

## 10. Success Criteria

### Pilot Run (5-10 instances)

- [ ] Chain instances build correctly from joins
- [ ] S1→S7 executes end-to-end without crashes
- [ ] JSONL output contains all `StepResult` fields
- [ ] S5:rag correctly skipped when `citing_case.majority_opinion` is `None`
- [ ] S7 gate correctly voids S6 on fabrication detection
- [ ] `MockBackend` produces deterministic test results

### Full Run (CHAIN_CORE dataset)

- [ ] Per-step accuracy computed and reported
- [ ] Chain completion rate computed
- [ ] Mean failure position tracked
- [ ] Void rate reported
- [ ] S5:rag coverage rate reported separately from accuracy
- [ ] FRD gap computed on aligned subset
- [ ] Results reproducible with fixed seed

### Publication Ready

- [ ] All metrics documented with definitions
- [ ] Comparison to CaseHOLD baseline (S5:cb vs CaseHOLD accuracy)
- [ ] HuggingFace dataset released with chain instances
- [ ] Reproducibility instructions in documentation

---

## Appendix A: Resolved Design Issues

| # | Issue | Resolution |
|---|-------|------------|
| 1 | `StepResult` missing `voided`, `void_reason` | Added to `StepResult` (§3.6) |
| 2 | S5 variant key collision in dict | Use `step_id` as key: `"s5:cb"`, `"s5:rag"` (§4.2) |
| 3 | S5:rag data requirement not in Step ABC | Executor handles coverage check (§6.1) |
| 4 | ~~S6 soft vs hard dependencies~~ | ~~S6 runs if required steps executed, regardless of success (§4.5)~~ |
| 4 | S6 dependency semantics (v2.1) | `requires()` returns `step_id`; only `status="OK"` satisfies; S6 requires `"s5:cb"` explicitly (§4.3, §4.5) |
| 5 | `ChainResult` undefined | Added `ChainResult` dataclass (§3.7) |
| 6 | S4 ground truth unclear | Added `S4GroundTruth` with disposition, party_winning, issue_area (§3.8) |
| 7 | No mock backend for tests | Added `MockBackend` (§5.3) |
| 8 | `StepStatus` enum missing | Using string status with documented values (§3.6) |
| 9 | Skipped steps satisfying dependencies (v2.1) | Only `status="OK"` results satisfy dependencies (§6.1) |

---

## Appendix B: File Checksums (HuggingFace)

For reproducibility verification:

| File | Size | Path |
|------|------|------|
| `scdb_sample.csv` | 94.6 MB | `samples/scdb_sample.csv` |
| `scotus_shepards_sample.csv` | 1.32 MB | `samples/scotus_shepards_sample.csv` |
| `scotus_overruled_db.csv` | 36.7 kB | `samples/scotus_overruled_db.csv` |
| `fake_cases.csv` | 78.6 kB | `samples/fake_cases.csv` |
| `fowler_scores.csv` | 1.76 MB | `sources/fowler_scores.csv` |

**Dataset:** `reglab/legal_hallucinations_paper_data`

---

## Appendix C: Prompt Contract Summary

See `PROMPT_CONTRACT.md` for full details. Key decisions:

| Issue | Resolution |
|-------|------------|
| Model output authority | Model emits `payload` only; executor sets `status` |
| S5 field naming | `agrees` (not `distinguished`) to match `edge.agree` |
| S4 disposition | Closed enum, exact string match required |
| S2 scoring | `score=MRR`, `correct=hit@10`, full metrics in `parsed` |
| S6 voiding | `status="OK"` + `voided=True` flag (not status override) |
| S5:cb input | Metadata + S4 only; no citing opinion text required |
