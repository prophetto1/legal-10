"""IRAC Rubric Scorer for S6.

From MVP_BUILD_ORDER.md Phase 7.

Provides MEE-style (Multistate Essay Examination) rubric scoring
for IRAC legal analysis components.
"""

from typing import Any

# Minimum character threshold for component to be considered "present"
MIN_COMPONENT_LENGTH = 10

# IRAC component weights (must sum to 1.0)
COMPONENT_WEIGHTS = {
    "issue": 0.25,
    "rule": 0.25,
    "application": 0.25,
    "conclusion": 0.25,
}


def score_irac_presence(parsed: dict[str, Any]) -> tuple[float, dict[str, bool]]:
    """Score IRAC components based on presence.

    Args:
        parsed: Parsed S6 response with issue, rule, application, conclusion

    Returns:
        (total_score, component_present_map)
        - total_score: 0.0 to 1.0 based on weighted presence
        - component_present_map: {component: bool} for each IRAC component
    """
    component_present = {}
    total_score = 0.0

    for component, weight in COMPONENT_WEIGHTS.items():
        value = parsed.get(component, "")
        is_present = isinstance(value, str) and len(value.strip()) > MIN_COMPONENT_LENGTH
        component_present[component] = is_present
        if is_present:
            total_score += weight

    return (total_score, component_present)


def score_irac_quality(
    parsed: dict[str, Any],
    ground_truth: dict[str, Any] | None = None
) -> tuple[float, dict[str, float]]:
    """Score IRAC components based on quality (future enhancement).

    Currently uses presence scoring. Future versions may use:
    - Keyword matching against case facts
    - LLM-as-judge evaluation
    - Citation accuracy checking

    Args:
        parsed: Parsed S6 response
        ground_truth: Optional ground truth for comparison

    Returns:
        (total_score, component_scores)
    """
    # For MVP, quality = presence
    total_score, component_present = score_irac_presence(parsed)

    component_scores = {
        component: (1.0 if present else 0.0)
        for component, present in component_present.items()
    }

    return (total_score, component_scores)


def is_irac_correct(score: float, threshold: float = 0.75) -> bool:
    """Determine if IRAC analysis is correct based on score.

    Args:
        score: Total IRAC score (0.0 to 1.0)
        threshold: Minimum score for correctness (default 0.75 = 3/4 components)

    Returns:
        True if score meets threshold
    """
    return score >= threshold


def get_missing_components(parsed: dict[str, Any]) -> list[str]:
    """Get list of missing IRAC components.

    Args:
        parsed: Parsed S6 response

    Returns:
        List of component names that are missing or too short
    """
    _, component_present = score_irac_presence(parsed)
    return [comp for comp, present in component_present.items() if not present]


def format_rubric_feedback(parsed: dict[str, Any]) -> str:
    """Generate human-readable rubric feedback.

    Args:
        parsed: Parsed S6 response

    Returns:
        Formatted feedback string
    """
    score, component_present = score_irac_presence(parsed)
    lines = [f"IRAC Score: {score:.0%}", ""]

    for component in ["issue", "rule", "application", "conclusion"]:
        status = "[OK]" if component_present[component] else "[MISSING]"
        lines.append(f"  {status} {component.upper()}")

    missing = get_missing_components(parsed)
    if missing:
        lines.append("")
        lines.append(f"Missing components: {', '.join(missing)}")

    return "\n".join(lines)
