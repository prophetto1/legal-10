"""Tests for S6 IRAC Synthesis step - Phase 7.

Exit Criteria:
- S6 synthesizes outputs from S1-S5
- Rubric scorer produces 0.0-1.0 scores
- S6 correctly skipped when dependencies not satisfied
- S7 void retroactively updates S6 scores
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s6_irac_synthesis import S6IRACSynthesis
from chain.steps.s7_citation_integrity import S7CitationIntegrity
from chain.steps.stub_step import StubStep
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import STATUS_OK, STATUS_SKIPPED_DEPENDENCY
from core.scoring.irac_rubric import (
    score_irac_presence,
    score_irac_quality,
    is_irac_correct,
    get_missing_components,
    format_rubric_feedback,
    MIN_COMPONENT_LENGTH,
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
        majority_opinion="We conclude that in the field of public education...",
    )


@pytest.fixture
def edge() -> ShepardsEdge:
    """Standard edge."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
        cited_case_name="Brown v. Board of Education",
        citing_case_name="Bolling v. Sharpe",
        agree=True,
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
def s6_step() -> S6IRACSynthesis:
    """S6 step instance."""
    return S6IRACSynthesis()


@pytest.fixture
def full_irac_response() -> str:
    """Complete IRAC response."""
    return '''{
        "issue": "Whether segregation in public schools violates the Equal Protection Clause of the Fourteenth Amendment.",
        "rule": "The Equal Protection Clause requires that similarly situated individuals be treated equally under the law.",
        "application": "The Court found that separate educational facilities are inherently unequal, causing psychological harm to minority students. Even if physical facilities were equal, the separation itself creates a sense of inferiority.",
        "conclusion": "Segregation in public education is unconstitutional. The doctrine of separate but equal has no place in public education."
    }'''


@pytest.fixture
def partial_irac_response() -> str:
    """Partial IRAC response (missing conclusion)."""
    return '''{
        "issue": "Whether segregation in public schools violates the Equal Protection Clause.",
        "rule": "The Equal Protection Clause requires equal treatment under the law.",
        "application": "Separate educational facilities are inherently unequal.",
        "conclusion": ""
    }'''


# =============================================================================
# Test: S6 Properties
# =============================================================================


class TestS6Properties:
    """Tests for S6 step properties."""

    def test_step_id(self, s6_step: S6IRACSynthesis) -> None:
        """S6 has correct step_id."""
        assert s6_step.step_id == "s6"

    def test_step_name(self, s6_step: S6IRACSynthesis) -> None:
        """S6 has correct step_name."""
        assert s6_step.step_name == "s6"

    def test_requires_all_prior_steps(self, s6_step: S6IRACSynthesis) -> None:
        """S6 requires S1, S2, S3, S4, S5:cb."""
        assert s6_step.requires() == {"s1", "s2", "s3", "s4", "s5:cb"}


# =============================================================================
# Test: S6 Coverage
# =============================================================================


