#!/usr/bin/env python
"""Validate dataset joins and print coverage report.

From MVP_BUILD_ORDER.md Phase 3.

Usage:
    python -m scripts.validate_joins
    python -m scripts.validate_joins --local ./data
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Run coverage validation and print report."""
    parser = argparse.ArgumentParser(
        description="Validate dataset joins and print coverage report"
    )
    parser.add_argument(
        "--local",
        type=Path,
        help="Load from local directory instead of HuggingFace",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="Number of sample ChainInstances to validate (default: 5)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("L10 Agentic Chain - Dataset Coverage Report")
    print("=" * 60)
    print()

    # Load datasets
    print("Loading datasets...")
    try:
        from chain.datasets.loaders import load_datasets, validate_datasets

        if args.local:
            bundle = load_datasets(source="local", local_path=args.local)
            print(f"  Source: local ({args.local})")
        else:
            bundle = load_datasets(source="huggingface")
            print("  Source: HuggingFace (reglab/legal_hallucinations_paper_data)")
    except Exception as e:
        print(f"  ERROR: Failed to load datasets: {e}")
        return 1

    # Validate dataset columns
    print()
    print("Validating dataset columns...")
    validation = validate_datasets(bundle)
    all_valid = True
    for name, valid in validation.items():
        status = "OK" if valid else "MISSING COLUMNS"
        print(f"  {name}: {status}")
        if not valid:
            all_valid = False

    if not all_valid:
        print()
        print("ERROR: Some datasets have missing columns")
        return 1

    # Print dataset sizes
    print()
    print("Dataset sizes:")
    print(f"  scdb_sample:           {len(bundle.scdb):,} rows")
    print(f"  scotus_shepards_sample: {len(bundle.shepards):,} rows")
    print(f"  scotus_overruled_db:   {len(bundle.overruled):,} rows")
    print(f"  fake_cases:            {len(bundle.fake_cases):,} rows")

    # Build indexes
    print()
    print("Building indexes...")
    from chain.datasets.builder import DatasetBuilder

    builder = DatasetBuilder(bundle)
    builder.build_indexes()

    print(f"  case_by_us_cite:       {len(builder.case_by_us_cite):,} entries")
    print(f"  overrule_by_us_cite:   {len(builder.overrule_by_us_cite):,} entries")
    print(f"  fake_us_cites:         {len(builder.fake_us_cites):,} entries")
    print(f"  fake_case_names:       {len(builder.fake_case_names):,} entries")

    # Compute coverage
    print()
    print("Computing coverage...")
    coverage = builder.compute_coverage()
    print()
    print(coverage)

    # Validate sample instances
    print()
    print(f"Validating {args.sample} sample ChainInstances...")
    instances = []
    for i, instance in enumerate(builder.iter_chain_instances()):
        instances.append(instance)
        if len(instances) >= args.sample:
            break

    if len(instances) < args.sample:
        print(f"  WARNING: Only {len(instances)} instances could be built")

    for i, inst in enumerate(instances, 1):
        has_cited = inst.has_cited_text
        has_citing = inst.has_citing_text
        tier = "A+B" if has_citing else ("A" if has_cited else "?")
        print(f"  [{i}] {inst.id[:50]}...")
        print(f"      cited: {inst.cited_case.case_name[:40]}... (text: {has_cited})")
        if inst.citing_case:
            print(
                f"      citing: {inst.citing_case.case_name[:40]}... (text: {has_citing})"
            )
        else:
            print("      citing: None")
        print(f"      edge.agree: {inst.edge.agree}, tier: {tier}")
        if inst.overrule:
            print(f"      overrule: {inst.overrule.year_overruled}")

    print()
    print("=" * 60)
    print("Validation complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
