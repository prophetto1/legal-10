"""Tests for S5 Distinguish steps - Phase 5.

Exit Criteria:
- S5:cb uses metadata + S4 only (no citing text)
- S5:rag uses citing text (Tier B)
- S5 scoring matches edge.agree ground truth
- Variants stored separately
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.s5_distinguish import S5DistinguishCB, S5DistinguishRAG
from chain.steps.stub_step import StubStep
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import STATUS_OK, STATUS_SKIPPED_COVERAGE, STATUS_SKIPPED_DEPENDENCY


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
def citing_case_with_opinion() -> CourtCase:
    """Citing case with opinion (Tier B)."""
    return CourtCase(
        us_cite="349 U.S. 294",
        case_name="Bolling v. Sharpe",
        term=1954,
        majority_opinion="Following Brown, we hold that segregation in DC schools...",
    )


@pytest.fixture
def citing_case_no_opinion() -> CourtCase:
    """Citing case without opinion."""
    return CourtCase(
        us_cite="349 U.S. 294",
        case_name="Bolling v. Sharpe",
        term=1954,
        # No majority_opinion
    )


@pytest.fixture
def edge_agrees() -> ShepardsEdge:
    """Edge where citing case agrees."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
        cited_case_name="Brown v. Board of Education",
        citing_case_name="Bolling v. Sharpe",
        shepards="followed",
        agree=True,
    )


@pytest.fixture
def edge_distinguishes() -> ShepardsEdge:
    """Edge where citing case distinguishes."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
        cited_case_name="Brown v. Board of Education",
        citing_case_name="Different Case",
        shepards="distinguished",
        agree=False,
    )


@pytest.fixture
def instance_tier_b(
    cited_case: CourtCase,
    citing_case_with_opinion: CourtCase,
    edge_agrees: ShepardsEdge,
) -> ChainInstance:
    """Instance with both case opinions (Tier A + B)."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case,
        citing_case=citing_case_with_opinion,
        edge=edge_agrees,
    )


@pytest.fixture
def instance_tier_a_only(
    cited_case: CourtCase,
    citing_case_no_opinion: CourtCase,
    edge_agrees: ShepardsEdge,
) -> ChainInstance:
    """Instance with only cited case opinion (Tier A only)."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case,
        citing_case=citing_case_no_opinion,
        edge=edge_agrees,
    )


@pytest.fixture
def instance_distinguishes(
    cited_case: CourtCase,
    citing_case_with_opinion: CourtCase,
    edge_distinguishes: ShepardsEdge,
) -> ChainInstance:
    """Instance where citing case distinguishes."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case,
        citing_case=citing_case_with_opinion,
        edge=edge_distinguishes,
    )


# =============================================================================
# Test: S5:cb Properties
# =============================================================================


class TestS5CBProperties:
    """Tests for S5:cb step properties."""

    def test_step_id(self) -> None:
        """S5:cb has correct step_id."""
        s5 = S5DistinguishCB()
        assert s5.step_id == "s5:cb"

    def test_step_name(self) -> None:
        """S5:cb has correct step_name (s5)."""
        s5 = S5DistinguishCB()
        assert s5.step_name == "s5"

    def test_requires_s1_and_s4(self) -> None:
        """S5:cb requires S1 and S4."""
        s5 = S5DistinguishCB()
        assert s5.requires() == {"s1", "s4"}

    def test_variant_extracted(self) -> None:
        """S5:cb extracts variant 'cb'."""
        s5 = S5DistinguishCB()
        assert s5._extract_variant() == "cb"


# =============================================================================
# Test: S5:rag Properties
# =============================================================================


class TestS5RAGProperties:
    """Tests for S5:rag step properties."""

    def test_step_id(self) -> None:
        """S5:rag has correct step_id."""
        s5 = S5DistinguishRAG()
        assert s5.step_id == "s5:rag"

    def test_step_name(self) -> None:
        """S5:rag has correct step_name (s5)."""
        s5 = S5DistinguishRAG()
        assert s5.step_name == "s5"

    def test_requires_s1_and_s4(self) -> None:
        """S5:rag requires S1 and S4."""
        s5 = S5DistinguishRAG()
        assert s5.requires() == {"s1", "s4"}

    def test_variant_extracted(self) -> None:
        """S5:rag extracts variant 'rag'."""
        s5 = S5DistinguishRAG()
        assert s5._extract_variant() == "rag"


# =============================================================================
# Test: S5:cb Coverage (No Citing Text Required)
# =============================================================================


