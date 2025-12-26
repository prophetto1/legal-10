"""S4: Fact Extraction step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 5 and PROMPT_CONTRACT.md.

S4 extracts key facts from the cited case opinion:
- disposition: closed enum (11 values)
- party_winning: closed enum (3 values)
- holding_summary: free text summary
"""

import json
from typing import Any

from chain.steps.base import Step
from core.schemas.chain import ChainContext
from core.schemas.ground_truth import (
    DISPOSITION_CODES,
    PARTY_WINNING_CODES,
    disposition_code_to_text,
    party_winning_code_to_text,
)

# Valid disposition values (from PROMPT_CONTRACT.md §3)
VALID_DISPOSITIONS = frozenset(DISPOSITION_CODES.values())

# Valid party_winning values
VALID_PARTY_WINNING = frozenset(PARTY_WINNING_CODES.values())

# Prompt template for S4
S4_PROMPT_TEMPLATE = """You are a legal research assistant. Read the following Supreme Court opinion and extract:

1. The disposition of the case (how the Court ruled)
2. Which party won (petitioner, respondent, or unclear)
3. A brief summary of the holding

OPINION:
{opinion_text}

DISPOSITION must be exactly one of these values:
- "stay granted"
- "affirmed"
- "reversed"
- "reversed and remanded"
- "vacated and remanded"
- "affirmed and reversed in part"
- "affirmed and vacated in part"
- "affirmed and reversed in part and remanded"
- "vacated"
- "petition denied"
- "certification"

PARTY_WINNING must be exactly one of:
- "petitioner"
- "respondent"
- "unclear"

Return a JSON object with these fields:
- "disposition": The disposition (from the list above)
- "party_winning": Which party won (from the list above)
- "holding_summary": A 1-2 sentence summary of the holding

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""


class S4FactExtraction(Step):
    """S4: Fact Extraction - extract disposition, party_winning, holding.

    Input: cited_case.majority_opinion
    Output: {disposition, party_winning, holding_summary}
    Scoring: Exact string match for disposition and party_winning
    """

    @property
    def step_id(self) -> str:
        return "s4"

    @property
    def step_name(self) -> str:
        return "s4"

    def requires(self) -> set[str]:
        """S4 requires S1 (known authority identification)."""
        return {"s1"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S4 requires cited_case text (Tier A)."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S4 prompt with opinion text."""
        opinion = ctx.instance.cited_case.majority_opinion or ""
        # Truncate very long opinions
        max_chars = 50000
        if len(opinion) > max_chars:
            opinion = opinion[:max_chars] + "\n\n[TRUNCATED]"

        return S4_PROMPT_TEMPLATE.format(opinion_text=opinion)

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S4 response into structured payload.

        Expected format:
        {
            "disposition": "reversed and remanded",
            "party_winning": "petitioner",
            "holding_summary": "The Court held that..."
        }
        """
        try:
            response = raw_response.strip()

            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
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

            if not isinstance(data, dict):
                return {"errors": ["Response is not a JSON object"]}

            disposition = data.get("disposition", "")
            party_winning = data.get("party_winning", "")
            holding_summary = data.get("holding_summary", "")

            # Normalize to lowercase for comparison
            if isinstance(disposition, str):
                disposition = disposition.lower().strip()
            if isinstance(party_winning, str):
                party_winning = party_winning.lower().strip()

            return {
                "disposition": disposition,
                "party_winning": party_winning,
                "holding_summary": str(holding_summary) if holding_summary else "",
            }

        except json.JSONDecodeError as e:
            return {"errors": [f"JSON parse error: {e}"]}

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Get ground truth from cited_case SCDB metadata."""
        cited = ctx.instance.cited_case

        # Convert SCDB codes to text
        disposition = disposition_code_to_text(cited.case_disposition)
        party_winning = party_winning_code_to_text(cited.party_winning)

        return {
            "disposition": disposition,
            "party_winning": party_winning,
            "disposition_code": cited.case_disposition,
            "party_winning_code": cited.party_winning,
        }

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S4 output against ground truth.

        Scoring (from PROMPT_CONTRACT.md):
        - disposition: Exact string match (closed enum)
        - party_winning: Exact string match (closed enum)
        - Both must match for correct=True

        Returns:
            (score, correct) where score is 0.0, 0.5, or 1.0
        """
        if "errors" in parsed:
            return (0.0, False)

        pred_disposition = parsed.get("disposition", "")
        pred_party = parsed.get("party_winning", "")

        true_disposition = ground_truth.get("disposition", "")
        true_party = ground_truth.get("party_winning", "")

        # Handle None ground truth (missing SCDB data)
        if true_disposition is None:
            true_disposition = ""
        if true_party is None:
            true_party = ""

        # Exact string match (case-insensitive, already lowercased in parse)
        disposition_match = pred_disposition == true_disposition.lower()
        party_match = pred_party == true_party.lower()

        if disposition_match and party_match:
            return (1.0, True)
        elif disposition_match or party_match:
            return (0.5, False)
        else:
            return (0.0, False)
