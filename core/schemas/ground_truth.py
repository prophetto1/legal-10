"""Ground truth schemas for L10 Agentic Chain.

From L10_AGENTIC_SPEC.md §3.8.
"""

from dataclasses import dataclass

# SCDB disposition code to text mapping
DISPOSITION_CODES: dict[int, str] = {
    1: "stay granted",
    2: "affirmed",
    3: "reversed",
    4: "reversed and remanded",
    5: "vacated and remanded",
    6: "affirmed and reversed in part",
    7: "affirmed and vacated in part",
    8: "affirmed and reversed in part and remanded",
    9: "vacated",
    10: "petition denied",
    11: "certification",
}

# SCDB party winning code to text mapping
PARTY_WINNING_CODES: dict[int, str] = {
    1: "petitioner",
    0: "respondent",
    2: "unclear",
}


def disposition_code_to_text(code: int | None) -> str | None:
    """Convert SCDB disposition code to text label.

    Args:
        code: SCDB caseDisposition code (1-11)

    Returns:
        Text label or None if code is None or unknown
    """
    if code is None:
        return None
    return DISPOSITION_CODES.get(code)


def party_winning_code_to_text(code: int | None) -> str | None:
    """Convert SCDB party winning code to text label.

    Args:
        code: SCDB partyWinning code (0, 1, or 2)

    Returns:
        Text label or None if code is None or unknown
    """
    if code is None:
        return None
    return PARTY_WINNING_CODES.get(code)


@dataclass(frozen=True)
class S4GroundTruth:
    """Ground truth for S4: Fact Extraction.

    Attributes:
        disposition_code: SCDB caseDisposition (raw code 1-11)
        disposition: Derived text from closed enum
        party_winning_code: SCDB partyWinning (1/0/2)
        party_winning: Derived text ("petitioner"/"respondent"/"unclear")
        issue_area: SCDB issueArea (optional for v1)
    """

    disposition_code: int | None = None
    disposition: str | None = None
    party_winning_code: int | None = None
    party_winning: str | None = None
    issue_area: int | None = None

    @classmethod
    def from_scdb_codes(
        cls,
        disposition_code: int | None,
        party_winning_code: int | None,
        issue_area: int | None = None,
    ) -> "S4GroundTruth":
        """Create S4GroundTruth from SCDB codes.

        Args:
            disposition_code: SCDB caseDisposition code
            party_winning_code: SCDB partyWinning code
            issue_area: SCDB issueArea code (optional)

        Returns:
            S4GroundTruth with derived text labels
        """
        return cls(
            disposition_code=disposition_code,
            disposition=disposition_code_to_text(disposition_code),
            party_winning_code=party_winning_code,
            party_winning=party_winning_code_to_text(party_winning_code),
            issue_area=issue_area,
        )
