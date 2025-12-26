"""Tests for S2 Unknown Authority step - Phase 6.

Exit Criteria:
- S2 predicts citing cases with MRR scoring
- S2 uses hit@10 for correct determination
- S2 requires S1 dependency
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s2_unknown_authority import S2UnknownAuthority
from chain.steps.stub_step import StubStep
from core.ids.canonical import canonicalize_cite
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import STATUS_OK, STATUS_SKIPPED_DEPENDENCY


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
        majority_opinion="We conclude that segregation is unconstitutional...",
    )


@pytest.fixture
def edge() -> ShepardsEdge:
    """Edge with known citing case."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
        cited_case_name="Brown v. Board of Education",
        citing_case_name="Bolling v. Sharpe",
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
def s2_step() -> S2UnknownAuthority:
    """S2 step instance."""
    return S2UnknownAuthority()


# =============================================================================
# Test: S2 Properties
# =============================================================================


class TestS2Properties:
    """Tests for S2 step properties."""

    def test_step_id(self, s2_step: S2UnknownAuthority) -> None:
        """S2 has correct step_id."""
        assert s2_step.step_id == "s2"

    def test_step_name(self, s2_step: S2UnknownAuthority) -> None:
        """S2 has correct step_name."""
        assert s2_step.step_name == "s2"

    def test_requires_s1(self, s2_step: S2UnknownAuthority) -> None:
        """S2 requires S1."""
        assert s2_step.requires() == {"s1"}


# =============================================================================
# Test: S2 Coverage
# =============================================================================


class TestS2Coverage:
    """Tests for S2 coverage requirements."""

    def test_coverage_with_cited_text(
        self, s2_step: S2UnknownAuthority, instance: ChainInstance
    ) -> None:
        """S2 has coverage when cited case has opinion."""
        ctx = ChainContext(instance=instance)
        assert s2_step.check_coverage(ctx) is True

    def test_coverage_without_cited_text(self, s2_step: S2UnknownAuthority) -> None:
        """S2 lacks coverage without cited case opinion."""
        cited = CourtCase(
            us_cite="347 U.S. 483",
            case_name="Brown v. Board of Education",
            term=1954,
            # No majority_opinion
        )
        edge = ShepardsEdge(
            cited_case_us_cite="347 U.S. 483",
            citing_case_us_cite="349 U.S. 294",
        )
        instance = ChainInstance(
            id="pair::347_us_483::349_us_294",
            cited_case=cited,
            edge=edge,
        )
        ctx = ChainContext(instance=instance)
        assert s2_step.check_coverage(ctx) is False


# =============================================================================
# Test: S2 Prompt
# =============================================================================


class TestS2Prompt:
    """Tests for S2 prompt generation."""

    def test_prompt_contains_case_metadata(
        self, s2_step: S2UnknownAuthority, instance: ChainInstance
    ) -> None:
        """S2 prompt contains case citation and name."""
        ctx = ChainContext(instance=instance)
        prompt = s2_step.prompt(ctx)

        assert "347 U.S. 483" in prompt
        assert "Brown" in prompt

    def test_prompt_includes_s4_holding(
        self, s2_step: S2UnknownAuthority, instance: ChainInstance
    ) -> None:
        """S2 prompt includes S4 holding if available."""
        ctx = ChainContext(instance=instance)

        # Add S4 result with holding
        from core.schemas.results import StepResult, STATUS_OK

        s4_result = StepResult(
            step_id="s4",
            step="s4",
            status=STATUS_OK,
            prompt="",
            raw_response="",
            parsed={"holding_summary": "Segregation is unconstitutional."},
            ground_truth={},
            score=1.0,
            correct=True,
            model="mock",
        )
        ctx.set("s4", s4_result)

        prompt = s2_step.prompt(ctx)
        assert "Segregation is unconstitutional" in prompt


# =============================================================================
# Test: S2 Parsing
# =============================================================================


