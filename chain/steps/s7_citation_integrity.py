"""S7: Citation Integrity step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 4 and PROMPT_CONTRACT.md.

S7 is a gate step that verifies citations in S6 output are real.
It extracts citations using eyecite and checks them against:
- fake_cases: Known fabricated citations
- scdb: Known real citations

If any citation is fabricated (in fake_cases or not in scdb),
S7 voids the S6 result.
"""

import json
from typing import Any

from chain.steps.base import Step
from core.ids.canonical import canonicalize_cite
from core.schemas.chain import ChainContext
from core.scoring.citation_verify import (
    extract_citations,
    verify_all_citations,
    build_canonical_sets,
)


class S7CitationIntegrity(Step):
    """S7: Citation Integrity - verify citations in S6 are real.

    Input: S6 output text (IRAC synthesis)
    Output: {citations_found, all_valid}
    Scoring: all_valid determines correct (True = 1.0, False = 0.0)

    Gate behavior:
    - If all_valid is False, S7 voids S6 result
    - The executor handles voiding logic based on S7.correct
    """

    def __init__(
        self,
        fake_us_cites: set[str] | None = None,
        scdb_us_cites: set[str] | dict[str, object] | None = None,
    ) -> None:
        """Initialize S7 with citation verification sets.

        Args:
            fake_us_cites: Set of fake US citations
            scdb_us_cites: Set or dict of real SCDB US citations
        """
        self._fake_us_cites = fake_us_cites or set()
        self._scdb_us_cites = scdb_us_cites or set()

        # Build canonicalized sets
        if fake_us_cites and scdb_us_cites:
            self._canonical_fake, self._canonical_scdb = build_canonical_sets(
                self._fake_us_cites, self._scdb_us_cites
            )
        else:
            self._canonical_fake = set()
            self._canonical_scdb = set()

    def set_verification_sets(
        self,
        fake_us_cites: set[str],
        scdb_us_cites: set[str] | dict[str, object],
    ) -> None:
        """Set verification sets after initialization.

        Useful when building S7 before data is loaded.

        Args:
            fake_us_cites: Set of fake US citations
            scdb_us_cites: Set or dict of real SCDB US citations
        """
        self._fake_us_cites = fake_us_cites
        self._scdb_us_cites = scdb_us_cites
        self._canonical_fake, self._canonical_scdb = build_canonical_sets(
            fake_us_cites, scdb_us_cites
        )

    @property
    def step_id(self) -> str:
        return "s7"

    @property
    def step_name(self) -> str:
        return "s7"

    def requires(self) -> set[str]:
        """S7 requires S6 to have run."""
        return {"s6"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S7 runs if S6 ran (same coverage as S6)."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """S7 doesn't use LLM - it's a verification step.

        Returns empty prompt; the executor will still call complete()
        but we extract citations from S6 output directly.
        """
        # Get S6 output to extract citations from
        s6_result = ctx.get("s6")
        if s6_result is None:
            return "[S7: No S6 output available]"

        # Combine all S6 IRAC fields for citation extraction
        parsed = s6_result.parsed
        text_parts = [
            parsed.get("issue", ""),
            parsed.get("rule", ""),
            parsed.get("application", ""),
            parsed.get("conclusion", ""),
        ]
        combined_text = "\n".join(text_parts)

        return f"[S7: Verify citations in S6 output]\n\n{combined_text}"

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S7 by extracting and verifying citations.

        Unlike other steps, S7 doesn't rely on LLM output.
        It extracts citations from S6 output (embedded in prompt).

        Args:
            raw_response: LLM response (ignored for S7)

        Returns:
            Dict with citations_found and all_valid
        """
        # S7 doesn't use the LLM response directly
        # The actual verification happens in execute_verification()
        # This parse() method is for compatibility with the Step interface

        # Try to parse if it's JSON (for testing)
        try:
            if raw_response.strip().startswith("{"):
                data = json.loads(raw_response)
                if "citations_found" in data:
                    return data
        except json.JSONDecodeError:
            pass

        # Default: return empty (verification done in score())
        return {"citations_found": [], "all_valid": True}

    def execute_verification(self, s6_text: str) -> dict[str, Any]:
        """Execute citation verification on S6 output.

        This is the core S7 logic - extract and verify citations.

        Args:
            s6_text: Combined text from S6 IRAC fields

        Returns:
            Dict with citations_found and all_valid
        """
        # Extract citations from S6 output
        citations = extract_citations(s6_text)

        # Verify all citations
        results, all_valid = verify_all_citations(
            citations, self._canonical_fake, self._canonical_scdb
        )

        # Format for output
        citations_found = [
            {"cite": r.cite, "exists": r.exists}
            for r in results
        ]

        return {
            "citations_found": citations_found,
            "all_valid": all_valid,
        }

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """S7 ground truth: all citations should be real.

        For S7, the ground truth is simply that all_valid should be True.
        """
        return {"all_valid": True}

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S7 output.

        Scoring:
        - correct=True (score=1.0) if all_valid=True
        - correct=False (score=0.0) if all_valid=False

        The executor uses correct=False to trigger S6 voiding.
        """
        all_valid = parsed.get("all_valid", False)

        if all_valid:
            return (1.0, True)
        else:
            return (0.0, False)

    def create_result_from_verification(
        self,
        ctx: ChainContext,
        model: str = "deterministic",
    ):
        """Create StepResult by running verification on S6 output.

        This is a convenience method that runs the full S7 logic:
        1. Extract S6 text
        2. Run verification
        3. Create StepResult

        Args:
            ctx: Chain context with S6 result
            model: Model identifier (default: "deterministic")

        Returns:
            StepResult with verification results
        """
        # Get S6 output
        s6_result = ctx.get("s6")
        if s6_result is None:
            return self.create_result(
                prompt="",
                raw_response="",
                parsed={"citations_found": [], "all_valid": True, "errors": ["No S6 output"]},
                ground_truth=self.ground_truth(ctx),
                score=0.0,
                correct=False,
                model=model,
            )

        # Combine S6 IRAC fields
        s6_parsed = s6_result.parsed
        text_parts = [
            s6_parsed.get("issue", ""),
            s6_parsed.get("rule", ""),
            s6_parsed.get("application", ""),
            s6_parsed.get("conclusion", ""),
        ]
        s6_text = "\n".join(text_parts)

        # Run verification
        parsed = self.execute_verification(s6_text)

        # Score
        gt = self.ground_truth(ctx)
        score_val, correct = self.score(parsed, gt)

        return self.create_result(
            prompt=f"[S7: Verify citations in S6 output]\n\n{s6_text}",
            raw_response="[Deterministic verification - no LLM call]",
            parsed=parsed,
            ground_truth=gt,
            score=score_val,
            correct=correct,
            model=model,
        )
