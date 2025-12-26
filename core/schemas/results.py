"""Result schemas for L10 Agentic Chain.

From L10_AGENTIC_SPEC.md §3.6-3.7 and PROMPT_CONTRACT.md.
"""

from dataclasses import dataclass, field
from typing import Any

# Valid status values (from spec §3.6)
STATUS_OK = "OK"
STATUS_SKIPPED_COVERAGE = "SKIPPED_COVERAGE"
STATUS_SKIPPED_DEPENDENCY = "SKIPPED_DEPENDENCY"

VALID_STATUSES = frozenset({STATUS_OK, STATUS_SKIPPED_COVERAGE, STATUS_SKIPPED_DEPENDENCY})


@dataclass
class StepResult:
    """Result of executing a single step in the chain.

    Attributes:
        step_id: Unique key (e.g., "s1", "s5:cb", "s5:rag")
        step: Logical step name (e.g., "s1", "s2", ..., "s7")
        variant: Step variant ("cb", "rag", or None)
        status: Execution status (OK, SKIPPED_COVERAGE, SKIPPED_DEPENDENCY)
        prompt: Prompt sent to LLM
        raw_response: Raw LLM response text
        parsed: Structured parse of response (model's payload)
        ground_truth: Expected values for scoring
        score: Score between 0.0 and 1.0
        correct: Binary correctness
        voided: True if S7 gate voided this result (S6 only)
        void_reason: Reason for voiding
        model: Model identifier
        timestamp: Unix timestamp of execution
        latency_ms: Response latency in milliseconds
        tokens_in: Input token count
        tokens_out: Output token count
        model_errors: Model's self-reported errors (informational only)
    """

    # Identity
    step_id: str
    step: str
    variant: str | None = None

    # Execution status (set by executor, never by model)
    status: str = STATUS_OK

    # Raw I/O
    prompt: str = ""
    raw_response: str = ""

    # Parsed output (model's payload)
    parsed: dict[str, Any] = field(default_factory=dict)

    # Ground truth and scoring
    ground_truth: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    correct: bool = False

    # Voiding (S6 only, triggered by S7 gate)
    voided: bool = False
    void_reason: str | None = None

    # Provenance
    model: str = ""
    timestamp: float = 0.0
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    # Model's self-reported errors (from PROMPT_CONTRACT.md §1)
    model_errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate status is one of the allowed values."""
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of: {VALID_STATUSES}"
            )


@dataclass
class ChainResult:
    """Result of executing a complete chain on one instance.

    Attributes:
        instance_id: ChainInstance.id
        step_results: Results keyed by step_id
        voided: True if S7 gate triggered
        void_reason: Reason if voided
    """

    instance_id: str
    step_results: dict[str, StepResult] = field(default_factory=dict)
    voided: bool = False
    void_reason: str | None = None
