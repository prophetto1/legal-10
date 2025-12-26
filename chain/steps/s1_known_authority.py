"""S1: Known Authority step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 4 and PROMPT_CONTRACT.md.

S1 asks the model to identify the anchor case (cited_case) from
its majority opinion. This is a deterministic baseline - the model
should be able to extract the citation, name, and term from the text.
"""

import json
import re
from typing import Any

from chain.steps.base import Step
from core.ids.canonical import canonicalize_cite
from core.schemas.chain import ChainContext

# Prompt template for S1
S1_PROMPT_TEMPLATE = """You are a legal research assistant. Read the following Supreme Court opinion and extract:
1. The U.S. Reports citation (e.g., "347 U.S. 483")
2. The case name (e.g., "Brown v. Board of Education")
3. The term (year the case was decided)

OPINION:
{opinion_text}

Return a single JSON object with these fields:
- "us_cite": The U.S. Reports citation
- "case_name": The case name
- "term": The term year (integer)

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""


class S1KnownAuthority(Step):
    """S1: Known Authority - extract anchor case metadata from opinion.

    Input: cited_case.majority_opinion
    Output: {us_cite, case_name, term}
    Scoring: canonicalized citation match + term match
    """

    @property
    def step_id(self) -> str:
        return "s1"

    @property
    def step_name(self) -> str:
        return "s1"

    def requires(self) -> set[str]:
        """S1 has no dependencies - it's the first step."""
        return set()

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S1 requires cited_case text (Tier A)."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S1 prompt with opinion text."""
        opinion = ctx.instance.cited_case.majority_opinion or ""
        # Truncate very long opinions to avoid token limits
        max_chars = 50000
        if len(opinion) > max_chars:
            opinion = opinion[:max_chars] + "\n\n[TRUNCATED]"

        return S1_PROMPT_TEMPLATE.format(opinion_text=opinion)

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S1 response into structured payload.

        Expected format:
        {
            "us_cite": "347 U.S. 483",
            "case_name": "Brown v. Board of Education",
            "term": 1954
        }
        """
        try:
            # Try to extract JSON from response
            response = raw_response.strip()

            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                # Skip first and last lines (``` markers)
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                response = "\n".join(json_lines)

            data = json.loads(response)

            # Validate required fields
            if not isinstance(data, dict):
                return {"errors": ["Response is not a JSON object"]}

            us_cite = data.get("us_cite", "")
            case_name = data.get("case_name", "")
            term = data.get("term")

            # Normalize term to int
            if term is not None:
                try:
                    term = int(term)
                except (ValueError, TypeError):
                    term = None

            return {
                "us_cite": str(us_cite) if us_cite else "",
                "case_name": str(case_name) if case_name else "",
                "term": term,
            }

        except json.JSONDecodeError as e:
            return {"errors": [f"JSON parse error: {e}"]}

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Get ground truth from cited_case metadata."""
        cited = ctx.instance.cited_case
        return {
            "us_cite": cited.us_cite,
            "case_name": cited.case_name,
            "term": cited.term,
        }

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S1 output against ground truth.

        Scoring:
        - Citation match: Use canonicalize_cite() for tolerance
        - Term match: Exact integer match
        - Case name: Not scored (too fuzzy)

        Returns:
            (score, correct) where score is 0.0-1.0
        """
        if "errors" in parsed:
            return (0.0, False)

        # Canonicalize citations for comparison
        pred_cite = canonicalize_cite(parsed.get("us_cite", ""))
        true_cite = canonicalize_cite(ground_truth.get("us_cite", ""))

        # Check citation match
        cite_match = pred_cite == true_cite and pred_cite != ""

        # Check term match
        pred_term = parsed.get("term")
        true_term = ground_truth.get("term")
        term_match = pred_term == true_term and pred_term is not None

        # Score: both must match for correct
        if cite_match and term_match:
            return (1.0, True)
        elif cite_match or term_match:
            return (0.5, False)
        else:
            return (0.0, False)
