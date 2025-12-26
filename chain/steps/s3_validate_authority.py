"""S3: Validate Authority step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 6 and PROMPT_CONTRACT.md.

S3 checks if the cited case has been overruled.
Ground truth comes from scotus_overruled_db.
"""

import json
from typing import Any

from chain.steps.base import Step
from core.schemas.chain import ChainContext

# Prompt template for S3
S3_PROMPT_TEMPLATE = """You are a legal research assistant. Determine if the following Supreme Court case has been overruled.

CASE:
- Citation: {us_cite}
- Name: {case_name}
- Term: {term}

Has this case been overruled by a later Supreme Court decision?

Return a JSON object with:
- "is_overruled": true if the case has been overruled, false otherwise
- "overruling_case": The name of the overruling case (null if not overruled)
- "year_overruled": The year it was overruled (null if not overruled)

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""


class S3ValidateAuthority(Step):
    """S3: Validate Authority - check if case overruled.

    Input: cited_case metadata
    Output: {is_overruled, overruling_case, year_overruled}
    Scoring: is_overruled must match ground truth
    """

    @property
    def step_id(self) -> str:
        return "s3"

    @property
    def step_name(self) -> str:
        return "s3"

    def requires(self) -> set[str]:
        """S3 requires S1 (known authority identification)."""
        return {"s1"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S3 requires cited_case text (Tier A)."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S3 prompt."""
        cited = ctx.instance.cited_case

        return S3_PROMPT_TEMPLATE.format(
            us_cite=cited.us_cite,
            case_name=cited.case_name,
            term=cited.term,
        )

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S3 response.

        Expected format:
        {
            "is_overruled": true,
            "overruling_case": "West Coast Hotel Co. v. Parrish",
            "year_overruled": 1937
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

            is_overruled = data.get("is_overruled", False)
            overruling_case = data.get("overruling_case")
            year_overruled = data.get("year_overruled")

            # Normalize is_overruled to bool
            if isinstance(is_overruled, str):
                is_overruled = is_overruled.lower() in ("true", "yes", "1")
            else:
                is_overruled = bool(is_overruled)

            # Normalize year to int or None
            if year_overruled is not None:
                try:
                    year_overruled = int(year_overruled)
                except (ValueError, TypeError):
                    year_overruled = None

            return {
                "is_overruled": is_overruled,
                "overruling_case": str(overruling_case) if overruling_case else None,
                "year_overruled": year_overruled,
            }

        except json.JSONDecodeError as e:
            return {"errors": [f"JSON parse error: {e}"]}

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Get ground truth from overrule record."""
        overrule = ctx.instance.overrule

        if overrule is None:
            return {
                "is_overruled": False,
                "overruling_case": None,
                "year_overruled": None,
            }

        return {
            "is_overruled": True,
            "overruling_case": overrule.overruling_case_name,
            "year_overruled": overrule.year_overruled,
        }

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S3 output.

        Scoring:
        - is_overruled must match exactly for correct=True
        - Bonus partial credit for matching year/case name (future)

        Returns:
            (score, correct) where score is 0.0 or 1.0
        """
        if "errors" in parsed:
            return (0.0, False)

        pred_overruled = parsed.get("is_overruled", False)
        true_overruled = ground_truth.get("is_overruled", False)

        if pred_overruled == true_overruled:
            return (1.0, True)
        else:
            return (0.0, False)