class TestS2Parse:
    """Tests for S2 response parsing."""

    def test_parse_valid_json(self, s2_step: S2UnknownAuthority) -> None:
        """Parse valid JSON response with citing cases."""
        response = '''{
            "citing_cases": [
                {"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"},
                {"us_cite": "350 U.S. 497", "case_name": "Some Other Case"}
            ]
        }'''
        parsed = s2_step.parse(response)

        assert len(parsed["citing_cases"]) == 2
        assert parsed["citing_cases"][0]["us_cite"] == "349 U.S. 294"
        assert parsed["citing_cases"][0]["case_name"] == "Bolling v. Sharpe"

    def test_parse_empty_list(self, s2_step: S2UnknownAuthority) -> None:
        """Parse empty citing cases list."""
        response = '{"citing_cases": []}'
        parsed = s2_step.parse(response)

        assert parsed["citing_cases"] == []

    def test_parse_markdown_code_block(self, s2_step: S2UnknownAuthority) -> None:
        """Parse response wrapped in markdown code block."""
        response = '''```json
{
    "citing_cases": [{"us_cite": "349 U.S. 294", "case_name": "Test"}]
}
```'''
        parsed = s2_step.parse(response)

        assert len(parsed["citing_cases"]) == 1

    def test_parse_invalid_json(self, s2_step: S2UnknownAuthority) -> None:
        """Parse failure returns errors."""
        parsed = s2_step.parse("not json")

        assert "errors" in parsed

    def test_parse_missing_case_name(self, s2_step: S2UnknownAuthority) -> None:
        """Parse handles missing case_name."""
        response = '{"citing_cases": [{"us_cite": "349 U.S. 294"}]}'
        parsed = s2_step.parse(response)

        assert parsed["citing_cases"][0]["us_cite"] == "349 U.S. 294"
        assert parsed["citing_cases"][0]["case_name"] == ""


# =============================================================================
# Test: S2 Ground Truth
# =============================================================================


class TestS2GroundTruth:
    """Tests for S2 ground truth from edge."""

    def test_ground_truth_from_edge(
        self, s2_step: S2UnknownAuthority, instance: ChainInstance
    ) -> None:
        """Ground truth uses edge citing case."""
        ctx = ChainContext(instance=instance)
        gt = s2_step.ground_truth(ctx)

        assert gt["citing_case_us_cite"] == "349 U.S. 294"
        assert gt["citing_case_name"] == "Bolling v. Sharpe"


# =============================================================================
# Test: S2 Scoring (MRR and hit@10)
# =============================================================================


