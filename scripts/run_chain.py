#!/usr/bin/env python
"""Run L10 Agentic Chain on instances.

From MVP_BUILD_ORDER.md Phase 4.

Usage:
    python -m scripts.run_chain --instances 5 --steps s1,s7
    python -m scripts.run_chain --instances 10 --steps s1 --output results.jsonl
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Run chain execution."""
    parser = argparse.ArgumentParser(
        description="Run L10 Agentic Chain on instances"
    )
    parser.add_argument(
        "--instances",
        type=int,
        default=5,
        help="Number of instances to process (default: 5)",
    )
    parser.add_argument(
        "--steps",
        type=str,
        default="s1,s7",
        help="Comma-separated list of steps to run (default: s1,s7)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL file path (default: stdout summary only)",
    )
    parser.add_argument(
        "--local",
        type=Path,
        default=None,
        help="Load data from local directory instead of HuggingFace",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output for each instance",
    )
    args = parser.parse_args()

    # Parse steps
    step_names = [s.strip() for s in args.steps.split(",")]

    print("=" * 60)
    print("L10 Agentic Chain - Execution")
    print("=" * 60)
    print(f"Instances: {args.instances}")
    print(f"Steps: {step_names}")
    if args.output:
        print(f"Output: {args.output}")
    print()

    # Load datasets
    print("Loading datasets...")
    try:
        from chain.datasets.loaders import load_datasets
        from chain.datasets.builder import DatasetBuilder

        if args.local:
            bundle = load_datasets(source="local", local_path=args.local)
        else:
            bundle = load_datasets(source="huggingface")

        builder = DatasetBuilder(bundle)
        builder.build_indexes()
        print(f"  Loaded {len(builder.case_by_us_cite)} cases")
        print(f"  Loaded {len(builder.fake_us_cites)} fake citations")

    except Exception as e:
        print(f"  ERROR: Failed to load datasets: {e}")
        return 1

    # Build step instances
    print()
    print("Building steps...")
    from chain.backends.mock_backend import MockBackend
    from chain.steps.stub_step import StubStep

    steps = []
    for step_name in step_names:
        if step_name == "s1":
            from chain.steps.s1_known_authority import S1KnownAuthority
            steps.append(S1KnownAuthority())
            print("  Added: S1 Known Authority")

        elif step_name == "s2":
            from chain.steps.s2_unknown_authority import S2UnknownAuthority
            steps.append(S2UnknownAuthority())
            print("  Added: S2 Unknown Authority")

        elif step_name == "s3":
            from chain.steps.s3_validate_authority import S3ValidateAuthority
            steps.append(S3ValidateAuthority())
            print("  Added: S3 Validate Authority")

        elif step_name == "s4":
            from chain.steps.s4_fact_extraction import S4FactExtraction
            steps.append(S4FactExtraction())
            print("  Added: S4 Fact Extraction")

        elif step_name == "s5:cb":
            from chain.steps.s5_distinguish import S5DistinguishCB
            steps.append(S5DistinguishCB())
            print("  Added: S5:cb Distinguish (backbone)")

        elif step_name == "s5:rag":
            from chain.steps.s5_distinguish import S5DistinguishRAG
            steps.append(S5DistinguishRAG())
            print("  Added: S5:rag Distinguish (enriched)")

        elif step_name == "s6":
            from chain.steps.s6_irac_synthesis import S6IRACSynthesis
            steps.append(S6IRACSynthesis())
            print("  Added: S6 IRAC Synthesis")

        elif step_name == "s7":
            from chain.steps.s7_citation_integrity import S7CitationIntegrity
            s7 = S7CitationIntegrity()
            s7.set_verification_sets(
                builder.fake_us_cites,
                builder.case_by_us_cite,
            )
            steps.append(s7)
            print("  Added: S7 Citation Integrity")

        else:
            # Generic stub for unknown steps
            steps.append(StubStep(name=step_name, requires=set()))
            print(f"  Added: {step_name} (stub)")

    # Create mock backend (for S1 - will need real backend later)
    # For now, return JSON that mimics correct extraction
    backend = MockBackend(
        responses={
            # S1 will get back whatever the mock returns
            # In real execution, this would be an LLM
        },
        default_response='{"us_cite": "", "case_name": "", "term": null}',
    )

    # Create executor
    from chain.runner.executor import ChainExecutor
    executor = ChainExecutor(backend=backend, steps=steps)

    # Run on instances
    print()
    print("Executing chain...")
    results = []
    instances_processed = 0

    for instance in builder.iter_chain_instances():
        if instances_processed >= args.instances:
            break

        result = executor.execute(instance)
        results.append(result)
        instances_processed += 1

        if args.verbose:
            print(f"\n  [{instances_processed}] {instance.id}")
            for step_id, sr in result.step_results.items():
                status_marker = "[OK]" if sr.status == "OK" else "[SKIP]"
                score_str = f"{sr.score:.2f}" if sr.status == "OK" else "-"
                print(f"      {status_marker} {step_id}: {sr.status} (score={score_str})")

    print(f"\n  Processed {instances_processed} instances")

    # Write results if output specified
    if args.output:
        from core.reporting.jsonl import write_results
        count = write_results(results, args.output)
        print(f"  Wrote {count} results to {args.output}")

    # Print summary
    print()
    print("Summary:")
    from core.reporting.jsonl import summarize_results
    summary = summarize_results(results)

    print(f"  Total instances: {summary['total_instances']}")
    print(f"  Voided instances: {summary['voided_instances']} ({summary['voided_rate']:.1%})")
    print()
    print("  Step Statistics:")
    for step_id, stats in summary["step_stats"].items():
        print(f"    {step_id}:")
        print(f"      OK: {stats['ok_count']}/{stats['count']}")
        print(f"      Skipped (coverage): {stats['skipped_coverage']}")
        print(f"      Skipped (dependency): {stats['skipped_dependency']}")
        if stats["ok_count"] > 0:
            print(f"      Avg score: {stats['avg_score']:.3f}")
            print(f"      Accuracy: {stats['accuracy']:.1%}")

    print()
    print("=" * 60)
    print("Execution complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
