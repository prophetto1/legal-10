"""Chain-related schemas for L10 Agentic Chain.

From L10_AGENTIC_SPEC.md §3.4-3.5.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.schemas.case import CourtCase, OverruleRecord, ShepardsEdge

if TYPE_CHECKING:
    from core.schemas.results import StepResult


@dataclass(frozen=True)
class ChainInstance:
    """One instance in the chain evaluation.

    Corresponds to one Shepard's edge (cited_case -> citing_case relationship).

    Attributes:
        id: Canonical pair ID (e.g., "pair::347_us_483::349_us_294")
        cited_case: The earlier case being cited (always present, Tier A)
        citing_case: The later case doing the citing (may be None, Tier B)
        edge: Shepard's relationship data including agree field
        overrule: Overruling record if cited_case was overruled (None otherwise)
    """

    id: str
    cited_case: CourtCase
    edge: ShepardsEdge
    citing_case: CourtCase | None = None
    overrule: OverruleRecord | None = None

    @property
    def has_cited_text(self) -> bool:
        """Check if cited case has majority opinion text (Tier A)."""
        return self.cited_case.majority_opinion is not None

    @property
    def has_citing_text(self) -> bool:
        """Check if citing case has majority opinion text (Tier B)."""
        return (
            self.citing_case is not None
            and self.citing_case.majority_opinion is not None
        )


@dataclass
class ChainContext:
    """Mutable state carrier passed through S1->S7.

    Attributes:
        instance: The ChainInstance being processed
        step_results: Results keyed by step_id (e.g., "s1", "s5:cb")
    """

    instance: ChainInstance
    step_results: dict[str, "StepResult"] = field(default_factory=dict)

    def get(self, step_id: str) -> "StepResult | None":
        """Get result by step_id.

        Args:
            step_id: Step identifier (e.g., "s4", "s5:cb")

        Returns:
            StepResult if found, None otherwise
        """
        return self.step_results.get(step_id)

    def set(self, step_id: str, result: "StepResult") -> None:
        """Store result by step_id.

        Args:
            step_id: Step identifier
            result: StepResult to store
        """
        self.step_results[step_id] = result

    def has_step(self, step_name: str) -> bool:
        """Check if any variant of a logical step has run.

        Args:
            step_name: Logical step name (e.g., "s5")

        Returns:
            True if any variant of the step exists in results
        """
        return any(sr.step == step_name for sr in self.step_results.values())

    def get_by_step(self, step_name: str) -> "StepResult | None":
        """Get first result matching logical step name.

        Args:
            step_name: Logical step name (e.g., "s5")

        Returns:
            First matching StepResult, or None
        """
        for sr in self.step_results.values():
            if sr.step == step_name:
                return sr
        return None

    def get_ok_step_ids(self) -> set[str]:
        """Get set of step_ids with status='OK'.

        Used for dependency resolution in executor.

        Returns:
            Set of step_ids that executed successfully
        """
        from core.schemas.results import STATUS_OK

        return {
            step_id
            for step_id, sr in self.step_results.items()
            if sr.status == STATUS_OK
        }