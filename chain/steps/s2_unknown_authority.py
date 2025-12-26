"""S2: Unknown Authority step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 6 and PROMPT_CONTRACT.md.

S2 asks the model to predict which cases cite the anchor case.
This tests the model's knowledge of case relationships.

Ground truth: edge.citing_case_us_cite
Scoring: MRR (score), hit@10 (correct)
"""

import json
from typing import Any

from chain.steps.base import Step
from core.ids.canonical import canonicalize_cite
from core.schemas.chain import ChainContext

# Prompt template for S2
S2_PROMPT_TEMPLATE = """You are a legal research assistant. Given the following Supreme Court case, list cases that cite this precedent.

CASE:
- Citation: {us_cite}
- Name: {case_name}
- Term: {term}
- Holding: {holding}

List up to 20 Supreme Court cases that cite this case, ranked by relevance/importance.
For each case, provide the U.S. Reports citation and case name.

Return a JSON object with:
- "citing_cases": An array of objects, each with "us_cite" and "case_name"

Example format:
{{
  "citing_cases": [
    {{"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"}},
    {{"us_cite": "350 U.S. 123", "case_name": "Another Case"}}
  ]
}}

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""


class S2UnknownAuthority(Step):
    """S2: Unknown Authority - predict citing cases.

    Input: cited_case metadata + S4 holding
    Output: {citing_cases: [{us_cite, case_name}, ...]}
    Scoring: MRR for score, hit@10 for correct
    """

    @property
    def step_id(self) -> str:
        return "s2"

    @property
    def step_name(self) -> str:
        return "s2"

    def requires(self) -> set[str]:
        """S2 requires S1 (known authority identification)."""
        return {"s1"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S2 requires cited_case text (Tier A)."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S2 prompt."""
        cited = ctx.instance.cited_case

        # Get holding from S4 if available
        s4_result = ctx.get("s4")
        if s4_result and s4_result.parsed:
            holding = s4_result.parsed.get("holding_summary", "")
        else:
            holding = ""

        return S2_PROMPT_TEMPLATE.format(
            us_cite=cited.us_cite,
            case_name=cited.case_name,
            term=cited.term,
            holding=holding or "(No holding summary available)",
        )

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S2 response.

        Expected format:
        {
            "citing_cases": [
                {"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"},
                ...
            ]
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

            citing_cases = data.get("citing_cases", [])

            if not isinstance(citing_cases, list):
                citing_cases = []

            # Normalize citing cases
            normalized = []
            for case in citing_cases:
                if isinstance(case, dict):
                    us_cite = case.get("us_cite", "")
                    case_name = case.get("case_name", "")
                    if us_cite:
                        normalized.append({
                            "us_cite": str(us_cite),
                            "case_name": str(case_name) if case_name else "",
                        })

            return {"citing_cases": normalized}

        except json.JSONDecodeError as e:
            return {"errors": [f"JSON parse error: {e}"]}

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """Get ground truth citing case from edge."""
        edge = ctx.instance.edge
        return {
            "citing_case_us_cite": edge.citing_case_us_cite,
            "citing_case_name": edge.citing_case_name,
        }

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S2 output using MRR and hit@10.

        Scoring (from PROMPT_CONTRACT.md):
        - score = MRR (Mean Reciprocal Rank)
        - correct = hit@10 (true if ground truth in top 10)

        Also computes extended metrics stored in parsed.
        """
        if "errors" in parsed:
            return (0.0, False)

        citing_cases = parsed.get("citing_cases", [])
        true_cite = ground_truth.get("citing_case_us_cite", "")

        if not true_cite:
            return (0.0, False)

        # Canonicalize for comparison
        true_canonical = canonicalize_cite(true_cite)

        # Find rank of ground truth in predictions
        rank = None
        for i, case in enumerate(citing_cases):
            pred_cite = case.get("us_cite", "")
            if canonicalize_cite(pred_cite) == true_canonical:
                rank = i + 1  # 1-indexed
                break

        # Compute metrics
        if rank is None:
            mrr = 0.0
            hit_at_1 = False
            hit_at_5 = False
            hit_at_10 = False
            hit_at_20 = False
        else:
            mrr = 1.0 / rank
            hit_at_1 = rank <= 1
            hit_at_5 = rank <= 5
            hit_at_10 = rank <= 10
            hit_at_20 = rank <= 20

        # Store extended metrics in parsed
        parsed["metrics"] = {
            "rank": rank,
            "mrr": mrr,
            "hit_at_1": hit_at_1,
            "hit_at_5": hit_at_5,
            "hit_at_10": hit_at_10,
            "hit_at_20": hit_at_20,
        }

        # score = MRR, correct = hit@10
        return (mrr, hit_at_10)
