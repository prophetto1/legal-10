"""S6: IRAC Synthesis step for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 7 and PROMPT_CONTRACT.md.

S6 synthesizes outputs from prior steps into an IRAC-format legal analysis:
- Issue: Legal question at stake
- Rule: Applicable legal principles
- Application: How rule applies to facts
- Conclusion: Final determination

Ground truth: Rubric-based scoring (MEE-style)
Voiding: S7 can void S6 if fabricated citations detected
"""

import json
from typing import Any

from chain.steps.base import Step
from core.schemas.chain import ChainContext

# Prompt template for S6
S6_PROMPT_TEMPLATE = """You are a legal research assistant. Synthesize the following information into a complete IRAC legal analysis.

CASE INFORMATION:
- Citation: {us_cite}
- Name: {case_name}
- Term: {term}

EXTRACTED FACTS (from S4):
- Disposition: {disposition}
- Party Winning: {party_winning}
- Holding: {holding}

AUTHORITY STATUS (from S3):
{authority_status}

RELATIONSHIP ANALYSIS (from S5):
{relationship_analysis}

CITING CASES (from S2):
{citing_cases}

Write a complete IRAC analysis of this case:

1. ISSUE: State the central legal question the Court addressed.

2. RULE: Identify the legal rule or principle the Court applied.

3. APPLICATION: Explain how the Court applied the rule to the facts.

4. CONCLUSION: State the Court's holding and its significance.

Return a JSON object with these fields:
- "issue": The legal issue (1-2 sentences)
- "rule": The applicable rule (1-2 sentences)
- "application": How the rule was applied (2-3 sentences)
- "conclusion": The holding and significance (1-2 sentences)

Return a single JSON object matching the schema exactly.
No extra keys. No surrounding text. No markdown code fences."""


class S6IRACSynthesis(Step):
    """S6: IRAC Synthesis - combine prior step outputs.

    Input: Results from S1, S2, S3, S4, S5:cb
    Output: {issue, rule, application, conclusion}
    Scoring: Rubric-based (presence and quality of each component)
    Voiding: S7 can void if fabricated citations detected
    """

    @property
    def step_id(self) -> str:
        return "s6"

    @property
    def step_name(self) -> str:
        return "s6"

    def requires(self) -> set[str]:
        """S6 requires S1, S2, S3, S4, and S5:cb."""
        return {"s1", "s2", "s3", "s4", "s5:cb"}

    def check_coverage(self, ctx: ChainContext) -> bool:
        """S6 requires cited_case text (Tier A)."""
        return ctx.instance.has_cited_text

    def prompt(self, ctx: ChainContext) -> str:
        """Build S6 prompt with outputs from prior steps."""
        cited = ctx.instance.cited_case

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

        # Get S3 results (authority validation)
        s3_result = ctx.get("s3")
        if s3_result and s3_result.parsed:
            is_overruled = s3_result.parsed.get("is_overruled", False)
            if is_overruled:
                overruling_case = s3_result.parsed.get("overruling_case", "Unknown")
                year = s3_result.parsed.get("year_overruled", "Unknown")
                authority_status = f"This case was OVERRULED by {overruling_case} in {year}."
            else:
                authority_status = "This case remains good law (not overruled)."
        else:
            authority_status = "Authority status unknown."

        # Get S5:cb results (relationship analysis)
        s5_result = ctx.get("s5:cb")
        if s5_result and s5_result.parsed:
            agrees = s5_result.parsed.get("agrees", None)
            reasoning = s5_result.parsed.get("reasoning", "")
            if agrees is True:
                relationship_analysis = f"The citing case AGREES with this precedent. {reasoning}"
            elif agrees is False:
                relationship_analysis = f"The citing case DISTINGUISHES this precedent. {reasoning}"
            else:
                relationship_analysis = "Relationship unclear."
        else:
            relationship_analysis = "No relationship analysis available."

        # Get S2 results (citing cases)
        s2_result = ctx.get("s2")
        if s2_result and s2_result.parsed:
            citing_cases_list = s2_result.parsed.get("citing_cases", [])
            if citing_cases_list:
                cases_str = "\n".join(
                    f"  - {c.get('case_name', 'Unknown')} ({c.get('us_cite', '')})"
                    for c in citing_cases_list[:5]  # Limit to top 5
                )
                citing_cases = f"Cases that cite this precedent:\n{cases_str}"
            else:
                citing_cases = "No citing cases identified."
        else:
            citing_cases = "No citing cases available."

        return S6_PROMPT_TEMPLATE.format(
            us_cite=cited.us_cite,
            case_name=cited.case_name,
            term=cited.term,
            disposition=disposition,
            party_winning=party_winning,
            holding=holding or "(No holding summary available)",
            authority_status=authority_status,
            relationship_analysis=relationship_analysis,
            citing_cases=citing_cases,
        )

    def parse(self, raw_response: str) -> dict[str, Any]:
        """Parse S6 response.

        Expected format:
        {
            "issue": "Whether segregation in public schools...",
            "rule": "The Equal Protection Clause...",
            "application": "Applying this rule...",
            "conclusion": "Therefore, the Court concludes..."
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

            issue = data.get("issue", "")
            rule = data.get("rule", "")
            application = data.get("application", "")
            conclusion = data.get("conclusion", "")

            return {
                "issue": str(issue) if issue else "",
                "rule": str(rule) if rule else "",
                "application": str(application) if application else "",
                "conclusion": str(conclusion) if conclusion else "",
            }

        except json.JSONDecodeError as e:
            return {"errors": [f"JSON parse error: {e}"]}

    def ground_truth(self, ctx: ChainContext) -> dict[str, Any]:
        """S6 ground truth is rubric-based.

        Unlike other steps, S6 doesn't have external ground truth data.
        Scoring is based on presence and quality of IRAC components.
        """
        return {
            "rubric": "irac_presence",
            "components": ["issue", "rule", "application", "conclusion"],
        }

    def score(
        self, parsed: dict[str, Any], ground_truth: dict[str, Any]
    ) -> tuple[float, bool]:
        """Score S6 output using IRAC rubric.

        Scoring:
        - Each IRAC component (issue, rule, application, conclusion) = 0.25
        - Component must be non-empty string with >10 chars to count
        - score = sum of component scores (0.0 to 1.0)
        - correct = True if score >= 0.75 (at least 3 components present)
        """
        if "errors" in parsed:
            return (0.0, False)

        components = ["issue", "rule", "application", "conclusion"]
        component_score = 0.0

        for component in components:
            value = parsed.get(component, "")
            if isinstance(value, str) and len(value.strip()) > 10:
                component_score += 0.25

        correct = component_score >= 0.75
        return (component_score, correct)
