"""Chain executor state machine for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 2 and L10_AGENTIC_SPEC.md.
"""

import time
from typing import Sequence

from chain.backends.base import Backend
from chain.steps.base import Step
from core.schemas.chain import ChainContext, ChainInstance
from core.schemas.results import (
    STATUS_OK,
    STATUS_SKIPPED_COVERAGE,
    STATUS_SKIPPED_DEPENDENCY,
    ChainResult,
    StepResult,
)


class ChainExecutor:
    """Execute chain steps on instances with dependency resolution.

    The executor is the central state machine that:
    1. Iterates through steps in order
    2. Checks coverage requirements (Tier A/B)
    3. Checks dependency requirements (requires())
    4. Calls backend for LLM completion
    5. Parses and scores results
    6. Handles S7 gate voiding of S6

    Key Design Points (from PROMPT_CONTRACT.md):
    - Executor owns status, never the model
    - Only status="OK" satisfies dependencies
    - S7 gate can void S6 result when correct=False
    """

    def __init__(
        self,
        backend: Backend,
        steps: Sequence[Step],
        s7_step_id: str = "s7",
        s6_step_id: str = "s6",
    ) -> None:
        """Initialize executor.

        Args:
            backend: LLM backend for completions
            steps: Ordered sequence of steps to execute
            s7_step_id: Step ID of S7 gate (for voiding logic)
            s6_step_id: Step ID of S6 (target of voiding)
        """
        self._backend = backend
        self._steps = list(steps)
        self._s7_step_id = s7_step_id
        self._s6_step_id = s6_step_id

    def execute(self, instance: ChainInstance) -> ChainResult:
        """Execute all steps on an instance.

        Args:
            instance: The chain instance to process

        Returns:
            ChainResult with all step results
        """
        ctx = ChainContext(instance=instance)

        for step in self._steps:
            result = self._execute_step(step, ctx)
            ctx.set(step.step_id, result)

            # S7 gate voiding logic
            if step.step_id == self._s7_step_id:
                self._apply_s7_voiding(ctx, result)

        return self._build_chain_result(ctx)

    def _execute_step(self, step: Step, ctx: ChainContext) -> StepResult:
        """Execute a single step with coverage and dependency checks.

        Args:
            step: The step to execute
            ctx: Current chain context

        Returns:
            StepResult (status may be SKIPPED_*)
        """
        # Check coverage first
        if not step.check_coverage(ctx):
            return StepResult(
                step_id=step.step_id,
                step=step.step_name,
                variant=step._extract_variant(),
                status=STATUS_SKIPPED_COVERAGE,
            )

        # Check dependencies
        ok_step_ids = ctx.get_ok_step_ids()
        required = step.requires()
        if not required.issubset(ok_step_ids):
            missing = required - ok_step_ids
            return StepResult(
                step_id=step.step_id,
                step=step.step_name,
                variant=step._extract_variant(),
                status=STATUS_SKIPPED_DEPENDENCY,
                model_errors=[f"Missing dependencies: {sorted(missing)}"],
            )

        # Build prompt and call backend
        prompt = step.prompt(ctx)
        start_time = time.time()
        raw_response = self._backend.complete(prompt)
        latency_ms = (time.time() - start_time) * 1000

        # Parse response
        parsed = step.parse(raw_response)

        # Get ground truth and score
        ground_truth = step.ground_truth(ctx)
        score_val, correct = step.score(parsed, ground_truth)

        # Create result with status=OK (executor owns status)
        result = step.create_result(
            prompt=prompt,
            raw_response=raw_response,
            parsed=parsed,
            ground_truth=ground_truth,
            score=score_val,
            correct=correct,
            model=self._backend.model_id,
        )

        # Add latency
        # Note: StepResult is not frozen, so we can set attributes
        result.latency_ms = latency_ms
        result.timestamp = start_time

        return result

    def _apply_s7_voiding(self, ctx: ChainContext, s7_result: StepResult) -> None:
        """Apply S7 gate voiding logic to S6.

        If S7 returns correct=False, void the S6 result.
        Per PROMPT_CONTRACT.md: status stays "OK", voided=True.

        Args:
            ctx: Chain context
            s7_result: The S7 step result
        """
        if s7_result.status != STATUS_OK:
            return

        if not s7_result.correct:
            s6_result = ctx.get(self._s6_step_id)
            if s6_result is not None and s6_result.status == STATUS_OK:
                s6_result.voided = True
                s6_result.void_reason = "S7 citation integrity gate failed"

    def _build_chain_result(self, ctx: ChainContext) -> ChainResult:
        """Build final ChainResult from context.

        Args:
            ctx: Chain context with all step results

        Returns:
            ChainResult aggregating all results
        """
        # Check if chain is voided (S7 gate failed)
        s7_result = ctx.get(self._s7_step_id)
        voided = False
        void_reason = None

        if s7_result is not None and s7_result.status == STATUS_OK:
            if not s7_result.correct:
                voided = True
                void_reason = "S7 citation integrity gate failed"

        return ChainResult(
            instance_id=ctx.instance.id,
            step_results=ctx.step_results.copy(),
            voided=voided,
            void_reason=void_reason,
        )