class TestS6Coverage:
    """Tests for S6 coverage requirements."""

    def test_coverage_with_cited_text(
        self, s6_step: S6IRACSynthesis, instance: ChainInstance
    ) -> None:
        """S6 has coverage when cited case has opinion."""
        ctx = ChainContext(instance=instance)
        assert s6_step.check_coverage(ctx) is True

    def test_coverage_without_cited_text(self, s6_step: S6IRACSynthesis) -> None:
        """S6 lacks coverage without cited case opinion."""
        cited = CourtCase(
            us_cite="347 U.S. 483",
            case_name="Brown v. Board of Education",
            term=1954,
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
        assert s6_step.check_coverage(ctx) is False


# =============================================================================
# Test: S6 Prompt
# =============================================================================


class TestS6Prompt:
    """Tests for S6 prompt generation."""

    def test_prompt_contains_case_metadata(
        self, s6_step: S6IRACSynthesis, instance: ChainInstance
    ) -> None:
        """S6 prompt contains case citation and name."""
        ctx = ChainContext(instance=instance)
        prompt = s6_step.prompt(ctx)

        assert "347 U.S. 483" in prompt
        assert "Brown" in prompt
        assert "1954" in prompt

    def test_prompt_includes_prior_step_results(
        self, s6_step: S6IRACSynthesis, instance: ChainInstance
    ) -> None:
        """S6 prompt includes results from S2, S3, S4, S5:cb."""
        ctx = ChainContext(instance=instance)

        # Add mock results from prior steps
        from core.schemas.results import StepResult, STATUS_OK

        s4_result = StepResult(
            step_id="s4", step="s4", status=STATUS_OK,
            prompt="", raw_response="",
            parsed={
                "disposition": "reversed",
                "party_winning": "petitioner",
                "holding_summary": "Segregation is unconstitutional.",
            },
            ground_truth={}, score=1.0, correct=True, model="mock",
        )
        ctx.set("s4", s4_result)

        s3_result = StepResult(
            step_id="s3", step="s3", status=STATUS_OK,
            prompt="", raw_response="",
            parsed={"is_overruled": False},
            ground_truth={}, score=1.0, correct=True, model="mock",
        )
        ctx.set("s3", s3_result)

        s5_result = StepResult(
            step_id="s5:cb", step="s5", status=STATUS_OK,
            prompt="", raw_response="",
            parsed={"agrees": True, "reasoning": "Case follows precedent."},
            ground_truth={}, score=1.0, correct=True, model="mock",
        )
        ctx.set("s5:cb", s5_result)

        s2_result = StepResult(
            step_id="s2", step="s2", status=STATUS_OK,
            prompt="", raw_response="",
            parsed={"citing_cases": [{"us_cite": "349 U.S. 294", "case_name": "Bolling v. Sharpe"}]},
            ground_truth={}, score=1.0, correct=True, model="mock",
        )
        ctx.set("s2", s2_result)

        prompt = s6_step.prompt(ctx)

        # S4 content
        assert "reversed" in prompt
        assert "petitioner" in prompt
        assert "Segregation is unconstitutional" in prompt

        # S3 content
        assert "good law" in prompt or "not overruled" in prompt

        # S5 content
        assert "AGREES" in prompt

        # S2 content
        assert "Bolling v. Sharpe" in prompt


# =============================================================================
# Test: S6 Parsing
# =============================================================================


class TestS6Parse:
    """Tests for S6 response parsing."""

    def test_parse_complete_irac(
        self, s6_step: S6IRACSynthesis, full_irac_response: str
    ) -> None:
        """Parse complete IRAC response."""
        parsed = s6_step.parse(full_irac_response)

        assert "Whether segregation" in parsed["issue"]
        assert "Equal Protection" in parsed["rule"]
        assert "inherently unequal" in parsed["application"]
        assert "unconstitutional" in parsed["conclusion"]

    def test_parse_partial_irac(
        self, s6_step: S6IRACSynthesis, partial_irac_response: str
    ) -> None:
        """Parse partial IRAC response."""
        parsed = s6_step.parse(partial_irac_response)

        assert parsed["issue"] != ""
        assert parsed["rule"] != ""
        assert parsed["application"] != ""
        assert parsed["conclusion"] == ""

    def test_parse_markdown_code_block(self, s6_step: S6IRACSynthesis) -> None:
        """Parse response wrapped in markdown code block."""
        response = '''```json
{
    "issue": "Test issue question here.",
    "rule": "Test rule statement here.",
    "application": "Test application analysis here.",
    "conclusion": "Test conclusion statement."
}
```'''
        parsed = s6_step.parse(response)

        assert parsed["issue"] == "Test issue question here."

    def test_parse_invalid_json(self, s6_step: S6IRACSynthesis) -> None:
        """Parse failure returns errors."""
        parsed = s6_step.parse("not json")

        assert "errors" in parsed


# =============================================================================
# Test: S6 Ground Truth
# =============================================================================


class TestS6GroundTruth:
    """Tests for S6 ground truth (rubric-based)."""

    def test_ground_truth_is_rubric_based(
        self, s6_step: S6IRACSynthesis, instance: ChainInstance
    ) -> None:
        """Ground truth indicates rubric-based scoring."""
        ctx = ChainContext(instance=instance)
        gt = s6_step.ground_truth(ctx)

        assert gt["rubric"] == "irac_presence"
        assert "issue" in gt["components"]
        assert "rule" in gt["components"]
        assert "application" in gt["components"]
        assert "conclusion" in gt["components"]


# =============================================================================
# Test: S6 Scoring
# =============================================================================


class TestS6Scoring:
    """Tests for S6 IRAC rubric scoring."""

    def test_score_complete_irac(self, s6_step: S6IRACSynthesis) -> None:
        """Score 1.0 when all IRAC components present."""
        parsed = {
            "issue": "Whether segregation violates Equal Protection.",
            "rule": "The Equal Protection Clause requires equal treatment.",
            "application": "Separate facilities are inherently unequal.",
            "conclusion": "Segregation is unconstitutional in education.",
        }
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_three_components(self, s6_step: S6IRACSynthesis) -> None:
        """Score 0.75 when 3 components present (still correct)."""
        parsed = {
            "issue": "Whether segregation violates Equal Protection.",
            "rule": "The Equal Protection Clause requires equal treatment.",
            "application": "Separate facilities are inherently unequal.",
            "conclusion": "",  # Missing
        }
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 0.75
        assert correct is True

    def test_score_two_components(self, s6_step: S6IRACSynthesis) -> None:
        """Score 0.5 when 2 components present (not correct)."""
        parsed = {
            "issue": "Whether segregation violates Equal Protection.",
            "rule": "The Equal Protection Clause requires equal treatment.",
            "application": "",  # Missing
            "conclusion": "",  # Missing
        }
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 0.5
        assert correct is False

    def test_score_one_component(self, s6_step: S6IRACSynthesis) -> None:
        """Score 0.25 when 1 component present."""
        parsed = {
            "issue": "Whether segregation violates Equal Protection.",
            "rule": "",
            "application": "",
            "conclusion": "",
        }
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 0.25
        assert correct is False

    def test_score_no_components(self, s6_step: S6IRACSynthesis) -> None:
        """Score 0.0 when no components present."""
        parsed = {
            "issue": "",
            "rule": "",
            "application": "",
            "conclusion": "",
        }
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_short_components_not_counted(
        self, s6_step: S6IRACSynthesis
    ) -> None:
        """Components shorter than MIN_COMPONENT_LENGTH not counted."""
        parsed = {
            "issue": "Short",  # Too short
            "rule": "This is a proper rule statement with enough characters.",
            "application": "X",  # Too short
            "conclusion": "Y",  # Too short
        }
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 0.25  # Only rule counts
        assert correct is False

    def test_score_parse_error(self, s6_step: S6IRACSynthesis) -> None:
        """Score 0.0 when parsed has errors."""
        parsed = {"errors": ["JSON parse error"]}
        gt = {"rubric": "irac_presence"}

        score, correct = s6_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False


# =============================================================================
# Test: IRAC Rubric Module
# =============================================================================


class TestIRACRubric:
    """Tests for core/scoring/irac_rubric.py module."""

    def test_score_irac_presence_complete(self) -> None:
        """score_irac_presence returns 1.0 for complete IRAC."""
        parsed = {
            "issue": "A sufficiently long issue statement.",
            "rule": "A sufficiently long rule statement.",
            "application": "A sufficiently long application.",
            "conclusion": "A sufficiently long conclusion.",
        }
        score, present = score_irac_presence(parsed)

        assert score == 1.0
        assert all(present.values())

    def test_score_irac_presence_partial(self) -> None:
        """score_irac_presence handles partial IRAC."""
        parsed = {
            "issue": "A sufficiently long issue statement.",
            "rule": "",
            "application": "A sufficiently long application.",
            "conclusion": "",
        }
        score, present = score_irac_presence(parsed)

        assert score == 0.5
        assert present["issue"] is True
        assert present["rule"] is False
        assert present["application"] is True
        assert present["conclusion"] is False

    def test_is_irac_correct_threshold(self) -> None:
        """is_irac_correct uses threshold correctly."""
        assert is_irac_correct(1.0) is True
        assert is_irac_correct(0.75) is True
        assert is_irac_correct(0.74) is False
        assert is_irac_correct(0.5) is False

    def test_get_missing_components(self) -> None:
        """get_missing_components identifies missing parts."""
        parsed = {
            "issue": "A sufficiently long issue statement.",
            "rule": "",
            "application": "A sufficiently long application.",
            "conclusion": "short",  # Too short
        }
        missing = get_missing_components(parsed)

        assert "rule" in missing
        assert "conclusion" in missing
        assert "issue" not in missing
        assert "application" not in missing

    def test_format_rubric_feedback(self) -> None:
        """format_rubric_feedback generates readable output."""
        parsed = {
            "issue": "A sufficiently long issue statement.",
            "rule": "A sufficiently long rule statement.",
            "application": "",
            "conclusion": "",
        }
        feedback = format_rubric_feedback(parsed)

        assert "IRAC Score: 50%" in feedback
        assert "[OK] ISSUE" in feedback
        assert "[OK] RULE" in feedback
        assert "[MISSING] APPLICATION" in feedback
        assert "[MISSING] CONCLUSION" in feedback


# =============================================================================
# Test: S6 Execution
# =============================================================================


class TestS6Execution:
    """Tests for S6 execution via ChainExecutor."""

    def test_s6_skipped_without_dependencies(self, instance: ChainInstance) -> None:
        """S6 skipped when required steps not present."""
        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[S6IRACSynthesis()])

        result = executor.execute(instance)

        assert result.step_results["s6"].status == STATUS_SKIPPED_DEPENDENCY

    def test_s6_skipped_partial_dependencies(self, instance: ChainInstance) -> None:
        """S6 skipped when only some dependencies satisfied."""
        s1 = StubStep(name="s1", requires=set())
        s4 = StubStep(name="s4", requires={"s1"})
        s6 = S6IRACSynthesis()

        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[s1, s4, s6])

        result = executor.execute(instance)

        # S6 should be skipped because S2, S3, S5:cb are missing
        assert result.step_results["s6"].status == STATUS_SKIPPED_DEPENDENCY

    def test_s6_executes_with_all_dependencies(self, instance: ChainInstance) -> None:
        """S6 executes when all dependencies satisfied."""
        s1 = StubStep(name="s1", requires=set())
        s2 = StubStep(name="s2", requires={"s1"})
        s3 = StubStep(name="s3", requires={"s1"})
        s4 = StubStep(name="s4", requires={"s1"})
        s5_cb = StubStep(name="s5:cb", requires={"s1", "s4"})
        s6 = S6IRACSynthesis()

        backend = MockBackend(
            default_response='''{
                "issue": "Whether segregation violates Equal Protection.",
                "rule": "Equal Protection requires equal treatment.",
                "application": "Separate facilities are unequal.",
                "conclusion": "Segregation is unconstitutional."
            }'''
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s2, s3, s4, s5_cb, s6])

        result = executor.execute(instance)

        assert result.step_results["s6"].status == STATUS_OK
        assert result.step_results["s6"].score == 1.0
        assert result.step_results["s6"].correct is True


