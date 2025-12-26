"""Step ABC for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 2 and PROMPT_CONTRACT.md.
"""

from abc import ABC, abstractmethod
from typing import Any

from core.schemas.chain import ChainContext
from core.schemas.results import StepResult


class Step(ABC):
    """Abstract base class for chain steps.

    Each step in the chain (S1-S7) implements this interface.
    The executor calls these methods in order to:
    1. Check dependencies via requires()
    2. Check coverage requirements via check_coverage()
    3. Build the prompt via prompt()
    4. Parse the LLM response via parse()
    5. Get ground truth via ground_truth()
    6. Score the result via score()

    Key Design Points (from PROMPT_CONTRACT.md):
    - Executor owns status, never the model
    - Model emits payload only (via parsed dict)
    - Step returns StepResult with status=OK; executor may override
    """

    @property
    @abstractmethod
    def step_id(self) -> str:
        """Return the unique step identifier.

        Returns:
            Step ID (e.g., "s1", "s5:cb", "s5:rag")
        """
        pass

    @property
    @abstractmethod
    def step_name(self) -> str:
        """Return the logical step name.

        Returns:
            Step name (e.g., "s1", "s5" for both s5:cb and s5:rag)
        """
        pass

    @abstractmethod
    def requires(self) -> set[str]:
        """Return set of step_ids that must be OK before this step runs.

        Returns:
            Set of required step_ids (e.g., {"s1", "s4"})
        """
        pass

    def check_coverage(self, ctx: ChainContext) -> bool:
        """Check if this step has required coverage.

        Override this method to implement tier-based coverage checks.
        Default implementation returns True (no coverage requirements).

        Args:
            ctx: Chain context with instance data

        Returns:
            True if coverage requirements met, False otherwise
        """
        return True

    @abstractmethod
    def prompt(self, ctx: ChainContext) -> str:
        """Build the prompt for this step.

        Args:
            ctx: Chain context with instance and prior results

        Returns:
            Prompt string to send to LLM
        """
        pass

    @abstractmethod
    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse LLM response into structured payload.

        Args:
            raw_response: Raw text from LLM

        Returns:
            Parsed payload dict (step-specific structure)

        Note:
            Parse failures should return {"errors": [...]} per PROMPT_CONTRACT.md
        """
        pass

    @abstractmethod
    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Extract ground truth for this step from context.

        Args:
            ctx: Chain context with instance data

        Returns:
            Ground truth dict for scoring
        """
        pass

    @abstractmethod
    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score the parsed response against ground truth.

        Args:
            parsed: Parsed payload from parse()
            ground_truth: Ground truth from ground_truth()

        Returns:
            Tuple of (score: float 0.0-1.0, correct: bool)
        """
        pass

    def create_result(
        self,
        prompt: str,
        raw_response: str,
        parsed: dict[str, Any],
        ground_truth: dict[str, Any],
        score: float,
        correct: bool,
        model: str,
    ) -> StepResult:
        """Create a StepResult with all fields populated.

        Args:
            prompt: The prompt sent to LLM
            raw_response: Raw LLM response
            parsed: Parsed payload
            ground_truth: Ground truth used for scoring
            score: Computed score
            correct: Binary correctness
            model: Model identifier

        Returns:
            StepResult with status=OK (executor may override)
        """
        return StepResult(
            step_id=self.step_id,
            step=self.step_name,
            variant=self._extract_variant(),
            prompt=prompt,
            raw_response=raw_response,
            parsed=parsed,
            ground_truth=ground_truth,
            score=score,
            correct=correct,
            model=model,
            model_errors=parsed.get("errors", []),
        )

    def _extract_variant(self) -> str | None:
        """Extract variant from step_id if present.

        Returns:
            Variant string (e.g., "cb", "rag") or None
        """
        if ":" in self.step_id:
            return self.step_id.split(":", 1)[1]
        return None
