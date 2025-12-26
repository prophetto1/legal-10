"""Tests for core schemas - Phase 1 Contract Lock.

Exit Criteria:
- All dataclasses importable
- StepResult.status is string enum with documented values
- ChainContext.get() / .set() work with step_id keys
"""

import pytest

from core.ids.canonical import canonicalize_cite, case_id, pair_id
from core.schemas.case import CourtCase, OverruleRecord, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.ground_truth import (
    DISPOSITION_CODES,
    PARTY_WINNING_CODES,
    S4GroundTruth,
    disposition_code_to_text,
    party_winning_code_to_text,
)
from core.schemas.results import (
    STATUS_OK,
    STATUS_SKIPPED_COVERAGE,
    STATUS_SKIPPED_DEPENDENCY,
    VALID_STATUSES,
    ChainResult,
    StepResult,
)


# =============================================================================
# Test: core/ids/canonical.py
# =============================================================================


class TestCanonicalIds:
    """Tests for ID canonicalization functions."""

    def test_canonicalize_cite_basic(self) -> None:
        """Spaces become underscores, periods removed, lowercase."""
        assert canonicalize_cite("347 U.S. 483") == "347_us_483"

    def test_canonicalize_cite_spaced_periods(self) -> None:
        """Handle citations with spaces around periods - normalizes to U.S."""
        assert canonicalize_cite("410 U. S. 113") == "410_us_113"

    def test_canonicalize_cite_already_clean(self) -> None:
        """Already canonical input passes through."""
        assert canonicalize_cite("347_us_483") == "347_us_483"

    def test_case_id(self) -> None:
        """Case ID includes scotus prefix, cite, and term."""
        result = case_id("347 U.S. 483", 1954)
        assert result == "scotus::347_us_483::1954"

    def test_pair_id(self) -> None:
        """Pair ID includes both citations."""
        result = pair_id("347 U.S. 483", "349 U.S. 294")
        assert result == "pair::347_us_483::349_us_294"


# =============================================================================
# Test: core/schemas/case.py
# =============================================================================


class TestCourtCase:
    """Tests for CourtCase dataclass."""

    def test_court_case_minimal(self) -> None:
        """CourtCase with only required fields."""
        case = CourtCase(
            us_cite="347 U.S. 483",
            case_name="Brown v. Board of Education",
            term=1954,
        )
        assert case.us_cite == "347 U.S. 483"
        assert case.case_name == "Brown v. Board of Education"
        assert case.term == 1954
        assert case.majority_opinion is None

    def test_court_case_full(self) -> None:
        """CourtCase with all fields populated."""
        case = CourtCase(
            us_cite="347 U.S. 483",
            case_name="Brown v. Board of Education",
            term=1954,
            maj_opin_writer=101,
            case_disposition=3,
            party_winning=1,
            issue_area=2,
            majority_opinion="We conclude that...",
            lexis_cite="1954 U.S. LEXIS 123",
            sct_cite="74 S. Ct. 686",
            importance=0.95,
        )
        assert case.case_disposition == 3
        assert case.majority_opinion == "We conclude that..."

    def test_court_case_frozen(self) -> None:
        """CourtCase is immutable."""
        case = CourtCase(us_cite="347 U.S. 483", case_name="Brown", term=1954)
        with pytest.raises(AttributeError):
            case.term = 1955  # type: ignore[misc]


class TestShepardsEdge:
    """Tests for ShepardsEdge dataclass."""

    def test_shepards_edge_minimal(self) -> None:
        """ShepardsEdge with only required fields."""
        edge = ShepardsEdge(
            cited_case_us_cite="347 U.S. 483",
            citing_case_us_cite="349 U.S. 294",
        )
        assert edge.cited_case_us_cite == "347 U.S. 483"
        assert edge.agree is False

    def test_shepards_edge_full(self) -> None:
        """ShepardsEdge with all fields populated."""
        edge = ShepardsEdge(
            cited_case_us_cite="347 U.S. 483",
            citing_case_us_cite="349 U.S. 294",
            cited_case_name="Brown v. Board of Education",
            citing_case_name="Bolling v. Sharpe",
            shepards="followed",
            agree=True,
            cited_case_year=1954,
            citing_case_year=1954,
        )
        assert edge.shepards == "followed"
        assert edge.agree is True