# =============================================================================
# Test: S7 Voiding S6
# =============================================================================


class TestS7VoidingS6:
    """Tests for S7 voiding S6 when citation integrity fails."""

    def test_s7_correct_does_not_void_s6(self, instance: ChainInstance) -> None:
        """S7 correct=True does not void S6."""
        s1 = StubStep(name="s1", requires=set())
        s2 = StubStep(name="s2", requires={"s1"})
        s3 = StubStep(name="s3", requires={"s1"})
        s4 = StubStep(name="s4", requires={"s1"})
        s5_cb = StubStep(name="s5:cb", requires={"s1", "s4"})
        s6 = StubStep(
            name="s6",
            requires={"s1", "s2", "s3", "s4", "s5:cb"},
            parsed_response={
                "issue": "Test issue statement here.",
                "rule": "Test rule here with citation 347 U.S. 483.",
                "application": "Application analysis here.",
                "conclusion": "Conclusion statement here.",
            },
        )
        s7 = S7CitationIntegrity()
        s7.set_verification_sets(
            fake_us_cites=set(),  # No fakes
            scdb_us_cites={"347 U.S. 483": "Brown v. Board"},
        )

        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[s1, s2, s3, s4, s5_cb, s6, s7])

        result = executor.execute(instance)

        # S7 should be correct (citation is real)
        assert result.step_results["s7"].correct is True

        # S6 should NOT be voided
        assert result.step_results["s6"].voided is False
        assert result.voided is False

    def test_s7_incorrect_voids_s6(self, instance: ChainInstance) -> None:
        """S7 correct=False voids S6."""
        s1 = StubStep(name="s1", requires=set())
        s2 = StubStep(name="s2", requires={"s1"})
        s3 = StubStep(name="s3", requires={"s1"})
        s4 = StubStep(name="s4", requires={"s1"})
        s5_cb = StubStep(name="s5:cb", requires={"s1", "s4"})
        s6 = StubStep(
            name="s6",
            requires={"s1", "s2", "s3", "s4", "s5:cb"},
            parsed_response={
                "issue": "Test issue statement here.",
                "rule": "Test rule citing 999 U.S. 999.",  # Fake citation!
                "application": "Application analysis here.",
                "conclusion": "Conclusion statement here.",
            },
        )
        # Use StubStep with always_correct=False to simulate S7 detecting fake citation
        # (S7 verification is deterministic, so we simulate the outcome)
        s7 = StubStep(
            name="s7",
            requires={"s6"},
            always_correct=False,  # This triggers voiding
            parsed_response={
                "citations_found": [{"cite": "999 U.S. 999", "exists": False}],
                "all_valid": False,
            },
        )

        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[s1, s2, s3, s4, s5_cb, s6, s7])

        result = executor.execute(instance)

        # S7 should be incorrect (fake citation detected)
        assert result.step_results["s7"].correct is False

        # S6 should be voided
        assert result.step_results["s6"].voided is True
        assert result.step_results["s6"].void_reason == "S7 citation integrity gate failed"
        assert result.voided is True