class TestS5CBCoverage:
    """Tests for S5:cb coverage - only needs Tier A."""

    def test_coverage_tier_a_only(
        self, instance_tier_a_only: ChainInstance
    ) -> None:
        """S5:cb has coverage even without citing opinion."""
        s5 = S5DistinguishCB()
        ctx = ChainContext(instance=instance_tier_a_only)

        assert s5.check_coverage(ctx) is True

    def test_coverage_tier_b(self, instance_tier_b: ChainInstance) -> None:
        """S5:cb has coverage with both opinions."""
        s5 = S5DistinguishCB()
        ctx = ChainContext(instance=instance_tier_b)

        assert s5.check_coverage(ctx) is True


# =============================================================================
# Test: S5:rag Coverage (Citing Text Required)
# =============================================================================


class TestS5RAGCoverage:
    """Tests for S5:rag coverage - needs Tier A + B."""

    def test_coverage_tier_a_only_fails(
        self, instance_tier_a_only: ChainInstance
    ) -> None:
        """S5:rag lacks coverage without citing opinion."""
        s5 = S5DistinguishRAG()
        ctx = ChainContext(instance=instance_tier_a_only)

        assert s5.check_coverage(ctx) is False

    def test_coverage_tier_b_succeeds(
        self, instance_tier_b: ChainInstance
    ) -> None:
        """S5:rag has coverage with both opinions."""
        s5 = S5DistinguishRAG()
        ctx = ChainContext(instance=instance_tier_b)

        assert s5.check_coverage(ctx) is True


# =============================================================================
# Test: S5:cb Prompt (Metadata Only)
# =============================================================================


class TestS5CBPrompt:
    """Tests for S5:cb prompt - uses metadata only."""

    def test_prompt_contains_case_metadata(
        self, instance_tier_a_only: ChainInstance
    ) -> None:
        """S5:cb prompt contains case metadata."""
        s5 = S5DistinguishCB()
        ctx = ChainContext(instance=instance_tier_a_only)

        # Add stub S4 result
        s4_result = StubStep(name="s4", parsed_response={
            "disposition": "reversed",
            "party_winning": "petitioner",
            "holding_summary": "Segregation is unconstitutional.",
        }).create_result(
            prompt="", raw_response="", parsed={
                "disposition": "reversed",
                "party_winning": "petitioner",
                "holding_summary": "Segregation is unconstitutional.",
            },
            ground_truth={}, score=1.0, correct=True, model="mock"
        )
        ctx.set("s4", s4_result)

        prompt = s5.prompt(ctx)

        assert "347 U.S. 483" in prompt
        assert "Brown" in prompt
        assert "reversed" in prompt

    def test_prompt_no_citing_opinion(
        self, instance_tier_b: ChainInstance
    ) -> None:
        """S5:cb prompt does NOT contain citing opinion text."""
        s5 = S5DistinguishCB()
        ctx = ChainContext(instance=instance_tier_b)
        prompt = s5.prompt(ctx)

        # Should not contain the citing opinion content
        assert "Following Brown" not in prompt


# =============================================================================
# Test: S5:rag Prompt (With Citing Opinion)
# =============================================================================


class TestS5RAGPrompt:
    """Tests for S5:rag prompt - includes citing opinion."""

    def test_prompt_contains_citing_opinion(
        self, instance_tier_b: ChainInstance
    ) -> None:
        """S5:rag prompt contains citing opinion text."""
        s5 = S5DistinguishRAG()
        ctx = ChainContext(instance=instance_tier_b)
        prompt = s5.prompt(ctx)

        # Should contain the citing opinion content
        assert "Following Brown" in prompt


# =============================================================================
# Test: S5 Parsing
# =============================================================================


class TestS5Parse:
    """Tests for S5 response parsing."""

    def test_parse_agrees_true(self) -> None:
        """Parse agrees=true."""
        s5 = S5DistinguishCB()
        response = '{"agrees": true, "reasoning": "The case follows precedent."}'
        parsed = s5.parse(response)

        assert parsed["agrees"] is True
        assert "follows precedent" in parsed["reasoning"]

    def test_parse_agrees_false(self) -> None:
        """Parse agrees=false."""
        s5 = S5DistinguishCB()
        response = '{"agrees": false, "reasoning": "The case distinguishes."}'
        parsed = s5.parse(response)

        assert parsed["agrees"] is False

    def test_parse_agrees_string_true(self) -> None:
        """Parse agrees as string 'true'."""
        s5 = S5DistinguishCB()
        response = '{"agrees": "true", "reasoning": ""}'
        parsed = s5.parse(response)

        assert parsed["agrees"] is True

    def test_parse_agrees_string_yes(self) -> None:
        """Parse agrees as string 'yes'."""
        s5 = S5DistinguishCB()
        response = '{"agrees": "yes", "reasoning": ""}'
        parsed = s5.parse(response)

        assert parsed["agrees"] is True

    def test_parse_invalid_json(self) -> None:
        """Parse failure returns errors."""
        s5 = S5DistinguishCB()
        parsed = s5.parse("not json")

        assert "errors" in parsed