class TestOverruleRecord:
    """Tests for OverruleRecord dataclass."""

    def test_overrule_record(self) -> None:
        """OverruleRecord creation."""
        record = OverruleRecord(
            overruled_case_us_id="198 U.S. 45",
            overruled_case_name="Lochner v. New York",
            overruling_case_name="West Coast Hotel Co. v. Parrish",
            year_overruled=1937,
            overruled_in_full=True,
        )
        assert record.year_overruled == 1937
        assert record.overruled_in_full is True


# =============================================================================
# Test: core/schemas/ground_truth.py
# =============================================================================


class TestGroundTruth:
    """Tests for S4GroundTruth and code mappings."""

    def test_disposition_codes_complete(self) -> None:
        """All 11 SCDB disposition codes are mapped."""
        assert len(DISPOSITION_CODES) == 11
        assert DISPOSITION_CODES[2] == "affirmed"
        assert DISPOSITION_CODES[3] == "reversed"
        assert DISPOSITION_CODES[4] == "reversed and remanded"

    def test_party_winning_codes_complete(self) -> None:
        """All 3 party winning codes are mapped."""
        assert len(PARTY_WINNING_CODES) == 3
        assert PARTY_WINNING_CODES[1] == "petitioner"
        assert PARTY_WINNING_CODES[0] == "respondent"
        assert PARTY_WINNING_CODES[2] == "unclear"

    def test_disposition_code_to_text(self) -> None:
        """Disposition code conversion."""
        assert disposition_code_to_text(3) == "reversed"
        assert disposition_code_to_text(None) is None
        assert disposition_code_to_text(99) is None

    def test_party_winning_code_to_text(self) -> None:
        """Party winning code conversion."""
        assert party_winning_code_to_text(1) == "petitioner"
        assert party_winning_code_to_text(None) is None

    def test_s4_ground_truth_from_codes(self) -> None:
        """S4GroundTruth.from_scdb_codes factory method."""
        gt = S4GroundTruth.from_scdb_codes(
            disposition_code=3,
            party_winning_code=1,
            issue_area=2,
        )
        assert gt.disposition_code == 3
        assert gt.disposition == "reversed"
        assert gt.party_winning_code == 1
        assert gt.party_winning == "petitioner"
        assert gt.issue_area == 2


# =============================================================================
# Test: core/schemas/results.py
# =============================================================================


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_step_result_minimal(self) -> None:
        """StepResult with only required fields."""
        result = StepResult(step_id="s1", step="s1")
        assert result.step_id == "s1"
        assert result.status == STATUS_OK
        assert result.score == 0.0

    def test_step_result_with_variant(self) -> None:
        """StepResult with variant (e.g., s5:cb)."""
        result = StepResult(step_id="s5:cb", step="s5", variant="cb")
        assert result.step_id == "s5:cb"
        assert result.variant == "cb"

    def test_step_result_valid_statuses(self) -> None:
        """All three valid status values work."""
        for status in VALID_STATUSES:
            result = StepResult(step_id="s1", step="s1", status=status)
            assert result.status == status

    def test_step_result_invalid_status_raises(self) -> None:
        """Invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            StepResult(step_id="s1", step="s1", status="INVALID")

    def test_step_result_voiding(self) -> None:
        """StepResult voiding fields."""
        result = StepResult(
            step_id="s6",
            step="s6",
            voided=True,
            void_reason="S7 citation integrity failure",
        )
        assert result.voided is True
        assert result.void_reason == "S7 citation integrity failure"


class TestChainResult:
    """Tests for ChainResult dataclass."""

    def test_chain_result_minimal(self) -> None:
        """ChainResult with only instance_id."""
        result = ChainResult(instance_id="pair::347_us_483::349_us_294")
        assert result.instance_id == "pair::347_us_483::349_us_294"
        assert result.step_results == {}
        assert result.voided is False


# =============================================================================
# Test: core/schemas/chain.py
# =============================================================================


class TestChainInstance:
    """Tests for ChainInstance dataclass."""

    @pytest.fixture
    def cited_case(self) -> CourtCase:
        """Fixture: cited case with opinion."""
        return CourtCase(
            us_cite="347 U.S. 483",
            case_name="Brown v. Board of Education",
            term=1954,
            majority_opinion="We conclude that in the field of public education...",
        )

    @pytest.fixture
    def citing_case(self) -> CourtCase:
        """Fixture: citing case with opinion."""
        return CourtCase(
            us_cite="349 U.S. 294",
            case_name="Bolling v. Sharpe",
            term=1954,
            majority_opinion="We have this day held...",
        )

    @pytest.fixture
    def edge(self) -> ShepardsEdge:
        """Fixture: Shepard's edge."""
        return ShepardsEdge(
            cited_case_us_cite="347 U.S. 483",
            citing_case_us_cite="349 U.S. 294",
            shepards="followed",
            agree=True,
        )

    def test_chain_instance_tier_a(
        self, cited_case: CourtCase, edge: ShepardsEdge
    ) -> None:
        """ChainInstance with only cited case (Tier A)."""
        instance = ChainInstance(
            id="pair::347_us_483::349_us_294",
            cited_case=cited_case,
            edge=edge,
        )
        assert instance.has_cited_text is True
        assert instance.has_citing_text is False

    def test_chain_instance_tier_b(
        self, cited_case: CourtCase, citing_case: CourtCase, edge: ShepardsEdge
    ) -> None:
        """ChainInstance with both cases (Tier A + B)."""
        instance = ChainInstance(
            id="pair::347_us_483::349_us_294",
            cited_case=cited_case,
            citing_case=citing_case,
            edge=edge,
        )
        assert instance.has_cited_text is True
        assert instance.has_citing_text is True

    def test_chain_instance_no_opinion(self, edge: ShepardsEdge) -> None:
        """ChainInstance with cited case missing opinion."""
        case_no_opinion = CourtCase(
            us_cite="347 U.S. 483",
            case_name="Brown v. Board of Education",
            term=1954,
            # No majority_opinion
        )
        instance = ChainInstance(
            id="pair::347_us_483::349_us_294",
            cited_case=case_no_opinion,
            edge=edge,
        )
        assert instance.has_cited_text is False