class TestS2Scoring:
    """Tests for S2 MRR and hit@k scoring."""

    def test_score_hit_at_1(self, s2_step: S2UnknownAuthority) -> None:
        """Score 1.0 (MRR) when ground truth is first."""
        parsed = {
            "citing_cases": [
                {"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"},
                {"us_cite": "350 U.S. 100", "case_name": "Other"},
            ]
        }
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == 1.0  # MRR = 1/1
        assert correct is True  # hit@10

    def test_score_hit_at_5(self, s2_step: S2UnknownAuthority) -> None:
        """Score 0.2 (MRR) when ground truth is at position 5."""
        parsed = {
            "citing_cases": [
                {"us_cite": "350 U.S. 1", "case_name": "Case 1"},
                {"us_cite": "350 U.S. 2", "case_name": "Case 2"},
                {"us_cite": "350 U.S. 3", "case_name": "Case 3"},
                {"us_cite": "350 U.S. 4", "case_name": "Case 4"},
                {"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"},
            ]
        }
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == pytest.approx(0.2)  # MRR = 1/5
        assert correct is True  # hit@10

    def test_score_hit_at_10(self, s2_step: S2UnknownAuthority) -> None:
        """Score 0.1 (MRR) when ground truth is at position 10."""
        citing_cases = [{"us_cite": f"350 U.S. {i}", "case_name": f"Case {i}"} for i in range(9)]
        citing_cases.append({"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"})

        parsed = {"citing_cases": citing_cases}
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == pytest.approx(0.1)  # MRR = 1/10
        assert correct is True  # hit@10

    def test_score_beyond_10(self, s2_step: S2UnknownAuthority) -> None:
        """correct=False when ground truth is beyond position 10."""
        citing_cases = [{"us_cite": f"350 U.S. {i}", "case_name": f"Case {i}"} for i in range(15)]
        citing_cases.append({"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"})

        parsed = {"citing_cases": citing_cases}
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == pytest.approx(1 / 16)  # MRR = 1/16
        assert correct is False  # NOT hit@10

    def test_score_not_found(self, s2_step: S2UnknownAuthority) -> None:
        """Score 0.0 when ground truth not in predictions."""
        parsed = {
            "citing_cases": [
                {"us_cite": "350 U.S. 1", "case_name": "Case 1"},
                {"us_cite": "350 U.S. 2", "case_name": "Case 2"},
            ]
        }
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_citation_normalization(self, s2_step: S2UnknownAuthority) -> None:
        """Score matches with normalized citations."""
        # Test that "349 U. S. 294" matches "349 U.S. 294"
        parsed = {
            "citing_cases": [
                {"us_cite": "349 U. S. 294", "case_name": "Bolling v. Sharpe"},
            ]
        }
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_parse_error(self, s2_step: S2UnknownAuthority) -> None:
        """Score 0.0 when parsed has errors."""
        parsed = {"errors": ["JSON parse error"]}
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        score, correct = s2_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_extended_metrics_stored(self, s2_step: S2UnknownAuthority) -> None:
        """Extended metrics stored in parsed dict."""
        parsed = {
            "citing_cases": [
                {"us_cite": "350 U.S. 1", "case_name": "Case 1"},
                {"us_cite": "349 U.S. 294", "case_name": "Bolling"},
                {"us_cite": "350 U.S. 2", "case_name": "Case 2"},
            ]
        }
        gt = {"citing_case_us_cite": "349 U.S. 294"}

        s2_step.score(parsed, gt)

        assert "metrics" in parsed
        assert parsed["metrics"]["rank"] == 2
        assert parsed["metrics"]["mrr"] == pytest.approx(0.5)
        assert parsed["metrics"]["hit_at_1"] is False
        assert parsed["metrics"]["hit_at_5"] is True
        assert parsed["metrics"]["hit_at_10"] is True


# =============================================================================
# Test: S2 Execution
# =============================================================================


class TestS2Execution:
    """Tests for S2 execution via ChainExecutor."""

    def test_s2_skipped_without_s1(self, instance: ChainInstance) -> None:
        """S2 skipped when S1 not present."""
        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[S2UnknownAuthority()])

        result = executor.execute(instance)

        assert result.step_results["s2"].status == STATUS_SKIPPED_DEPENDENCY

    def test_s2_executes_after_s1(self, instance: ChainInstance) -> None:
        """S2 executes when S1 dependency satisfied."""
        s1 = StubStep(name="s1", requires=set())
        s2 = S2UnknownAuthority()

        backend = MockBackend(
            default_response='{"citing_cases": [{"us_cite": "349 U.S. 294", "case_name": "Bolling"}]}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s2])

        result = executor.execute(instance)

        assert result.step_results["s1"].status == STATUS_OK
        assert result.step_results["s2"].status == STATUS_OK

    def test_s2_correct_with_hit_at_1(self, instance: ChainInstance) -> None:
        """S2 scores correct when ground truth is first in predictions."""
        s1 = StubStep(name="s1", requires=set())
        s2 = S2UnknownAuthority()

        # Response has ground truth first
        backend = MockBackend(
            default_response='{"citing_cases": [{"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"}]}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s2])

        result = executor.execute(instance)

        assert result.step_results["s2"].correct is True
        assert result.step_results["s2"].score == 1.0
