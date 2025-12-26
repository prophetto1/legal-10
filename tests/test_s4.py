"""Tests for S4 Fact Extraction step - Phase 5.

Exit Criteria:
- S4 extracts disposition from closed enum
- S4 extracts party_winning from closed enum
- S4 scoring uses exact string match
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s4_fact_extraction import (
    S4FactExtraction,
    VALID_DISPOSITIONS,
    VALID_PARTY_WINNING,
)
from chain.steps.stub_step import StubStep
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.ground_truth import DISPOSITION_CODES, PARTY_WINNING_CODES
from core.schemas.results import STATUS_OK, STATUS_SKIPPED_DEPENDENCY


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cited_case() -> CourtCase:
    """Cited case with SCDB metadata."""
    return CourtCase(
        us_cite="347 U.S. 483",
        case_name="Brown v. Board of Education",
        term=1954,
        case_disposition=3,  # reversed
        party_winning=1,  # petitioner
        majority_opinion="We conclude that in the field of public education...",
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
def s4_step() -> S4FactExtraction:
    """S4 step instance."""
    return S4FactExtraction()


# =============================================================================
# Test: Closed Enums
# =============================================================================


class TestClosedEnums:
    """Tests for disposition and party_winning closed enums."""

    def test_valid_dispositions_has_11_values(self) -> None:
        """VALID_DISPOSITIONS contains exactly 11 values."""
        assert len(VALID_DISPOSITIONS) == 11

    def test_valid_dispositions_matches_codes(self) -> None:
        """VALID_DISPOSITIONS matches DISPOSITION_CODES values."""
        assert VALID_DISPOSITIONS == frozenset(DISPOSITION_CODES.values())

    def test_valid_party_winning_has_3_values(self) -> None:
        """VALID_PARTY_WINNING contains exactly 3 values."""
        assert len(VALID_PARTY_WINNING) == 3

    def test_valid_party_winning_matches_codes(self) -> None:
        """VALID_PARTY_WINNING matches PARTY_WINNING_CODES values."""
        assert VALID_PARTY_WINNING == frozenset(PARTY_WINNING_CODES.values())


# =============================================================================
# Test: S4 Properties
# =============================================================================


class TestS4Properties:
    """Tests for S4 step properties."""

    def test_step_id(self, s4_step: S4FactExtraction) -> None:
        """S4 has correct step_id."""
        assert s4_step.step_id == "s4"

    def test_step_name(self, s4_step: S4FactExtraction) -> None:
        """S4 has correct step_name."""
        assert s4_step.step_name == "s4"

    def test_requires_s1(self, s4_step: S4FactExtraction) -> None:
        """S4 requires S1."""
        assert s4_step.requires() == {"s1"}


# =============================================================================
# Test: S4 Prompt
# =============================================================================


class TestS4Prompt:
    """Tests for S4 prompt generation."""

    def test_prompt_contains_disposition_enum(
        self, s4_step: S4FactExtraction, instance: ChainInstance
    ) -> None:
        """S4 prompt lists all valid dispositions."""
        ctx = ChainContext(instance=instance)
        prompt = s4_step.prompt(ctx)

        # Check some key dispositions are in prompt
        assert "affirmed" in prompt
        assert "reversed" in prompt
        assert "reversed and remanded" in prompt
        assert "vacated" in prompt

    def test_prompt_contains_party_winning_enum(
        self, s4_step: S4FactExtraction, instance: ChainInstance
    ) -> None:
        """S4 prompt lists party_winning options."""
        ctx = ChainContext(instance=instance)
        prompt = s4_step.prompt(ctx)

        assert "petitioner" in prompt
        assert "respondent" in prompt
        assert "unclear" in prompt


# =============================================================================
# Test: S4 Parsing
# =============================================================================


class TestS4Parse:
    """Tests for S4 response parsing."""

    def test_parse_valid_json(self, s4_step: S4FactExtraction) -> None:
        """Parse valid JSON response."""
        response = '''{
            "disposition": "reversed",
            "party_winning": "petitioner",
            "holding_summary": "The Court held that segregation is unconstitutional."
        }'''
        parsed = s4_step.parse(response)

        assert parsed["disposition"] == "reversed"
        assert parsed["party_winning"] == "petitioner"
        assert "segregation" in parsed["holding_summary"]

    def test_parse_normalizes_case(self, s4_step: S4FactExtraction) -> None:
        """Parse normalizes to lowercase."""
        response = '{"disposition": "REVERSED", "party_winning": "PETITIONER", "holding_summary": ""}'
        parsed = s4_step.parse(response)

        assert parsed["disposition"] == "reversed"
        assert parsed["party_winning"] == "petitioner"

    def test_parse_strips_whitespace(self, s4_step: S4FactExtraction) -> None:
        """Parse strips whitespace."""
        response = '{"disposition": " reversed ", "party_winning": " petitioner ", "holding_summary": ""}'
        parsed = s4_step.parse(response)

        assert parsed["disposition"] == "reversed"
        assert parsed["party_winning"] == "petitioner"

    def test_parse_invalid_json(self, s4_step: S4FactExtraction) -> None:
        """Parse failure returns errors."""
        parsed = s4_step.parse("not json")

        assert "errors" in parsed


# =============================================================================
# Test: S4 Ground Truth
# =============================================================================


class TestS4GroundTruth:
    """Tests for S4 ground truth extraction."""

    def test_ground_truth_from_scdb_codes(
        self, s4_step: S4FactExtraction, instance: ChainInstance
    ) -> None:
        """Ground truth converts SCDB codes to text."""
        ctx = ChainContext(instance=instance)
        gt = s4_step.ground_truth(ctx)

        # case_disposition=3 -> "reversed"
        assert gt["disposition"] == "reversed"
        # party_winning=1 -> "petitioner"
        assert gt["party_winning"] == "petitioner"
        # Raw codes preserved
        assert gt["disposition_code"] == 3
        assert gt["party_winning_code"] == 1


# =============================================================================
# Test: S4 Scoring (Exact Match)
# =============================================================================


class TestS4Scoring:
    """Tests for S4 scoring with exact string match."""

    def test_score_exact_match(self, s4_step: S4FactExtraction) -> None:
        """Score 1.0 when both fields match exactly."""
        parsed = {"disposition": "reversed", "party_winning": "petitioner"}
        gt = {"disposition": "reversed", "party_winning": "petitioner"}

        score, correct = s4_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_disposition_only(self, s4_step: S4FactExtraction) -> None:
        """Score 0.5 when only disposition matches."""
        parsed = {"disposition": "reversed", "party_winning": "respondent"}
        gt = {"disposition": "reversed", "party_winning": "petitioner"}

        score, correct = s4_step.score(parsed, gt)

        assert score == 0.5
        assert correct is False

    def test_score_party_only(self, s4_step: S4FactExtraction) -> None:
        """Score 0.5 when only party_winning matches."""
        parsed = {"disposition": "affirmed", "party_winning": "petitioner"}
        gt = {"disposition": "reversed", "party_winning": "petitioner"}

        score, correct = s4_step.score(parsed, gt)

        assert score == 0.5
        assert correct is False

    def test_score_neither_match(self, s4_step: S4FactExtraction) -> None:
        """Score 0.0 when neither field matches."""
        parsed = {"disposition": "affirmed", "party_winning": "respondent"}
        gt = {"disposition": "reversed", "party_winning": "petitioner"}

        score, correct = s4_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_case_insensitive(self, s4_step: S4FactExtraction) -> None:
        """Scoring is case-insensitive (parse normalizes)."""
        parsed = {"disposition": "reversed", "party_winning": "petitioner"}
        gt = {"disposition": "Reversed", "party_winning": "Petitioner"}

        score, correct = s4_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_parse_error(self, s4_step: S4FactExtraction) -> None:
        """Score 0.0 when parsed has errors."""
        parsed = {"errors": ["JSON parse error"]}
        gt = {"disposition": "reversed", "party_winning": "petitioner"}

        score, correct = s4_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False


# =============================================================================
# Test: S4 Execution
# =============================================================================


class TestS4Execution:
    """Tests for S4 execution via ChainExecutor."""

    def test_s4_skipped_without_s1(self, instance: ChainInstance) -> None:
        """S4 skipped when S1 not present."""
        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[S4FactExtraction()])

        result = executor.execute(instance)

        assert result.step_results["s4"].status == STATUS_SKIPPED_DEPENDENCY

    def test_s4_executes_after_s1(self, instance: ChainInstance) -> None:
        """S4 executes when S1 dependency satisfied."""
        s1 = StubStep(name="s1", requires=set())
        s4 = S4FactExtraction()

        backend = MockBackend(
            default_response='{"disposition": "reversed", "party_winning": "petitioner", "holding_summary": "test"}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s4])

        result = executor.execute(instance)

        assert result.step_results["s1"].status == STATUS_OK
        assert result.step_results["s4"].status == STATUS_OK

    def test_s4_correct_with_matching_response(self, instance: ChainInstance) -> None:
        """S4 scores correct when response matches ground truth."""
        s1 = StubStep(name="s1", requires=set())
        s4 = S4FactExtraction()

        # Response matches ground truth (disposition=3=reversed, party_winning=1=petitioner)
        backend = MockBackend(
            default_response='{"disposition": "reversed", "party_winning": "petitioner", "holding_summary": ""}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s4])

        result = executor.execute(instance)

        assert result.step_results["s4"].correct is True
        assert result.step_results["s4"].score == 1.0
