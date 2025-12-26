"""S5: Distinguish step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 5 and PROMPT_CONTRACT.md.

S5 determines whether the citing case agrees with or distinguishes
the cited case. Two variants:
- S5:cb (Backbone): Uses only metadata + S4 facts, no citing opinion
- S5:rag (Enriched): Uses citing opinion text for full analysis

Ground truth: edge.agree (bool)
Output: {agrees: bool, reasoning: str}
"""

import json
from typing import Any

from chain.steps.base import Step
from core.schemas.chain import ChainContext

# Prompt template for S5:cb (backbone - no citing opinion text)
S5_CB_PROMPT_TEMPLATE = """You are a legal research assistant analyzing the relationship between two Supreme Court cases.

CITED CASE (the precedent):
- Citation: {cited_cite}
- Name: {cited_name}
- Term: {cited_term}
- Disposition: {cited_disposition}
- Party Winning: {cited_party_winning}
- Holding: {cited_holding}

CITING CASE (the later case):
- Citation: {citing_cite}
- Name: {citing_name}

Based on the Shepard's signal "{shepards}", determine whether the citing case AGREES with or DISTINGUISHES the cited case.

A case AGREES if it follows, applies, or extends the precedent.
A case DISTINGUISHES if it criticizes, limits, questions, or overrules the precedent.

Return a JSON object with:
- "agrees": true if the citing case agrees with the precedent, false if it distinguishes
- "reasoning": A brief explanation of your determination

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""

# Prompt template for S5:rag (enriched - with citing opinion text)
S5_RAG_PROMPT_TEMPLATE = """You are a legal research assistant analyzing the relationship between two Supreme Court cases.

CITED CASE (the precedent):
- Citation: {cited_cite}
- Name: {cited_name}
- Term: {cited_term}
- Disposition: {cited_disposition}
- Party Winning: {cited_party_winning}
- Holding: {cited_holding}

CITING CASE (the later case):
- Citation: {citing_cite}
- Name: {citing_name}

CITING CASE OPINION (excerpt):
{citing_opinion}

Based on the citing case's treatment of the precedent, determine whether it AGREES with or DISTINGUISHES the cited case.

A case AGREES if it follows, applies, or extends the precedent.
A case DISTINGUISHES if it criticizes, limits, questions, or overrules the precedent.

Return a JSON object with:
- "agrees": true if the citing case agrees with the precedent, false if it distinguishes
- "reasoning": A brief explanation based on the opinion text

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""