class TestChainContext:
    """Tests for ChainContext dataclass."""

    @pytest.fixture
    def instance(self) -> ChainInstance:
        """Fixture: minimal ChainInstance."""
        return ChainInstance(
            id="pair::347_us_483::349_us_294",
            cited_case=CourtCase(
                us_cite="347 U.S. 483",
                case_name="Brown",
                term=1954,
            ),
            edge=ShepardsEdge(
                cited_case_us_cite="347 U.S. 483",
                citing_case_us_cite="349 U.S. 294",
            ),
        )

    def test_chain_context_get_set(self, instance: ChainInstance) -> None:
        """ChainContext.get() and .set() work with step_id keys."""
        ctx = ChainContext(instance=instance)

        # Initially empty
        assert ctx.get("s1") is None

        # Set and get
        result = StepResult(step_id="s1", step="s1", score=0.95)
        ctx.set("s1", result)
        assert ctx.get("s1") is result
        assert ctx.get("s1").score == 0.95  # type: ignore[union-attr]

    def test_chain_context_variant_step_ids(self, instance: ChainInstance) -> None:
        """s5:cb and s5:rag stored separately."""
        ctx = ChainContext(instance=instance)

        cb_result = StepResult(step_id="s5:cb", step="s5", variant="cb")
        rag_result = StepResult(step_id="s5:rag", step="s5", variant="rag")

        ctx.set("s5:cb", cb_result)
        ctx.set("s5:rag", rag_result)

        assert ctx.get("s5:cb") is cb_result
        assert ctx.get("s5:rag") is rag_result
        assert ctx.get("s5:cb") is not ctx.get("s5:rag")

    def test_chain_context_has_step(self, instance: ChainInstance) -> None:
        """has_step checks logical step name across variants."""
        ctx = ChainContext(instance=instance)

        assert ctx.has_step("s5") is False

        ctx.set("s5:cb", StepResult(step_id="s5:cb", step="s5", variant="cb"))
        assert ctx.has_step("s5") is True

    def test_chain_context_get_by_step(self, instance: ChainInstance) -> None:
        """get_by_step returns first matching logical step."""
        ctx = ChainContext(instance=instance)

        ctx.set("s5:cb", StepResult(step_id="s5:cb", step="s5", variant="cb"))
        ctx.set("s5:rag", StepResult(step_id="s5:rag", step="s5", variant="rag"))

        result = ctx.get_by_step("s5")
        assert result is not None
        assert result.step == "s5"

    def test_chain_context_get_ok_step_ids(self, instance: ChainInstance) -> None:
        """get_ok_step_ids returns only OK status steps."""
        ctx = ChainContext(instance=instance)

        ctx.set("s1", StepResult(step_id="s1", step="s1", status=STATUS_OK))
        ctx.set(
            "s2",
            StepResult(step_id="s2", step="s2", status=STATUS_SKIPPED_DEPENDENCY),
        )
        ctx.set("s3", StepResult(step_id="s3", step="s3", status=STATUS_OK))

        ok_ids = ctx.get_ok_step_ids()
        assert ok_ids == {"s1", "s3"}
