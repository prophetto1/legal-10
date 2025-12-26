"""Tests for S1 Known Authority step - Phase 4.

Exit Criteria:
- S1 executes on real ChainInstance, returns valid StepResult
- S1 scoring uses canonicalize_cite() for tolerance
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s1_known_authority import S1KnownAuthority
from core.ids.canonical import canonicalize_cite
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import STATUS_OK, STATUS_SKIPPED_COVERAGE


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cited_case() -> CourtCase:
    """Cited case with opinion text."""
    return CourtCase(
        us_cite="347 U.S. 483",
        case_name="Brown v. Board of Education",
        term=1954,
        majority_opinion="""
            Brown v. Board of Education of Topeka, 347 U.S. 483 (1954)

            We come then to the question presented: Does segregation of children
            in public schools solely on the basis of race, even though the physical
            facilities and other "tangible" factors may be equal, deprive the children
            of the minority group of equal educational opportunities? We believe that it does.

            We conclude that in the field of public education the doctrine of
            "separate but equal" has no place. Separate educational facilities are
            inherently unequal.
        """,
    )


@pytest.fixture
def cited_case_no_opinion() -> CourtCase:
    """Cited case without opinion text."""
    return CourtCase(
        us_cite="347 U.S. 483",
        case_name="Brown v. Board of Education",
        term=1954,
        # No majority_opinion
    )


@pytest.fixture
def edge() -> ShepardsEdge:
    """Standard edge."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
    )


@pytest.fixture
def instance_with_opinion(cited_case: CourtCase, edge: ShepardsEdge) -> ChainInstance:
    """Instance with cited case having opinion."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case,
        edge=edge,
    )


@pytest.fixture
def instance_no_opinion(cited_case_no_opinion: CourtCase, edge: ShepardsEdge) -> ChainInstance:
    """Instance with cited case missing opinion."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case_no_opinion,
        edge=edge,
    )


@pytest.fixture
def s1_step() -> S1KnownAuthority:
    """S1 step instance."""
    return S1KnownAuthority()


# =============================================================================
# Test: S1 Basic Properties
# =============================================================================


class TestS1Properties:
    """Tests for S1 step properties."""

    def test_step_id(self, s1_step: S1KnownAuthority) -> None:
        """S1 has correct step_id."""
        assert s1_step.step_id == "s1"

    def test_step_name(self, s1_step: S1KnownAuthority) -> None:
        """S1 has correct step_name."""
        assert s1_step.step_name == "s1"

    def test_no_dependencies(self, s1_step: S1KnownAuthority) -> None:
        """S1 has no dependencies."""
        assert s1_step.requires() == set()


# =============================================================================
# Test: S1 Coverage Check
# =============================================================================


class TestS1Coverage:
    """Tests for S1 coverage checking."""

    def test_coverage_with_opinion(
        self, s1_step: S1KnownAuthority, instance_with_opinion: ChainInstance
    ) -> None:
        """S1 has coverage when cited case has opinion."""
        ctx = ChainContext(instance=instance_with_opinion)
        assert s1_step.check_coverage(ctx) is True

    def test_coverage_without_opinion(
        self, s1_step: S1KnownAuthority, instance_no_opinion: ChainInstance
    ) -> None:
        """S1 lacks coverage when cited case has no opinion."""
        ctx = ChainContext(instance=instance_no_opinion)
        assert s1_step.check_coverage(ctx) is False


# =============================================================================
# Test: S1 Prompt Generation
# =============================================================================


class TestS1Prompt:
    """Tests for S1 prompt generation."""

    def test_prompt_contains_opinion(
        self, s1_step: S1KnownAuthority, instance_with_opinion: ChainInstance
    ) -> None:
        """S1 prompt contains opinion text."""
        ctx = ChainContext(instance=instance_with_opinion)
        prompt = s1_step.prompt(ctx)

        assert "Brown v. Board of Education" in prompt
        assert "347 U.S. 483" in prompt
        assert "separate but equal" in prompt

    def test_prompt_ends_with_json_instruction(
        self, s1_step: S1KnownAuthority, instance_with_opinion: ChainInstance
    ) -> None:
        """S1 prompt ends with JSON format instruction."""
        ctx = ChainContext(instance=instance_with_opinion)
        prompt = s1_step.prompt(ctx)

        assert "JSON object" in prompt
        assert "No markdown code fences" in prompt


# =============================================================================
# Test: S1 Parsing
# =============================================================================


