"""Canonical ID generation for L10 entities.

ID Schemes (from L10_AGENTIC_SPEC.md §1.1):
- SCOTUS Case: scotus::<usCite>::<term>
- Case Pair: pair::<cited_us_cite>::<citing_us_cite>

Canonicalization rules:
- Replace spaces with underscores
- Remove periods from citation abbreviations
- Lowercase all characters
"""


def canonicalize_cite(cite: str) -> str:
    """Canonicalize a US citation for use in IDs.

    Args:
        cite: Raw citation string (e.g., "347 U.S. 483")

    Returns:
        Canonicalized citation (e.g., "347_us_483")

    Examples:
        >>> canonicalize_cite("347 U.S. 483")
        '347_us_483'
        >>> canonicalize_cite("410 U. S. 113")
        '410_us_113'
    """
    # Normalize "U. S." variants to "U.S." first
    normalized = cite.replace("U. S.", "U.S.").replace("u. s.", "u.s.")
    # Then apply standard canonicalization
    return normalized.replace(" ", "_").replace(".", "").lower()


def case_id(us_cite: str, term: int) -> str:
    """Generate canonical case ID.

    Args:
        us_cite: US Reports citation (e.g., "347 U.S. 483")
        term: SCDB term year (e.g., 1954)

    Returns:
        Canonical case ID (e.g., "scotus::347_us_483::1954")

    Examples:
        >>> case_id("347 U.S. 483", 1954)
        'scotus::347_us_483::1954'
    """
    return f"scotus::{canonicalize_cite(us_cite)}::{term}"


def pair_id(cited_us_cite: str, citing_us_cite: str) -> str:
    """Generate canonical case pair ID.

    Args:
        cited_us_cite: US citation of the cited (earlier) case
        citing_us_cite: US citation of the citing (later) case

    Returns:
        Canonical pair ID (e.g., "pair::347_us_483::349_us_294")

    Examples:
        >>> pair_id("347 U.S. 483", "349 U.S. 294")
        'pair::347_us_483::349_us_294'
    """
    return f"pair::{canonicalize_cite(cited_us_cite)}::{canonicalize_cite(citing_us_cite)}"
