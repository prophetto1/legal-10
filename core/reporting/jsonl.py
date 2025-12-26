"""JSONL output for L10 Agentic Chain results.

From MVP_BUILD_ORDER.md Phase 4.
Emits ChainResult and StepResult objects as JSONL for analysis.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import IO, Sequence

from core.schemas.results import ChainResult, StepResult


def step_result_to_dict(result: StepResult) -> dict:
    """Convert StepResult to serializable dict.

    Args:
        result: StepResult to convert

    Returns:
        Dict suitable for JSON serialization
    """
    return {
        "step_id": result.step_id,
        "step": result.step,
        "variant": result.variant,
        "status": result.status,
        "prompt": result.prompt,
        "raw_response": result.raw_response,
        "parsed": result.parsed,
        "ground_truth": result.ground_truth,
        "score": result.score,
        "correct": result.correct,
        "voided": result.voided,
        "void_reason": result.void_reason,
        "model": result.model,
        "timestamp": result.timestamp,
        "latency_ms": result.latency_ms,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "model_errors": result.model_errors,
    }


def chain_result_to_dict(result: ChainResult) -> dict:
    """Convert ChainResult to serializable dict.

    Args:
        result: ChainResult to convert

    Returns:
        Dict suitable for JSON serialization
    """
    step_results = {
        step_id: step_result_to_dict(sr)
        for step_id, sr in result.step_results.items()
    }

    return {
        "instance_id": result.instance_id,
        "step_results": step_results,
        "voided": result.voided,
        "void_reason": result.void_reason,
    }


def write_result(result: ChainResult, file: IO[str]) -> None:
    """Write a single ChainResult as JSONL line.

    Args:
        result: ChainResult to write
        file: Open file handle to write to
    """
    data = chain_result_to_dict(result)
    json_line = json.dumps(data, ensure_ascii=False)
    file.write(json_line + "\n")


def write_results(
    results: Sequence[ChainResult],
    output_path: Path | str,
) -> int:
    """Write multiple ChainResults to JSONL file.

    Args:
        results: Sequence of ChainResults to write
        output_path: Path to output JSONL file

    Returns:
        Number of results written
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for result in results:
            write_result(result, f)
            count += 1

    return count


def read_results(input_path: Path | str) -> list[dict]:
    """Read ChainResults from JSONL file.

    Args:
        input_path: Path to input JSONL file

    Returns:
        List of result dicts (not hydrated to ChainResult objects)
    """
    input_path = Path(input_path)
    results = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    return results


def summarize_results(results: Sequence[ChainResult]) -> dict:
    """Generate summary statistics from results.

    Args:
        results: Sequence of ChainResults

    Returns:
        Dict with summary statistics
    """
    total = len(results)
    voided_count = sum(1 for r in results if r.voided)

    # Aggregate step statistics
    step_stats: dict[str, dict] = {}

    for result in results:
        for step_id, sr in result.step_results.items():
            if step_id not in step_stats:
                step_stats[step_id] = {
                    "count": 0,
                    "ok_count": 0,
                    "skipped_coverage": 0,
                    "skipped_dependency": 0,
                    "total_score": 0.0,
                    "correct_count": 0,
                    "voided_count": 0,
                }

            stats = step_stats[step_id]
            stats["count"] += 1

            if sr.status == "OK":
                stats["ok_count"] += 1
                stats["total_score"] += sr.score
                if sr.correct:
                    stats["correct_count"] += 1
                if sr.voided:
                    stats["voided_count"] += 1
            elif sr.status == "SKIPPED_COVERAGE":
                stats["skipped_coverage"] += 1
            elif sr.status == "SKIPPED_DEPENDENCY":
                stats["skipped_dependency"] += 1

    # Compute averages
    for step_id, stats in step_stats.items():
        if stats["ok_count"] > 0:
            stats["avg_score"] = stats["total_score"] / stats["ok_count"]
            stats["accuracy"] = stats["correct_count"] / stats["ok_count"]
        else:
            stats["avg_score"] = 0.0
            stats["accuracy"] = 0.0

    return {
        "total_instances": total,
        "voided_instances": voided_count,
        "voided_rate": voided_count / total if total > 0 else 0.0,
        "step_stats": step_stats,
    }
