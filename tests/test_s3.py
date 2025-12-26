"""Tests for S3 Validate Authority step - Phase 6.

Exit Criteria:
- S3 checks if case has been overruled
- S3 ground truth from OverruleRecord
- S3 scoring matches is_overruled exactly
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s3_validate_authority import S3ValidateAuthority
from chain.steps.stub_step import StubStep
from core.schemas.case import CourtCase, ShepardsEdge, OverruleRecord
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import STATUS_OK, STATUS_SKIPPED_DEPENDENCY


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cited_case() -> CourtCase:
    """Cited case with opinion."""
    return CourtCase(
        us_cite="198 U.S. 45",
        case_name="Lochner v. New York",
        term=1905,
        majority_opinion="The general right to make a contract...",
    )


@pytest.fixture
def overrule_record() -> OverruleRecord:
    """Overrule record for Lochner."""
    return OverruleRecord(
        overruled_case_us_id="198 U.S. 45",
        overruled_case_name="Lochner v. New York",
        overruling_case_name="West Coast Hotel Co. v. Parrish",
        year_overruled=1937,
        overruled_in_full=True,
    )


@pytest.fixture
def edge() -> ShepardsEdge:
    """Standard edge."""
    return ShepardsEdge(
        cited_case_us_cite="198 U.S. 45",
        citing_case_us_cite="300 U.S. 379",
    )


@pytest.fixture
def instance_overruled(
    cited_case: CourtCase, edge: ShepardsEdge, overrule_record: OverruleRecord
) -> ChainInstance:
    """Instance with overruled case."""
    return ChainInstance(
        id="pair::198_us_45::300_us_379",
        cited_case=cited_case,
        edge=edge,
        overrule=overrule_record,
    )


@pytest.fixture
def instance_not_overruled(cited_case: CourtCase, edge: ShepardsEdge) -> ChainInstance:
    """Instance with case that was NOT overruled."""
    # Use Brown v. Board - not overruled
    cited = CourtCase(
        us_cite="347 U.S. 483",
        case_name="Brown v. Board of Education",
        term=1954,
        majority_opinion="We conclude that segregation is unconstitutional...",
    )
    edge = ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
    )
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited,
        edge=edge,
        overrule=None,  # Not overruled
    )


@pytest.fixture
def s3_step() -> S3ValidateAuthority:
    """S3 step instance."""
    return S3ValidateAuthority()


# =============================================================================
# Test: S3 Properties
# =============================================================================


class TestS3Properties:
    """Tests for S3 step properties."""

    def test_step_id(self, s3_step: S3ValidateAuthority) -> None:
        """S3 has correct step_id."""
        assert s3_step.step_id == "s3"

    def test_step_name(self, s3_step: S3ValidateAuthority) -> None:
        """S3 has correct step_name."""
        assert s3_step.step_name == "s3"

    def test_requires_s1(self, s3_step: S3ValidateAuthority) -> None:
        """S3 requires S1."""
        assert s3_step.requires() == {"s1"}


# =============================================================================
# Test: S3 Coverage
# =============================================================================


class TestS3Coverage:
    """Tests for S3 coverage requirements."""

    def test_coverage_with_cited_text(
        self, s3_step: S3ValidateAuthority, instance_overruled: ChainInstance
    ) -> None:
        """S3 has coverage when cited case has opinion."""
        ctx = ChainContext(instance=instance_overruled)
        assert s3_step.check_coverage(ctx) is True

    def test_coverage_without_cited_text(self, s3_step: S3ValidateAuthority) -> None:
        """S3 lacks coverage without cited case opinion."""
        cited = CourtCase(
            us_cite="198 U.S. 45",
            case_name="Lochner v. New York",
            term=1905,
            # No majority_opinion
        )
        edge = ShepardsEdge(
            cited_case_us_cite="198 U.S. 45",
            citing_case_us_cite="300 U.S. 379",
        )
        instance = ChainInstance(
            id="pair::198_us_45::300_us_379",
            cited_case=cited,
            edge=edge,
        )
        ctx = ChainContext(instance=instance)
        assert s3_step.check_coverage(ctx) is False


# =============================================================================
# Test: S3 Prompt
# =============================================================================


class TestS3Prompt:
    """Tests for S3 prompt generation."""

    def test_prompt_contains_case_metadata(
        self, s3_step: S3ValidateAuthority, instance_overruled: ChainInstance
    ) -> None:
        """S3 prompt contains case citation, name, and term."""
        ctx = ChainContext(instance=instance_overruled)
        prompt = s3_step.prompt(ctx)

        assert "198 U.S. 45" in prompt
        assert "Lochner" in prompt
        assert "1905" in prompt

    def test_prompt_asks_about_overruling(
        self, s3_step: S3ValidateAuthority, instance_overruled: ChainInstance
    ) -> None:
        """S3 prompt asks about overruling."""
        ctx = ChainContext(instance=instance_overruled)
        prompt = s3_step.prompt(ctx)

        assert "overruled" in prompt.lower()


# =============================================================================
# Test: S3 Parsing
# =============================================================================


class TestS3Parse:
    """Tests for S3 response parsing."""

    def test_parse_overruled(self, s3_step: S3ValidateAuthority) -> None:
        """Parse overruled response."""
        response = '''{
            "is_overruled": true,
            "overruling_case": "West Coast Hotel Co. v. Parrish",
            "year_overruled": 1937
        }'''
        parsed = s3_step.parse(response)

        assert parsed["is_overruled"] is True
        assert parsed["overruling_case"] == "West Coast Hotel Co. v. Parrish"
        assert parsed["year_overruled"] == 1937

    def test_parse_not_overruled(self, s3_step: S3ValidateAuthority) -> None:
        """Parse not-overruled response."""
        response = '''{
            "is_overruled": false,
            "overruling_case": null,
            "year_overruled": null
        }'''
        parsed = s3_step.parse(response)

        assert parsed["is_overruled"] is False
        assert parsed["overruling_case"] is None
        assert parsed["year_overruled"] is None

    def test_parse_string_true(self, s3_step: S3ValidateAuthority) -> None:
        """Parse is_overruled as string 'true'."""
        response = '{"is_overruled": "true", "overruling_case": null, "year_overruled": null}'
        parsed = s3_step.parse(response)

        assert parsed["is_overruled"] is True

    def test_parse_string_false(self, s3_step: S3ValidateAuthority) -> None:
        """Parse is_overruled as string 'false'."""
        response = '{"is_overruled": "false", "overruling_case": null, "year_overruled": null}'
        parsed = s3_step.parse(response)

        assert parsed["is_overruled"] is False

    def test_parse_year_as_string(self, s3_step: S3ValidateAuthority) -> None:
        """Parse year_overruled as string."""
        response = '{"is_overruled": true, "overruling_case": "Test", "year_overruled": "1937"}'
        parsed = s3_step.parse(response)

        assert parsed["year_overruled"] == 1937

    def test_parse_markdown_code_block(self, s3_step: S3ValidateAuthority) -> None:
        """Parse response wrapped in markdown code block."""
        response = '''```json
{
    "is_overruled": true,
    "overruling_case": "West Coast Hotel",
    "year_overruled": 1937
}
```'''
        parsed = s3_step.parse(response)

        assert parsed["is_overruled"] is True

    def test_parse_invalid_json(self, s3_step: S3ValidateAuthority) -> None:
        """Parse failure returns errors."""
        parsed = s3_step.parse("not json")

        assert "errors" in parsed


# =============================================================================
# Test: S3 Ground Truth
# =============================================================================


class TestS3GroundTruth:
    """Tests for S3 ground truth from OverruleRecord."""

    def test_ground_truth_overruled(
        self, s3_step: S3ValidateAuthority, instance_overruled: ChainInstance
    ) -> None:
        """Ground truth reflects overruled case."""
        ctx = ChainContext(instance=instance_overruled)
        gt = s3_step.ground_truth(ctx)

        assert gt["is_overruled"] is True
        assert gt["overruling_case"] == "West Coast Hotel Co. v. Parrish"
        assert gt["year_overruled"] == 1937

    def test_ground_truth_not_overruled(
        self, s3_step: S3ValidateAuthority, instance_not_overruled: ChainInstance
    ) -> None:
        """Ground truth reflects not-overruled case."""
        ctx = ChainContext(instance=instance_not_overruled)
        gt = s3_step.ground_truth(ctx)

        assert gt["is_overruled"] is False
        assert gt["overruling_case"] is None
        assert gt["year_overruled"] is None


# =============================================================================
# Test: S3 Scoring
# =============================================================================


class TestS3Scoring:
    """Tests for S3 scoring - is_overruled must match exactly."""

    def test_score_correct_overruled(self, s3_step: S3ValidateAuthority) -> None:
        """Score 1.0 when is_overruled=True matches ground truth."""
        parsed = {
            "is_overruled": True,
            "overruling_case": "West Coast Hotel Co. v. Parrish",
            "year_overruled": 1937,
        }
        gt = {"is_overruled": True}

        score, correct = s3_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_correct_not_overruled(self, s3_step: S3ValidateAuthority) -> None:
        """Score 1.0 when is_overruled=False matches ground truth."""
        parsed = {
            "is_overruled": False,
            "overruling_case": None,
            "year_overruled": None,
        }
        gt = {"is_overruled": False}

        score, correct = s3_step.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_false_positive(self, s3_step: S3ValidateAuthority) -> None:
        """Score 0.0 for false positive (predicted overruled, actually not)."""
        parsed = {
            "is_overruled": True,
            "overruling_case": "Some Case",
            "year_overruled": 1950,
        }
        gt = {"is_overruled": False}

        score, correct = s3_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_false_negative(self, s3_step: S3ValidateAuthority) -> None:
        """Score 0.0 for false negative (predicted not overruled, actually was)."""
        parsed = {
            "is_overruled": False,
            "overruling_case": None,
            "year_overruled": None,
        }
        gt = {"is_overruled": True}

        score, correct = s3_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_parse_error(self, s3_step: S3ValidateAuthority) -> None:
        """Score 0.0 when parsed has errors."""
        parsed = {"errors": ["JSON parse error"]}
        gt = {"is_overruled": True}

        score, correct = s3_step.score(parsed, gt)

        assert score == 0.0
        assert correct is False


# =============================================================================
# Test: S3 Execution
# =============================================================================


class TestS3Execution:
    """Tests for S3 execution via ChainExecutor."""

    def test_s3_skipped_without_s1(self, instance_overruled: ChainInstance) -> None:
        """S3 skipped when S1 not present."""
        backend = MockBackend()
        executor = ChainExecutor(backend=backend, steps=[S3ValidateAuthority()])

        result = executor.execute(instance_overruled)

        assert result.step_results["s3"].status == STATUS_SKIPPED_DEPENDENCY

    def test_s3_executes_after_s1(self, instance_overruled: ChainInstance) -> None:
        """S3 executes when S1 dependency satisfied."""
        s1 = StubStep(name="s1", requires=set())
        s3 = S3ValidateAuthority()

        backend = MockBackend(
            default_response='{"is_overruled": true, "overruling_case": "West Coast Hotel", "year_overruled": 1937}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s3])

        result = executor.execute(instance_overruled)

        assert result.step_results["s1"].status == STATUS_OK
        assert result.step_results["s3"].status == STATUS_OK

    def test_s3_correct_overruled(self, instance_overruled: ChainInstance) -> None:
        """S3 scores correct when overruled response matches ground truth."""
        s1 = StubStep(name="s1", requires=set())
        s3 = S3ValidateAuthority()

        backend = MockBackend(
            default_response='{"is_overruled": true, "overruling_case": "West Coast Hotel", "year_overruled": 1937}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s3])

        result = executor.execute(instance_overruled)

        assert result.step_results["s3"].correct is True
        assert result.step_results["s3"].score == 1.0

    def test_s3_correct_not_overruled(
        self, instance_not_overruled: ChainInstance
    ) -> None:
        """S3 scores correct when not-overruled response matches ground truth."""
        s1 = StubStep(name="s1", requires=set())
        s3 = S3ValidateAuthority()

        backend = MockBackend(
            default_response='{"is_overruled": false, "overruling_case": null, "year_overruled": null}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s3])

        result = executor.execute(instance_not_overruled)

        assert result.step_results["s3"].correct is True
        assert result.step_results["s3"].score == 1.0
