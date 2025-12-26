"""Tests for S7 Citation Integrity step - Phase 4.

Exit Criteria:
- S7 extracts citations using eyecite (or regex fallback)
- S7 correctly identifies fabricated citations (in fake_cases OR not in scdb)
- S7 gate voids S6 (tested with stub S6)
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s7_citation_integrity import S7CitationIntegrity
from chain.steps.stub_step import StubStep
from core.ids.canonical import canonicalize_cite
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import STATUS_OK
from core.scoring.citation_verify import (
    extract_citations,
    verify_citation,
    verify_all_citations,
    CitationResult,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cited_case() -> CourtCase:
    """Cited case with opinion."""
    return CourtCase(
        us_cite="347 U.S. 483",
        case_name="Brown v. Board of Education",
        term=1954,
        majority_opinion="We conclude that...",
    )


@pytest.fixture
def edge() -> ShepardsEdge:
    """Standard edge."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
    )


@pytest.fixture
def instance(cited_case: CourtCase, edge: ShepardsEdge) -> ChainInstance:
    """Test instance."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case,
        edge=edge,
    )


@pytest.fixture
def fake_cites() -> set[str]:
    """Set of fake citations (canonicalized)."""
    return {
        canonicalize_cite("999 U.S. 999"),
        canonicalize_cite("888 U.S. 888"),
    }


@pytest.fixture
def scdb_cites() -> set[str]:
    """Set of real SCDB citations (canonicalized)."""
    return {
        canonicalize_cite("347 U.S. 483"),  # Brown
        canonicalize_cite("349 U.S. 294"),  # Bolling
        canonicalize_cite("410 U.S. 113"),  # Roe
    }


@pytest.fixture
def s7_step(fake_cites: set[str], scdb_cites: set[str]) -> S7CitationIntegrity:
    """S7 step with verification sets configured."""
    s7 = S7CitationIntegrity()
    s7.set_verification_sets(fake_cites, scdb_cites)
    return s7


# =============================================================================
# Test: Citation Extraction
# =============================================================================


class TestCitationExtraction:
    """Tests for extract_citations function."""

    def test_extract_simple_citation(self) -> None:
        """Extract single U.S. citation."""
        text = "The Court held in Brown v. Board of Education, 347 U.S. 483 (1954)."
        citations = extract_citations(text)

        assert len(citations) >= 1
        assert any("347" in c and "483" in c for c in citations)

    def test_extract_multiple_citations(self) -> None:
        """Extract multiple U.S. citations."""
        text = """
        In 347 U.S. 483, the Court overruled 163 U.S. 537.
        See also 410 U.S. 113.
        """
        citations = extract_citations(text)

        assert len(citations) >= 2

    def test_extract_spaced_citation(self) -> None:
        """Extract citation with extra spaces."""
        text = "The case at 347 U. S. 483 is important."
        citations = extract_citations(text)

        assert len(citations) >= 1

    def test_extract_no_citations(self) -> None:
        """Return empty list when no citations."""
        text = "This text has no legal citations."
        citations = extract_citations(text)

        assert citations == []

    def test_deduplicate_citations(self) -> None:
        """Deduplicate same citation appearing multiple times."""
        text = "347 U.S. 483 is cited. See 347 U.S. 483 again."
        citations = extract_citations(text)

        # Should deduplicate by canonical form
        canonical_cites = [canonicalize_cite(c) for c in citations]
        assert len(set(canonical_cites)) == len(canonical_cites)


# =============================================================================
# Test: Citation Verification
# =============================================================================


class TestCitationVerification:
    """Tests for verify_citation function."""

    def test_real_citation_exists(
        self, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """Real citation (in SCDB, not fake) has exists=True."""
        result = verify_citation("347 U.S. 483", fake_cites, scdb_cites)

        assert result.exists is True
        assert result.is_fake is False
        assert result.in_scdb is True

    def test_fake_citation_not_exists(
        self, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """Fake citation has exists=False."""
        result = verify_citation("999 U.S. 999", fake_cites, scdb_cites)

        assert result.exists is False
        assert result.is_fake is True

    def test_unknown_citation_not_exists(
        self, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """Citation not in SCDB has exists=False."""
        result = verify_citation("500 U.S. 500", fake_cites, scdb_cites)

        assert result.exists is False
        assert result.is_fake is False
        assert result.in_scdb is False

    def test_verify_all_citations_all_valid(
        self, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """All valid citations returns all_valid=True."""
        citations = ["347 U.S. 483", "349 U.S. 294"]
        results, all_valid = verify_all_citations(citations, fake_cites, scdb_cites)

        assert all_valid is True
        assert len(results) == 2
        assert all(r.exists for r in results)

    def test_verify_all_citations_one_fake(
        self, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """One fake citation returns all_valid=False."""
        citations = ["347 U.S. 483", "999 U.S. 999"]
        results, all_valid = verify_all_citations(citations, fake_cites, scdb_cites)

        assert all_valid is False
        assert len(results) == 2


# =============================================================================
# Test: S7 Step Properties
# =============================================================================


class TestS7Properties:
    """Tests for S7 step properties."""

    def test_step_id(self, s7_step: S7CitationIntegrity) -> None:
        """S7 has correct step_id."""
        assert s7_step.step_id == "s7"

    def test_step_name(self, s7_step: S7CitationIntegrity) -> None:
        """S7 has correct step_name."""
        assert s7_step.step_name == "s7"

    def test_requires_s6(self, s7_step: S7CitationIntegrity) -> None:
        """S7 requires S6."""
        assert s7_step.requires() == {"s6"}


# =============================================================================
# Test: S7 Verification Logic
# =============================================================================


class TestS7Verification:
    """Tests for S7 execute_verification method."""

    def test_verification_all_valid(self, s7_step: S7CitationIntegrity) -> None:
        """All citations valid returns all_valid=True."""
        s6_text = """
        Issue: The case at 347 U.S. 483.
        Rule: Following 349 U.S. 294.
        Application: Applying the precedent.
        Conclusion: Therefore affirmed.
        """
        result = s7_step.execute_verification(s6_text)

        assert result["all_valid"] is True
        assert len(result["citations_found"]) >= 2

    def test_verification_fake_citation(self, s7_step: S7CitationIntegrity) -> None:
        """Fake citation returns all_valid=False."""
        s6_text = """
        Issue: The case at 999 U.S. 999 held that...
        """
        result = s7_step.execute_verification(s6_text)

        assert result["all_valid"] is False

    def test_verification_no_citations(self, s7_step: S7CitationIntegrity) -> None:
        """No citations returns all_valid=True (nothing to invalidate)."""
        s6_text = "This text has no legal citations."
        result = s7_step.execute_verification(s6_text)

        assert result["all_valid"] is True
        assert result["citations_found"] == []


# =============================================================================
# Test: S7 Scoring
# =============================================================================


class TestS7Scoring:
    """Tests for S7 scoring."""

    def test_score_all_valid(self, s7_step: S7CitationIntegrity) -> None:
        """Score 1.0 when all_valid=True."""
        parsed = {"all_valid": True, "citations_found": []}
        gt = {"all_valid": True}

        score, correct = s7_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_not_valid(self, s7_step: S7CitationIntegrity) -> None:
        """Score 0.0 when all_valid=False."""
        parsed = {"all_valid": False, "citations_found": [{"cite": "999 U.S. 999", "exists": False}]}
        gt = {"all_valid": True}

        score, correct = s7_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False


# =============================================================================
# Test: S7 Gate Voids S6
# =============================================================================


class TestS7VoidingS6:
    """Tests for S7 gate voiding S6 when citations are fabricated."""

    def test_s7_correct_does_not_void_s6(
        self, instance: ChainInstance, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """S7 correct=True does not void S6."""
        # S6 stub with real citations
        s6 = StubStep(
            name="s6",
            requires=set(),
            always_correct=True,
            parsed_response={
                "issue": "The case at 347 U.S. 483",
                "rule": "Following precedent",
                "application": "Applied here",
                "conclusion": "Affirmed",
            },
        )

        s7 = S7CitationIntegrity()
        s7.set_verification_sets(fake_cites, scdb_cites)

        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[s6, s7])

        result = executor.execute(instance)

        assert result.step_results["s6"].voided is False
        assert result.voided is False

    def test_s7_incorrect_voids_s6(
        self, instance: ChainInstance, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """S7 correct=False (fake citation) voids S6."""
        # S6 stub with fake citation
        s6 = StubStep(
            name="s6",
            requires=set(),
            always_correct=True,
            parsed_response={
                "issue": "The case at 999 U.S. 999",  # FAKE!
                "rule": "Fabricated precedent",
                "application": "Applied here",
                "conclusion": "Invalid",
            },
        )

        # Custom S7 that actually runs verification
        # For this test, we need to hook into the executor flow
        # The stub S7 below simulates S7 detecting the fake citation
        s7 = StubStep(
            name="s7",
            requires={"s6"},
            always_correct=False,  # This triggers voiding
        )

        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[s6, s7])

        result = executor.execute(instance)

        assert result.step_results["s6"].voided is True
        assert result.step_results["s6"].void_reason == "S7 citation integrity gate failed"
        assert result.voided is True


# =============================================================================
# Test: JSONL Output Contains All Fields
# =============================================================================


class TestJSONLOutput:
    """Tests for JSONL output format."""

    def test_step_result_serializes_all_fields(
        self, instance: ChainInstance, fake_cites: set[str], scdb_cites: set[str]
    ) -> None:
        """StepResult serializes all required fields."""
        from core.reporting.jsonl import step_result_to_dict, chain_result_to_dict

        s6 = StubStep(name="s6", requires=set())
        s7 = StubStep(name="s7", requires={"s6"})

        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[s6, s7])

        result = executor.execute(instance)

        # Convert to dict
        result_dict = chain_result_to_dict(result)

        # Check top-level fields
        assert "instance_id" in result_dict
        assert "step_results" in result_dict
        assert "voided" in result_dict
        assert "void_reason" in result_dict

        # Check step result fields
        s6_dict = result_dict["step_results"]["s6"]
        required_fields = [
            "step_id",
            "step",
            "variant",
            "status",
            "prompt",
            "raw_response",
            "parsed",
            "ground_truth",
            "score",
            "correct",
            "voided",
            "void_reason",
            "model",
            "timestamp",
            "latency_ms",
            "tokens_in",
            "tokens_out",
            "model_errors",
        ]
        for field in required_fields:
            assert field in s6_dict, f"Missing field: {field}"
