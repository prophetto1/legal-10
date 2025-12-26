"""Case-related schemas for L10 Agentic Chain.

From L10_AGENTIC_SPEC.md §3.1-3.3.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CourtCase:
    """A SCOTUS case with metadata and optional opinion text.

    Attributes:
        us_cite: US Reports citation (e.g., "347 U.S. 483")
        case_name: Full case name (e.g., "Brown v. Board of Education")
        term: SCDB term year (e.g., 1954)
        maj_opin_writer: SCDB majOpinWriter code
        case_disposition: SCDB caseDisposition code (1-11)
        party_winning: SCDB partyWinning (1=petitioner, 0=respondent, 2=unclear)
        issue_area: SCDB issueArea code
        majority_opinion: Full text of majority opinion (None if not available)
        lexis_cite: LexisNexis citation
        sct_cite: Supreme Court Reporter citation
        importance: pauth_score from fowler_scores
    """

    us_cite: str
    case_name: str
    term: int
    maj_opin_writer: int | None = None
    case_disposition: int | None = None
    party_winning: int | None = None
    issue_area: int | None = None
    majority_opinion: str | None = None
    lexis_cite: str | None = None
    sct_cite: str | None = None
    importance: float | None = None


@dataclass(frozen=True)
class ShepardsEdge:
    """A citation relationship between two cases.

    Represents one edge in the Shepard's citation network.

    Attributes:
        cited_case_us_cite: US citation of the cited (earlier) case
        citing_case_us_cite: US citation of the citing (later) case
        cited_case_name: Name of the cited case
        citing_case_name: Name of the citing case
        shepards: Shepard's signal (e.g., "followed", "distinguished")
        agree: True if followed/parallel, False otherwise
        cited_case_year: Year of the cited case
        citing_case_year: Year of the citing case
    """

    cited_case_us_cite: str
    citing_case_us_cite: str
    cited_case_name: str | None = None
    citing_case_name: str | None = None
    shepards: str = ""
    agree: bool = False
    cited_case_year: int | None = None
    citing_case_year: int | None = None


@dataclass(frozen=True)
class OverruleRecord:
    """A record of a case being overruled.

    Attributes:
        overruled_case_us_id: US citation of the overruled case
        overruled_case_name: Name of the overruled case
        overruling_case_name: Name of the case that overruled it
        year_overruled: Year the case was overruled
        overruled_in_full: True if fully overruled, False if partial
    """

    overruled_case_us_id: str
    overruled_case_name: str
    overruling_case_name: str
    year_overruled: int
    overruled_in_full: bool = True