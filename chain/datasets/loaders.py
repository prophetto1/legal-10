"""Dataset loaders for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 3.
Loads 4 CSVs from HuggingFace: scdb_sample, scotus_shepards_sample,
scotus_overruled_db, fake_cases.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# HuggingFace dataset path
HF_REPO = "reglab/legal_hallucinations_paper_data"
HF_SAMPLES_PATH = "samples"


@dataclass
class DatasetBundle:
    """Container for all loaded datasets.

    Attributes:
        scdb: SCDB sample with opinions (5,000 cases)
        shepards: Shepard's citation relationships (5,000 pairs)
        overruled: Overruling relationships (288 rows)
        fake_cases: Fabricated cases for hallucination testing (999 rows)
    """

    scdb: pd.DataFrame
    shepards: pd.DataFrame
    overruled: pd.DataFrame
    fake_cases: pd.DataFrame


def load_from_huggingface() -> DatasetBundle:
    """Load all 4 CSVs from HuggingFace.

    Returns:
        DatasetBundle with all datasets

    Raises:
        Exception: If HuggingFace datasets library not available or load fails
    """
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "HuggingFace datasets library required. Install with: pip install datasets"
        ) from e

    # Load each CSV from the HuggingFace repo
    scdb = load_dataset(HF_REPO, data_files=f"{HF_SAMPLES_PATH}/scdb_sample.csv")[
        "train"
    ].to_pandas()

    shepards = load_dataset(
        HF_REPO, data_files=f"{HF_SAMPLES_PATH}/scotus_shepards_sample.csv"
    )["train"].to_pandas()

    overruled = load_dataset(
        HF_REPO, data_files=f"{HF_SAMPLES_PATH}/scotus_overruled_db.csv"
    )["train"].to_pandas()

    fake_cases = load_dataset(HF_REPO, data_files=f"{HF_SAMPLES_PATH}/fake_cases.csv")[
        "train"
    ].to_pandas()

    return DatasetBundle(
        scdb=scdb,
        shepards=shepards,
        overruled=overruled,
        fake_cases=fake_cases,
    )


def load_from_local(data_dir: Path | str) -> DatasetBundle:
    """Load all 4 CSVs from local directory.

    Args:
        data_dir: Path to directory containing CSV files

    Returns:
        DatasetBundle with all datasets

    Raises:
        FileNotFoundError: If any required file is missing
    """
    data_dir = Path(data_dir)

    scdb_path = data_dir / "scdb_sample.csv"
    shepards_path = data_dir / "scotus_shepards_sample.csv"
    overruled_path = data_dir / "scotus_overruled_db.csv"
    fake_cases_path = data_dir / "fake_cases.csv"

    # Validate all files exist
    for path in [scdb_path, shepards_path, overruled_path, fake_cases_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    return DatasetBundle(
        scdb=pd.read_csv(scdb_path),
        shepards=pd.read_csv(shepards_path),
        overruled=pd.read_csv(overruled_path),
        fake_cases=pd.read_csv(fake_cases_path),
    )


def load_datasets(
    source: str = "huggingface",
    local_path: Path | str | None = None,
) -> DatasetBundle:
    """Load datasets from specified source.

    Args:
        source: "huggingface" or "local"
        local_path: Required if source is "local"

    Returns:
        DatasetBundle with all datasets

    Raises:
        ValueError: If source is invalid or local_path missing for local source
    """
    if source == "huggingface":
        return load_from_huggingface()
    elif source == "local":
        if local_path is None:
            raise ValueError("local_path required when source is 'local'")
        return load_from_local(local_path)
    else:
        raise ValueError(f"Invalid source: {source}. Must be 'huggingface' or 'local'")


def validate_datasets(bundle: DatasetBundle) -> dict[str, bool]:
    """Validate that all datasets have expected columns.

    Args:
        bundle: DatasetBundle to validate

    Returns:
        Dict mapping dataset name to validation result
    """
    results = {}

    # SCDB required columns
    scdb_required = {"usCite", "caseName", "term", "majority_opinion"}
    results["scdb"] = scdb_required.issubset(set(bundle.scdb.columns))

    # Shepards required columns
    shepards_required = {
        "cited_case_us_cite",
        "citing_case_us_cite",
        "agree",
        "shepards",
    }
    results["shepards"] = shepards_required.issubset(set(bundle.shepards.columns))

    # Overruled required columns
    overruled_required = {
        "overruled_case_us_id",
        "overruled_case_name",
        "overruling_case_name",
        "year_overruled",
    }
    results["overruled"] = overruled_required.issubset(set(bundle.overruled.columns))

    # Fake cases required columns
    fake_required = {"case_name", "us_citation"}
    results["fake_cases"] = fake_required.issubset(set(bundle.fake_cases.columns))

    return results