class S5DistinguishCB(Step):
    """S5:cb - Distinguish using backbone (metadata + S4 only).

    Input: Case metadata + S4 extracted facts (no citing opinion)
    Output: {agrees, reasoning}
    Scoring: agrees matches edge.agree
    """

    @property
    def step_id(self) -> str:
        return "s5:cb"

    @property
    def step_name(self) -> str:
        return "s5"

    def requires(self) -> set[str]:
        """S5:cb requires S1 and S4."""
        return {"s1", "s4"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S5:cb requires cited_case text (Tier A) - no citing text needed."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S5:cb prompt with metadata only."""
        cited = ctx.instance.cited_case
        edge = ctx.instance.edge

        # Get S4 results for holding/disposition
        s4_result = ctx.get("s4")
        if s4_result and s4_result.parsed:
            disposition = s4_result.parsed.get("disposition", "unknown")
            party_winning = s4_result.parsed.get("party_winning", "unknown")
            holding = s4_result.parsed.get("holding_summary", "")
        else:
            disposition = "unknown"
            party_winning = "unknown"
            holding = ""

        return S5_CB_PROMPT_TEMPLATE.format(
            cited_cite=cited.us_cite,
            cited_name=cited.case_name,
            cited_term=cited.term,
            cited_disposition=disposition,
            cited_party_winning=party_winning,
            cited_holding=holding,
            citing_cite=edge.citing_case_us_cite,
            citing_name=edge.citing_case_name or "Unknown",
            shepards=edge.shepards or "cited",
        )

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S5 response."""
        return _parse_s5_response(raw_response)

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Get ground truth from edge.agree."""
        return {"agrees": ctx.instance.edge.agree}

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S5 output - agrees must match edge.agree."""
        return _score_s5(parsed, ground_truth)


class S5DistinguishRAG(Step):
    """S5:rag - Distinguish using RAG (with citing opinion text).

    Input: Case metadata + S4 facts + citing_case.majority_opinion
    Output: {agrees, reasoning}
    Scoring: agrees matches edge.agree
    """

    @property
    def step_id(self) -> str:
        return "s5:rag"

    @property
    def step_name(self) -> str:
        return "s5"

    def requires(self) -> set[str]:
        """S5:rag requires S1 and S4."""
        return {"s1", "s4"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S5:rag requires BOTH cited and citing text (Tier A + B)."""
        return ctx.instance.has_cited_text and ctx.instance.has_citing_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S5:rag prompt with citing opinion."""
        cited = ctx.instance.cited_case
        citing = ctx.instance.citing_case
        edge = ctx.instance.edge

        # Get S4 results
        s4_result = ctx.get("s4")
        if s4_result and s4_result.parsed:
            disposition = s4_result.parsed.get("disposition", "unknown")
            party_winning = s4_result.parsed.get("party_winning", "unknown")
            holding = s4_result.parsed.get("holding_summary", "")
        else:
            disposition = "unknown"
            party_winning = "unknown"
            holding = ""

        # Get citing opinion (truncate if needed)
        citing_opinion = ""
        if citing and citing.majority_opinion:
            citing_opinion = citing.majority_opinion
            max_chars = 30000
            if len(citing_opinion) > max_chars:
                citing_opinion = citing_opinion[:max_chars] + "\n\n[TRUNCATED]"

        return S5_RAG_PROMPT_TEMPLATE.format(
            cited_cite=cited.us_cite,
            cited_name=cited.case_name,
            cited_term=cited.term,
            cited_disposition=disposition,
            cited_party_winning=party_winning,
            cited_holding=holding,
            citing_cite=edge.citing_case_us_cite,
            citing_name=edge.citing_case_name or (citing.case_name if citing else "Unknown"),
            citing_opinion=citing_opinion,
        )

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S5 response."""
        return _parse_s5_response(raw_response)

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Get ground truth from edge.agree."""
        return {"agrees": ctx.instance.edge.agree}

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S5 output - agrees must match edge.agree."""
        return _score_s5(parsed, ground_truth)


def _parse_s5_response(raw_response: str) -> dict[str, Any]:
    """Parse S5 response (shared by cb and rag).

    Expected format:
    {
        "agrees": true,
        "reasoning": "The citing case follows the precedent because..."
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

        agrees = data.get("agrees")
        reasoning = data.get("reasoning", "")

        # Normalize agrees to bool
        if isinstance(agrees, str):
            agrees = agrees.lower() in ("true", "yes", "1")
        elif agrees is None:
            agrees = False
        else:
            agrees = bool(agrees)

        return {
            "agrees": agrees,
            "reasoning": str(reasoning) if reasoning else "",
        }

    except json.JSONDecodeError as e:
        return {"errors": [f"JSON parse error: {e}"]}


def _score_s5(parsed: dict[str, Any], ground_truth: dict[str, Any]) -> tuple[float, bool]:
    """Score S5 output (shared by cb and rag).

    Scoring:
    - agrees must match edge.agree exactly
    - correct=True and score=1.0 if match
    - correct=False and score=0.0 if no match
    """
    if "errors" in parsed:
        return (0.0, False)

    pred_agrees = parsed.get("agrees", False)
    true_agrees = ground_truth.get("agrees", False)

    if pred_agrees == true_agrees:
        return (1.0, True)
    else:
        return (0.0, False)