class TestS1Parse:
    """Tests for S1 response parsing."""

    def test_parse_valid_json(self, s1_step: S1KnownAuthority) -> None:
        """Parse valid JSON response."""
        response = '{"us_cite": "347 U.S. 483", "case_name": "Brown v. Board", "term": 1954}'
        parsed = s1_step.parse(response)

        assert parsed["us_cite"] == "347 U.S. 483"
        assert parsed["case_name"] == "Brown v. Board"
        assert parsed["term"] == 1954

    def test_parse_markdown_code_block(self, s1_step: S1KnownAuthority) -> None:
        """Parse JSON wrapped in markdown code block."""
        response = """```json
{"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}
```"""
        parsed = s1_step.parse(response)

        assert parsed["us_cite"] == "347 U.S. 483"
        assert parsed["term"] == 1954

    def test_parse_invalid_json(self, s1_step: S1KnownAuthority) -> None:
        """Parse failure returns errors."""
        response = "This is not JSON"
        parsed = s1_step.parse(response)

        assert "errors" in parsed

    def test_parse_empty_response(self, s1_step: S1KnownAuthority) -> None:
        """Parse empty response returns errors."""
        parsed = s1_step.parse("")

        assert "errors" in parsed

    def test_parse_term_as_string(self, s1_step: S1KnownAuthority) -> None:
        """Parse term as string, convert to int."""
        response = '{"us_cite": "347 U.S. 483", "case_name": "Brown", "term": "1954"}'
        parsed = s1_step.parse(response)

        assert parsed["term"] == 1954


# =============================================================================
# Test: S1 Ground Truth
# =============================================================================


class TestS1GroundTruth:
    """Tests for S1 ground truth extraction."""

    def test_ground_truth_from_cited_case(
        self, s1_step: S1KnownAuthority, instance_with_opinion: ChainInstance
    ) -> None:
        """Ground truth comes from cited_case metadata."""
        ctx = ChainContext(instance=instance_with_opinion)
        gt = s1_step.ground_truth(ctx)

        assert gt["us_cite"] == "347 U.S. 483"
        assert gt["case_name"] == "Brown v. Board of Education"
        assert gt["term"] == 1954


# =============================================================================
# Test: S1 Scoring with canonicalize_cite()
# =============================================================================


class TestS1Scoring:
    """Tests for S1 scoring using canonicalize_cite()."""

    def test_score_exact_match(self, s1_step: S1KnownAuthority) -> None:
        """Score 1.0 when citation and term match exactly."""
        parsed = {"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}
        gt = {"us_cite": "347 U.S. 483", "case_name": "Brown v. Board", "term": 1954}

        score, correct = s1_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_canonical_tolerance(self, s1_step: S1KnownAuthority) -> None:
        """Score tolerates different citation formats via canonicalize_cite()."""
        # Different spacing/formatting, same canonical form
        parsed = {"us_cite": "347 U. S. 483", "case_name": "Brown", "term": 1954}
        gt = {"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}

        # Verify they canonicalize to same value
        assert canonicalize_cite("347 U. S. 483") == canonicalize_cite("347 U.S. 483")

        score, correct = s1_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_wrong_citation(self, s1_step: S1KnownAuthority) -> None:
        """Score 0.5 when only term matches."""
        parsed = {"us_cite": "999 U.S. 999", "case_name": "Wrong", "term": 1954}
        gt = {"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}

        score, correct = s1_step.score(parsed, gt)

        assert score == 0.5  # Term matches
        assert correct is False

    def test_score_wrong_term(self, s1_step: S1KnownAuthority) -> None:
        """Score 0.5 when only citation matches."""
        parsed = {"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1900}
        gt = {"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}

        score, correct = s1_step.score(parsed, gt)

        assert score == 0.5  # Citation matches
        assert correct is False

    def test_score_both_wrong(self, s1_step: S1KnownAuthority) -> None:
        """Score 0.0 when neither matches."""
        parsed = {"us_cite": "999 U.S. 999", "case_name": "Wrong", "term": 1900}
        gt = {"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}

        score, correct = s1_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_parse_error(self, s1_step: S1KnownAuthority) -> None:
        """Score 0.0 when parsed has errors."""
        parsed = {"errors": ["JSON parse error"]}
        gt = {"us_cite": "347 U.S. 483", "term": 1954}

        score, correct = s1_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False


# =============================================================================
# Test: S1 Execution with Executor
# =============================================================================


class TestS1Execution:
    """Tests for S1 execution via ChainExecutor."""

    def test_s1_executes_returns_step_result(
        self, instance_with_opinion: ChainInstance
    ) -> None:
        """S1 executes and returns valid StepResult."""
        backend = MockBackend(
            responses={
                "OPINION": '{"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}'
            }
        )
        executor = ChainExecutor(backend=backend, steps=[S1KnownAuthority()])

        result = executor.execute(instance_with_opinion)

        assert "s1" in result.step_results
        sr = result.step_results["s1"]
        assert sr.step_id == "s1"
        assert sr.status == STATUS_OK

    def test_s1_skipped_no_opinion(
        self, instance_no_opinion: ChainInstance
    ) -> None:
        """S1 skipped when cited case has no opinion."""
        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[S1KnownAuthority()])

        result = executor.execute(instance_no_opinion)

        assert "s1" in result.step_results
        sr = result.step_results["s1"]
        assert sr.status == STATUS_SKIPPED_COVERAGE

    def test_s1_correct_with_mock_response(
        self, instance_with_opinion: ChainInstance
    ) -> None:
        """S1 scores correct when mock returns matching data."""
        backend = MockBackend(
            default_response='{"us_cite": "347 U.S. 483", "case_name": "Brown", "term": 1954}'
        )
        executor = ChainExecutor(backend=backend, steps=[S1KnownAuthority()])

        result = executor.execute(instance_with_opinion)

        sr = result.step_results["s1"]
        assert sr.correct is True
        assert sr.score == 1.0
