"""Citation extraction and verification for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 4.
Uses eyecite for citation extraction, verifies against fake_cases and scdb.
"""

import re
from dataclasses import dataclass
from typing import Sequence

from core.ids.canonical import canonicalize_cite


@dataclass(frozen=True)
class CitationResult:
    """Result of verifying a single citation.

    Attributes:
        cite: The original citation string
        canonical: Canonicalized form of the citation
        exists: Whether the citation is real (in SCDB and not in fake_cases)
        is_fake: Whether the citation is in the fake_cases set
        in_scdb: Whether the citation is in the SCDB index
    """

    cite: str
    canonical: str
    exists: bool
    is_fake: bool
    in_scdb: bool


def extract_citations(text: str) -> list[str]:
    """Extract U.S. Reports citations from text.

    Uses regex pattern matching for U.S. citations.
    Falls back to eyecite if available.

    Args:
        text: Text to extract citations from

    Returns:
        List of citation strings (e.g., ["347 U.S. 483", "349 U.S. 294"])
    """
    citations = []

    # Try eyecite first if available
    try:
        from eyecite import get_citations

        eyecite_results = get_citations(text)
        for cite in eyecite_results:
            # Get the matched text
            cite_text = str(cite)
            # Filter for U.S. citations
            if "U.S." in cite_text or "U. S." in cite_text:
                citations.append(cite_text)

        if citations:
            return citations

    except ImportError:
        pass  # Fall back to regex

    # Regex fallback for U.S. citations
    # Matches patterns like "347 U.S. 483" or "347 U. S. 483"
    us_cite_pattern = r"\d{1,3}\s+U\.?\s*S\.?\s+\d{1,4}"
    matches = re.findall(us_cite_pattern, text, re.IGNORECASE)

    # Normalize matches
    for match in matches:
        # Clean up the match
        cleaned = re.sub(r"\s+", " ", match.strip())
        citations.append(cleaned)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for cite in citations:
        canonical = canonicalize_cite(cite)
        if canonical not in seen:
            seen.add(canonical)
            unique.append(cite)

    return unique


def verify_citation(
    cite: str,
    fake_us_cites: set[str],
    scdb_us_cites: set[str],
) -> CitationResult:
    """Verify a single citation against fake_cases and SCDB.

    A citation is "real" (exists=True) if:
    - It is NOT in fake_cases
    - It IS in SCDB

    Args:
        cite: Citation string to verify
        fake_us_cites: Set of fake US citations (canonicalized)
        scdb_us_cites: Set of real SCDB US citations (canonicalized)

    Returns:
        CitationResult with verification details
    """
    canonical = canonicalize_cite(cite)

    is_fake = canonical in fake_us_cites
    in_scdb = canonical in scdb_us_cites

    # Citation exists if it's in SCDB and not fake
    exists = in_scdb and not is_fake

    return CitationResult(
        cite=cite,
        canonical=canonical,
        exists=exists,
        is_fake=is_fake,
        in_scdb=in_scdb,
    )


def verify_all_citations(
    citations: Sequence[str],
    fake_us_cites: set[str],
    scdb_us_cites: set[str],
) -> tuple[list[CitationResult], bool]:
    """Verify all citations and determine if all are valid.

    Args:
        citations: List of citation strings to verify
        fake_us_cites: Set of fake US citations (canonicalized)
        scdb_us_cites: Set of real SCDB US citations (canonicalized)

    Returns:
        Tuple of (list of CitationResult, all_valid bool)
    """
    results = []
    all_valid = True

    for cite in citations:
        result = verify_citation(cite, fake_us_cites, scdb_us_cites)
        results.append(result)
        if not result.exists:
            all_valid = False

    return results, all_valid


def build_canonical_sets(
    fake_us_cites: set[str],
    scdb_us_cites: set[str] | dict[str, object],
) -> tuple[set[str], set[str]]:
    """Build canonicalized sets for verification.

    Args:
        fake_us_cites: Raw fake US citations
        scdb_us_cites: Raw SCDB US citations (set or dict keys)

    Returns:
        Tuple of (canonical_fake_cites, canonical_scdb_cites)
    """
    canonical_fake = {canonicalize_cite(cite) for cite in fake_us_cites}

    if isinstance(scdb_us_cites, dict):
        canonical_scdb = {canonicalize_cite(cite) for cite in scdb_us_cites.keys()}
    else:
        canonical_scdb = {canonicalize_cite(cite) for cite in scdb_us_cites}

    return canonical_fake, canonical_scdb