# =============================================================================
# Test: S5 Ground Truth
# =============================================================================


class TestS5GroundTruth:
    """Tests for S5 ground truth from edge.agree."""

    def test_ground_truth_agrees(self, instance_tier_b: ChainInstance) -> None:
        """Ground truth reflects edge.agree=True."""
        s5 = S5DistinguishCB()
        ctx = ChainContext(instance=instance_tier_b)
        gt = s5.ground_truth(ctx)

        assert gt["agrees"] is True

    def test_ground_truth_distinguishes(
        self, instance_distinguishes: ChainInstance
    ) -> None:
        """Ground truth reflects edge.agree=False."""
        s5 = S5DistinguishCB()
        ctx = ChainContext(instance=instance_distinguishes)
        gt = s5.ground_truth(ctx)

        assert gt["agrees"] is False


# =============================================================================
# Test: S5 Scoring
# =============================================================================


class TestS5Scoring:
    """Tests for S5 scoring against edge.agree."""

    def test_score_agrees_match(self) -> None:
        """Score 1.0 when agrees matches ground truth."""
        s5 = S5DistinguishCB()
        parsed = {"agrees": True, "reasoning": ""}
        gt = {"agrees": True}

        score, correct = s5.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_disagrees_match(self) -> None:
        """Score 1.0 when both false."""
        s5 = S5DistinguishCB()
        parsed = {"agrees": False, "reasoning": ""}
        gt = {"agrees": False}

        score, correct = s5.score(parsed, gt)

        assert score == 1.0
        assert correct is True

    def test_score_mismatch(self) -> None:
        """Score 0.0 when agrees doesn't match."""
        s5 = S5DistinguishCB()
        parsed = {"agrees": True, "reasoning": ""}
        gt = {"agrees": False}

        score, correct = s5.score(parsed, gt)

        assert score == 0.0
        assert correct is False

    def test_score_parse_error(self) -> None:
        """Score 0.0 when parsed has errors."""
        s5 = S5DistinguishCB()
        parsed = {"errors": ["parse error"]}
        gt = {"agrees": True}

        score, correct = s5.score(parsed, gt)

        assert score == 0.0
        assert correct is False


# =============================================================================
# Test: S5 Variants Stored Separately
# =============================================================================


class TestS5VariantRouting:
    """Tests for S5:cb and S5:rag stored separately."""

    def test_variants_stored_separately(
        self, instance_tier_b: ChainInstance
    ) -> None:
        """S5:cb and S5:rag results stored under different step_ids."""
        s1 = StubStep(name="s1", requires=set())
        s4 = StubStep(name="s4", requires={"s1"})
        s5_cb = S5DistinguishCB()
        s5_rag = S5DistinguishRAG()

        backend = MockBackend(
            default_response='{"agrees": true, "reasoning": "test"}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s4, s5_cb, s5_rag])

        result = executor.execute(instance_tier_b)

        assert "s5:cb" in result.step_results
        assert "s5:rag" in result.step_results
        assert result.step_results["s5:cb"] is not result.step_results["s5:rag"]

    def test_cb_runs_rag_skipped_tier_a_only(
        self, instance_tier_a_only: ChainInstance
    ) -> None:
        """S5:cb runs, S5:rag skipped when only Tier A available."""
        s1 = StubStep(name="s1", requires=set())
        s4 = StubStep(name="s4", requires={"s1"})
        s5_cb = S5DistinguishCB()
        s5_rag = S5DistinguishRAG()

        backend = MockBackend(
            default_response='{"agrees": true, "reasoning": "test"}'
        )
        executor = ChainExecutor(backend=backend, steps=[s1, s4, s5_cb, s5_rag])

        result = executor.execute(instance_tier_a_only)

        assert result.step_results["s5:cb"].status == STATUS_OK
        assert result.step_results["s5:rag"].status == STATUS_SKIPPED_COVERAGE
