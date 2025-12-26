"""Tests for executor - Phase 2 Contract Lock.

Exit Criteria:
- requires() dependency resolution works
- step_id routing: s5:cb and s5:rag stored separately
- SKIPPED_COVERAGE fires when citing_case.majority_opinion is None
- SKIPPED_DEPENDENCY fires when required step missing/not OK
- S7 gate voids S6 when correct=False
- All tests pass
"""

import pytest

from chain.backends.mock_backend import MockBackend
from chain.runner.executor import ChainExecutor
from chain.steps.stub_step import StubStep
from core.schemas.case import CourtCase, ShepardsEdge
from core.schemas.chain import ChainInstance
from core.schemas.results import (
    STATUS_OK,
    STATUS_SKIPPED_COVERAGE,
    STATUS_SKIPPED_DEPENDENCY,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cited_case_with_opinion() -> CourtCase:
    """Cited case with majority opinion (Tier A satisfied)."""
    return CourtCase(
        us_cite="347 U.S. 483",
        case_name="Brown v. Board of Education",
        term=1954,
        majority_opinion="We conclude that in the field of public education...",
    )


@pytest.fixture
def citing_case_with_opinion() -> CourtCase:
    """Citing case with majority opinion (Tier B satisfied)."""
    return CourtCase(
        us_cite="349 U.S. 294",
        case_name="Bolling v. Sharpe",
        term=1954,
        majority_opinion="We have this day held that...",
    )


@pytest.fixture
def citing_case_no_opinion() -> CourtCase:
    """Citing case without majority opinion (Tier B NOT satisfied)."""
    return CourtCase(
        us_cite="349 U.S. 294",
        case_name="Bolling v. Sharpe",
        term=1954,
        # No majority_opinion
    )


@pytest.fixture
def edge() -> ShepardsEdge:
    """Standard Shepard's edge."""
    return ShepardsEdge(
        cited_case_us_cite="347 U.S. 483",
        citing_case_us_cite="349 U.S. 294",
        shepards="followed",
        agree=True,
    )


@pytest.fixture
def instance_tier_b(
    cited_case_with_opinion: CourtCase,
    citing_case_with_opinion: CourtCase,
    edge: ShepardsEdge,
) -> ChainInstance:
    """Instance with both cases having opinions (Tier A + B)."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case_with_opinion,
        citing_case=citing_case_with_opinion,
        edge=edge,
    )


@pytest.fixture
def instance_tier_a_only(
    cited_case_with_opinion: CourtCase,
    citing_case_no_opinion: CourtCase,
    edge: ShepardsEdge,
) -> ChainInstance:
    """Instance with only cited case having opinion (Tier A only)."""
    return ChainInstance(
        id="pair::347_us_483::349_us_294",
        cited_case=cited_case_with_opinion,
        citing_case=citing_case_no_opinion,
        edge=edge,
    )


@pytest.fixture
def mock_backend() -> MockBackend:
    """Mock backend with default empty response."""
    return MockBackend()


# =============================================================================
# Test: Dependency Resolution
# =============================================================================


class TestDependencyResolution:
    """Tests for requires() dependency resolution."""

    def test_no_dependencies_executes(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Step with no dependencies executes successfully."""
        s1 = StubStep(name="s1", requires=set(), always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s1])

        result = executor.execute(instance_tier_b)

        assert "s1" in result.step_results
        assert result.step_results["s1"].status == STATUS_OK

    def test_satisfied_dependency_executes(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Step with satisfied dependency executes successfully."""
        s1 = StubStep(name="s1", requires=set(), always_correct=True)
        s2 = StubStep(name="s2", requires={"s1"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s1, s2])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s1"].status == STATUS_OK
        assert result.step_results["s2"].status == STATUS_OK

    def test_unsatisfied_dependency_skipped(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Step with unsatisfied dependency is skipped."""
        # s2 requires s1, but we only run s2 (s1 not in step list)
        s2 = StubStep(name="s2", requires={"s1"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s2])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s2"].status == STATUS_SKIPPED_DEPENDENCY

    def test_failed_dependency_skipped(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Step is skipped when dependency exists but not OK."""
        # s1 will be skipped due to missing its own dependency
        s1 = StubStep(name="s1", requires={"nonexistent"}, always_correct=True)
        s2 = StubStep(name="s2", requires={"s1"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s1, s2])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s1"].status == STATUS_SKIPPED_DEPENDENCY
        assert result.step_results["s2"].status == STATUS_SKIPPED_DEPENDENCY

    def test_multiple_dependencies_all_required(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """All dependencies must be satisfied."""
        s1 = StubStep(name="s1", requires=set(), always_correct=True)
        s4 = StubStep(name="s4", requires=set(), always_correct=True)
        s5 = StubStep(name="s5", variant="cb", requires={"s1", "s4"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s1, s4, s5])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s5:cb"].status == STATUS_OK

    def test_partial_dependencies_skipped(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Step skipped when only some dependencies satisfied."""
        s1 = StubStep(name="s1", requires=set(), always_correct=True)
        # s5 requires s1 and s4, but s4 not in steps
        s5 = StubStep(name="s5", variant="cb", requires={"s1", "s4"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s1, s5])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s1"].status == STATUS_OK
        assert result.step_results["s5:cb"].status == STATUS_SKIPPED_DEPENDENCY


# =============================================================================
# Test: Step ID Routing
# =============================================================================


class TestStepIdRouting:
    """Tests for step_id routing with variants."""

    def test_variants_stored_separately(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """s5:cb and s5:rag are stored as separate step_ids."""
        s1 = StubStep(name="s1", requires=set(), always_correct=True)
        s5_cb = StubStep(
            name="s5",
            variant="cb",
            requires={"s1"},
            always_correct=True,
            score_value=0.8,
        )
        s5_rag = StubStep(
            name="s5",
            variant="rag",
            requires={"s1"},
            always_correct=True,
            score_value=0.9,
        )
        executor = ChainExecutor(backend=mock_backend, steps=[s1, s5_cb, s5_rag])

        result = executor.execute(instance_tier_b)

        assert "s5:cb" in result.step_results
        assert "s5:rag" in result.step_results
        assert result.step_results["s5:cb"].score == 0.8
        assert result.step_results["s5:rag"].score == 0.9
        assert result.step_results["s5:cb"] is not result.step_results["s5:rag"]

    def test_variant_dependency_resolution(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Variant step_ids work in dependency resolution."""
        s5_cb = StubStep(name="s5", variant="cb", requires=set(), always_correct=True)
        s6 = StubStep(name="s6", requires={"s5:cb"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s5_cb, s6])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s5:cb"].status == STATUS_OK
        assert result.step_results["s6"].status == STATUS_OK


# =============================================================================
# Test: Coverage Checks
# =============================================================================


class TestCoverageChecks:
    """Tests for SKIPPED_COVERAGE when coverage requirements not met."""

    def test_tier_b_required_but_missing(
        self, mock_backend: MockBackend, instance_tier_a_only: ChainInstance
    ) -> None:
        """Step requiring citing text skipped when citing_case.majority_opinion is None."""
        s6 = StubStep(
            name="s6",
            requires=set(),
            require_citing_text=True,
            always_correct=True,
        )
        executor = ChainExecutor(backend=mock_backend, steps=[s6])

        result = executor.execute(instance_tier_a_only)

        assert result.step_results["s6"].status == STATUS_SKIPPED_COVERAGE

    def test_tier_b_required_and_present(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Step requiring citing text executes when citing_case has opinion."""
        s6 = StubStep(
            name="s6",
            requires=set(),
            require_citing_text=True,
            always_correct=True,
        )
        executor = ChainExecutor(backend=mock_backend, steps=[s6])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s6"].status == STATUS_OK

    def test_tier_a_step_runs_without_tier_b(
        self, mock_backend: MockBackend, instance_tier_a_only: ChainInstance
    ) -> None:
        """Step not requiring citing text runs even without it."""
        s1 = StubStep(
            name="s1",
            requires=set(),
            require_citing_text=False,
            always_correct=True,
        )
        executor = ChainExecutor(backend=mock_backend, steps=[s1])

        result = executor.execute(instance_tier_a_only)

        assert result.step_results["s1"].status == STATUS_OK


# =============================================================================
# Test: S7 Gate Voiding
# =============================================================================


class TestS7GateVoiding:
    """Tests for S7 gate voiding S6 when correct=False."""

    def test_s7_correct_no_voiding(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """S6 not voided when S7 correct=True."""
        s6 = StubStep(name="s6", requires=set(), always_correct=True)
        s7 = StubStep(name="s7", requires={"s6"}, always_correct=True)
        executor = ChainExecutor(backend=mock_backend, steps=[s6, s7])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s6"].voided is False
        assert result.voided is False

    def test_s7_incorrect_voids_s6(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """S6 voided when S7 correct=False."""
        s6 = StubStep(name="s6", requires=set(), always_correct=True)
        s7 = StubStep(name="s7", requires={"s6"}, always_correct=False)
        executor = ChainExecutor(backend=mock_backend, steps=[s6, s7])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s6"].voided is True
        assert result.step_results["s6"].void_reason == "S7 citation integrity gate failed"
        assert result.step_results["s6"].status == STATUS_OK  # Status stays OK
        assert result.voided is True

    def test_s7_skipped_no_voiding(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """S6 not voided when S7 is skipped."""
        s6 = StubStep(name="s6", requires=set(), always_correct=True)
        # s7 requires nonexistent step, so it will be skipped
        s7 = StubStep(name="s7", requires={"nonexistent"}, always_correct=False)
        executor = ChainExecutor(backend=mock_backend, steps=[s6, s7])

        result = executor.execute(instance_tier_b)

        assert result.step_results["s6"].voided is False
        assert result.step_results["s7"].status == STATUS_SKIPPED_DEPENDENCY
        assert result.voided is False


# =============================================================================
# Test: MockBackend
# =============================================================================


class TestMockBackend:
    """Tests for MockBackend substring matching."""

    def test_substring_matching(self) -> None:
        """Backend returns response matching prompt substring."""
        backend = MockBackend(
            responses={
                "S1": '{"holding": "test"}',
                "S4": '{"disposition": "reversed"}',
            }
        )

        assert backend.complete("S1: Extract holding") == '{"holding": "test"}'
        assert backend.complete("S4: Get disposition") == '{"disposition": "reversed"}'

    def test_first_match_wins(self) -> None:
        """First matching substring wins."""
        backend = MockBackend(
            responses={
                "Extract": '{"first": true}',
                "S1": '{"second": true}',
            }
        )

        # "Extract" appears first in responses dict
        assert backend.complete("S1: Extract holding") == '{"first": true}'

    def test_default_response(self) -> None:
        """Default response when no match."""
        backend = MockBackend(
            responses={"S1": '{"matched": true}'},
            default_response='{"default": true}',
        )

        assert backend.complete("S99: Unknown step") == '{"default": true}'

    def test_call_history(self) -> None:
        """Call history tracks all prompts."""
        backend = MockBackend()
        backend.complete("prompt 1")
        backend.complete("prompt 2")

        assert backend.call_history == ["prompt 1", "prompt 2"]

    def test_model_id(self) -> None:
        """Model ID is 'mock'."""
        backend = MockBackend()
        assert backend.model_id == "mock"


# =============================================================================
# Test: Full Chain Execution
# =============================================================================


class TestFullChainExecution:
    """Integration tests for full chain execution."""

    def test_full_chain_all_pass(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """Execute full chain with all steps passing."""
        steps = [
            StubStep(name="s1", requires=set()),
            StubStep(name="s2", requires={"s1"}),
            StubStep(name="s3", requires={"s1"}),
            StubStep(name="s4", requires={"s1"}),
            StubStep(name="s5", variant="cb", requires={"s1", "s4"}),
            StubStep(name="s6", requires={"s5:cb"}),
            StubStep(name="s7", requires={"s6"}),
        ]
        executor = ChainExecutor(backend=mock_backend, steps=steps)

        result = executor.execute(instance_tier_b)

        assert len(result.step_results) == 7
        for step_id, sr in result.step_results.items():
            assert sr.status == STATUS_OK, f"{step_id} should be OK"
        assert result.voided is False

    def test_chain_result_has_instance_id(
        self, mock_backend: MockBackend, instance_tier_b: ChainInstance
    ) -> None:
        """ChainResult includes instance_id."""
        s1 = StubStep(name="s1", requires=set())
        executor = ChainExecutor(backend=mock_backend, steps=[s1])

        result = executor.execute(instance_tier_b)

        assert result.instance_id == "pair::347_us_483::349_us_294"
