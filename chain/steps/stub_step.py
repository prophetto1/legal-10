"""Stub step for testing executor logic.

From MVP_BUILD_ORDER.md Phase 2.
"""

from typing import Any

from chain.steps.base import Step
from core.schemas.chain import ChainContext


class StubStep(Step):
    """Configurable stub step for testing executor logic.

    This step allows complete control over behavior for testing:
    - Set dependencies via requires parameter
    - Control correctness via always_correct parameter
    - Set custom score via score_value parameter
    - Control coverage check via require_citing_text parameter

    Example:
        # Step that always passes, no dependencies
        s1 = StubStep(name="s1", requires=set(), always_correct=True)

        # Step that depends on s1 and s4, always fails
        s5 = StubStep(
            name="s5",
            variant="cb",
            requires={"s1", "s4"},
            always_correct=False,
        )

        # Step that requires citing text (Tier B)
        s6 = StubStep(
            name="s6",
            requires={"s5:cb"},
            require_citing_text=True,
        )
    """

    def __init__(
        self,
        name: str,
        requires: set[str] | None = None,
        always_correct: bool = True,
        score_value: float = 1.0,
        variant: str | None = None,
        require_citing_text: bool = False,
        parsed_response: dict[str, Any] | None = None,
        ground_truth_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize stub step.

        Args:
            name: Logical step name (e.g., "s1", "s5")
            requires: Set of step_ids that must be OK before this runs
            always_correct: If True, score() returns correct=True
            score_value: Score to return (0.0-1.0)
            variant: Optional variant (e.g., "cb", "rag")
            require_citing_text: If True, check_coverage requires citing text
            parsed_response: Custom parsed response dict
            ground_truth_data: Custom ground truth dict
        """
        self._name = name
        self._variant = variant
        self._requires = requires or set()
        self._always_correct = always_correct
        self._score_value = score_value
        self._require_citing_text = require_citing_text
        self._parsed_response = parsed_response or {}
        self._ground_truth_data = ground_truth_data or {}

    @property
    def step_id(self) -> str:
        """Return step_id including variant if present."""
        if self._variant:
            return f"{self._name}:{self._variant}"
        return self._name

    @property
    def step_name(self) -> str:
        """Return logical step name."""
        return self._name

    def requires(self) -> set[str]:
        """Return configured dependencies."""
        return self._requires.copy()

    def check_coverage(self, ctx: ChainContext) -> bool:
        """Check coverage based on require_citing_text setting.

        Args:
            ctx: Chain context

        Returns:
            True if coverage met, False if citing text required but missing
        """
        if self._require_citing_text:
            return ctx.instance.has_citing_text
        return True

    def prompt(self, ctx: ChainContext) -> str:
        """Return stub prompt."""
        return f"[STUB PROMPT for {self.step_id}]"

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Return configured parsed response."""
        return self._parsed_response.copy()

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Return configured ground truth."""
        return self._ground_truth_data.copy()

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Return configured score and correctness."""
        return (self._score_value, self._always_correct)