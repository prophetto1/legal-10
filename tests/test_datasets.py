"""Tests for dataset loaders and builder - Phase 3 Contract Lock.

Exit Criteria:
- All 4 CSVs load (scdb_sample, scotus_shepards_sample, scotus_overruled_db, fake_cases)
- case_by_us_cite index built
- overrule_by_us_cite index built
- fake_us_cites and fake_case_names sets built
- 5 sample ChainInstance objects validate against schema
"""

import pandas as pd
import pytest

from chain.datasets.builder import CoverageReport, DatasetBuilder
from chain.datasets.loaders import DatasetBundle, validate_datasets
from core.schemas.case import CourtCase, OverruleRecord, ShepardsEdge
from core.schemas.chain import ChainInstance


# =============================================================================
# Fixtures: Mock DataFrames
# =============================================================================


@pytest.fixture
def mock_scdb() -> pd.DataFrame:
    """Mock SCDB sample with 3 cases."""
    return pd.DataFrame(
        {
            "usCite": ["347 U.S. 483", "349 U.S. 294", "410 U.S. 113"],
            "caseName": [
                "Brown v. Board of Education",
                "Bolling v. Sharpe",
                "Roe v. Wade",
            ],
            "term": [1954, 1954, 1973],
            "majOpinWriter": [101, 102, 103],
            "caseDisposition": [3, 3, 4],
            "partyWinning": [1, 1, 1],
            "issueArea": [2, 2, 4],
            "majority_opinion": [
                "We conclude that in the field of public education...",
                "We have this day held...",
                None,  # No opinion for Roe (test coverage)
            ],
            "lexisCite": ["1954 U.S. LEXIS 123", "1954 U.S. LEXIS 456", None],
            "sctCite": ["74 S. Ct. 686", "75 S. Ct. 753", None],
            "pauth_score": [0.95, 0.85, 0.75],
        }
    )


@pytest.fixture
def mock_shepards() -> pd.DataFrame:
    """Mock Shepard's sample with 4 edges."""
    return pd.DataFrame(
        {
            "cited_case_us_cite": [
                "347 U.S. 483",
                "347 U.S. 483",
                "349 U.S. 294",
                "999 U.S. 999",  # Not in SCDB
            ],
            "citing_case_us_cite": [
                "349 U.S. 294",
                "410 U.S. 113",
                "410 U.S. 113",
                "347 U.S. 483",
            ],
            "cited_case_name": ["Brown", "Brown", "Bolling", "Unknown"],
            "citing_case_name": ["Bolling", "Roe", "Roe", "Brown"],
            "shepards": ["followed", "followed", "distinguished", "criticized"],
            "agree": [1, 1, 0, 0],
            "cited_case_year": [1954, 1954, 1954, 1900],
            "citing_case_year": [1954, 1973, 1973, 1954],
        }
    )


@pytest.fixture
def mock_overruled() -> pd.DataFrame:
    """Mock overruled DB with 2 records."""
    return pd.DataFrame(
        {
            "overruled_case_us_id": ["198 U.S. 45", "163 U.S. 537"],
            "overruled_case_name": [
                "Lochner v. New York",
                "Plessy v. Ferguson",
            ],
            "overruling_case_name": [
                "West Coast Hotel v. Parrish",
                "Brown v. Board of Education",
            ],
            "year_overruled": [1937, 1954],
            "overruled_in_full": [True, True],
        }
    )


@pytest.fixture
def mock_fake_cases() -> pd.DataFrame:
    """Mock fake cases with 3 entries."""
    return pd.DataFrame(
        {
            "case_name": ["Fake v. Case", "Made v. Up", "Not v. Real"],
            "us_citation": ["999 U.S. 1", "999 U.S. 2", "999 U.S. 3"],
            "fd_citation": ["999 F.2d 1", "999 F.2d 2", "999 F.2d 3"],
            "fsupp_citation": ["999 F. Supp. 1", "999 F. Supp. 2", "999 F. Supp. 3"],
        }
    )


@pytest.fixture
def mock_bundle(
    mock_scdb: pd.DataFrame,
    mock_shepards: pd.DataFrame,
    mock_overruled: pd.DataFrame,
    mock_fake_cases: pd.DataFrame,
) -> DatasetBundle:
    """Mock dataset bundle."""
    return DatasetBundle(
        scdb=mock_scdb,
        shepards=mock_shepards,
        overruled=mock_overruled,
        fake_cases=mock_fake_cases,
    )


# =============================================================================
# Test: DatasetBundle Validation
# =============================================================================


class TestDatasetBundle:
    """Tests for DatasetBundle structure."""

    def test_bundle_contains_all_datasets(self, mock_bundle: DatasetBundle) -> None:
        """Bundle has all 4 datasets."""
        assert mock_bundle.scdb is not None
        assert mock_bundle.shepards is not None
        assert mock_bundle.overruled is not None
        assert mock_bundle.fake_cases is not None

    def test_validate_datasets_all_pass(self, mock_bundle: DatasetBundle) -> None:
        """All datasets pass validation."""
        results = validate_datasets(mock_bundle)
        assert results["scdb"] is True
        assert results["shepards"] is True
        assert results["overruled"] is True
        assert results["fake_cases"] is True

    def test_validate_datasets_missing_column(self) -> None:
        """Validation fails when required column missing."""
        bad_scdb = pd.DataFrame({"wrong_column": [1, 2, 3]})
        bundle = DatasetBundle(
            scdb=bad_scdb,
            shepards=pd.DataFrame(
                {
                    "cited_case_us_cite": [],
                    "citing_case_us_cite": [],
                    "agree": [],
                    "shepards": [],
                }
            ),
            overruled=pd.DataFrame(
                {
                    "overruled_case_us_id": [],
                    "overruled_case_name": [],
                    "overruling_case_name": [],
                    "year_overruled": [],
                }
            ),
            fake_cases=pd.DataFrame({"case_name": [], "us_citation": []}),
        )
        results = validate_datasets(bundle)
        assert results["scdb"] is False


# =============================================================================
# Test: Index Building
# =============================================================================


class TestIndexBuilding:
    """Tests for DatasetBuilder index construction."""

    def test_case_by_us_cite_built(self, mock_bundle: DatasetBundle) -> None:
        """case_by_us_cite index built correctly."""
        builder = DatasetBuilder(mock_bundle)
        builder.build_indexes()

        assert len(builder.case_by_us_cite) == 3
        assert "347 U.S. 483" in builder.case_by_us_cite
        assert "349 U.S. 294" in builder.case_by_us_cite
        assert "410 U.S. 113" in builder.case_by_us_cite

    def test_case_index_values_are_court_cases(
        self, mock_bundle: DatasetBundle
    ) -> None:
        """Index values are CourtCase instances."""
        builder = DatasetBuilder(mock_bundle)
        builder.build_indexes()

        case = builder.case_by_us_cite["347 U.S. 483"]
        assert isinstance(case, CourtCase)
        assert case.us_cite == "347 U.S. 483"
        assert case.case_name == "Brown v. Board of Education"
        assert case.term == 1954

    def test_overrule_by_us_cite_built(self, mock_bundle: DatasetBundle) -> None:
        """overrule_by_us_cite index built correctly."""
        builder = DatasetBuilder(mock_bundle)
        builder.build_indexes()

        assert len(builder.overrule_by_us_cite) == 2
        assert "198 U.S. 45" in builder.overrule_by_us_cite
        assert "163 U.S. 537" in builder.overrule_by_us_cite

    def test_overrule_index_values_are_records(
        self, mock_bundle: DatasetBundle
    ) -> None:
        """Index values are OverruleRecord instances."""
        builder = DatasetBuilder(mock_bundle)
        builder.build_indexes()

        record = builder.overrule_by_us_cite["198 U.S. 45"]
        assert isinstance(record, OverruleRecord)
        assert record.overruled_case_name == "Lochner v. New York"
        assert record.year_overruled == 1937

    def test_fake_us_cites_set_built(self, mock_bundle: DatasetBundle) -> None:
        """fake_us_cites set built correctly."""
        builder = DatasetBuilder(mock_bundle)
        builder.build_indexes()

        assert len(builder.fake_us_cites) == 3
        assert "999 U.S. 1" in builder.fake_us_cites
        assert "999 U.S. 2" in builder.fake_us_cites
        assert "999 U.S. 3" in builder.fake_us_cites

    def test_fake_case_names_set_built(self, mock_bundle: DatasetBundle) -> None:
        """fake_case_names set built correctly."""
        builder = DatasetBuilder(mock_bundle)
        builder.build_indexes()

        assert len(builder.fake_case_names) == 3
        assert "Fake v. Case" in builder.fake_case_names
        assert "Made v. Up" in builder.fake_case_names


# =============================================================================
# Test: ChainInstance Building
# =============================================================================


class TestChainInstanceBuilding:
    """Tests for ChainInstance construction."""

    def test_builds_instances_from_shepards(self, mock_bundle: DatasetBundle) -> None:
        """Builds ChainInstances from Shepard's edges."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        # Should build 3 instances (4th edge has cited_case not in SCDB)
        assert len(instances) == 3

    def test_instance_has_cited_case(self, mock_bundle: DatasetBundle) -> None:
        """ChainInstance has cited_case populated."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        for inst in instances:
            assert inst.cited_case is not None
            assert isinstance(inst.cited_case, CourtCase)

    def test_instance_has_edge(self, mock_bundle: DatasetBundle) -> None:
        """ChainInstance has edge populated."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        for inst in instances:
            assert inst.edge is not None
            assert isinstance(inst.edge, ShepardsEdge)

    def test_instance_citing_case_may_be_none(
        self, mock_bundle: DatasetBundle
    ) -> None:
        """ChainInstance citing_case may be None or CourtCase."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        # All our mock citing cases are in SCDB, so all should be populated
        for inst in instances:
            if inst.citing_case is not None:
                assert isinstance(inst.citing_case, CourtCase)

    def test_instance_has_correct_id(self, mock_bundle: DatasetBundle) -> None:
        """ChainInstance has pair_id format."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        assert instances[0].id == "pair::347_us_483::349_us_294"

    def test_instance_has_cited_text_property(
        self, mock_bundle: DatasetBundle
    ) -> None:
        """has_cited_text property works."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        # First instance: Brown has opinion text
        assert instances[0].has_cited_text is True

    def test_instance_has_citing_text_property(
        self, mock_bundle: DatasetBundle
    ) -> None:
        """has_citing_text property works."""
        builder = DatasetBuilder(mock_bundle)
        instances = builder.build_chain_instances()

        # First instance: Brown -> Bolling, both have text
        assert instances[0].has_citing_text is True

        # Second instance: Brown -> Roe, Roe has no opinion
        assert instances[1].has_citing_text is False

    def test_iter_chain_instances(self, mock_bundle: DatasetBundle) -> None:
        """Iterator yields same instances as list builder."""
        builder = DatasetBuilder(mock_bundle)
        list_instances = builder.build_chain_instances()
        iter_instances = list(builder.iter_chain_instances())

        assert len(list_instances) == len(iter_instances)


# =============================================================================
# Test: Coverage Report
# =============================================================================


class TestCoverageReport:
    """Tests for coverage computation."""

    def test_coverage_report_fields(self, mock_bundle: DatasetBundle) -> None:
        """CoverageReport has all expected fields."""
        builder = DatasetBuilder(mock_bundle)
        coverage = builder.compute_coverage()

        assert isinstance(coverage, CoverageReport)
        assert coverage.total_edges == 4
        assert coverage.cited_resolved == 3  # 3 of 4 edges have cited in SCDB
        assert coverage.citing_resolved >= 0

    def test_coverage_chain_core(self, mock_bundle: DatasetBundle) -> None:
        """CHAIN_CORE counts instances with cited text."""
        builder = DatasetBuilder(mock_bundle)
        coverage = builder.compute_coverage()

        # Brown and Bolling have text, Roe doesn't
        # Edges with Brown or Bolling as cited should count
        assert coverage.chain_core >= 2

    def test_coverage_rag_subset(self, mock_bundle: DatasetBundle) -> None:
        """CHAIN_RAG_SUBSET counts instances with both texts."""
        builder = DatasetBuilder(mock_bundle)
        coverage = builder.compute_coverage()

        # Only Brown -> Bolling has both texts
        assert coverage.chain_rag_subset >= 1

    def test_coverage_percentages(self, mock_bundle: DatasetBundle) -> None:
        """Coverage percentages calculated correctly."""
        builder = DatasetBuilder(mock_bundle)
        coverage = builder.compute_coverage()

        assert 0 <= coverage.cited_percent <= 100
        assert 0 <= coverage.citing_percent <= 100

    def test_coverage_str_format(self, mock_bundle: DatasetBundle) -> None:
        """Coverage __str__ produces expected format."""
        builder = DatasetBuilder(mock_bundle)
        coverage = builder.compute_coverage()
        output = str(coverage)

        assert "Total Shepard's edges:" in output
        assert "cited_case resolved:" in output
        assert "citing_case resolved:" in output
        assert "CHAIN_CORE:" in output
        assert "CHAIN_RAG_SUBSET:" in output


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_scdb(self) -> None:
        """Handle empty SCDB gracefully."""
        bundle = DatasetBundle(
            scdb=pd.DataFrame(
                columns=[
                    "usCite",
                    "caseName",
                    "term",
                    "majority_opinion",
                ]
            ),
            shepards=pd.DataFrame(
                columns=[
                    "cited_case_us_cite",
                    "citing_case_us_cite",
                    "agree",
                    "shepards",
                ]
            ),
            overruled=pd.DataFrame(
                columns=[
                    "overruled_case_us_id",
                    "overruled_case_name",
                    "overruling_case_name",
                    "year_overruled",
                ]
            ),
            fake_cases=pd.DataFrame(columns=["case_name", "us_citation"]),
        )
        builder = DatasetBuilder(bundle)
        builder.build_indexes()

        assert len(builder.case_by_us_cite) == 0
        assert len(builder.build_chain_instances()) == 0

    def test_nan_values_handled(self) -> None:
        """NaN values handled without crashing."""
        scdb = pd.DataFrame(
            {
                "usCite": ["347 U.S. 483", None],
                "caseName": ["Brown", None],
                "term": [1954, None],
                "majority_opinion": [None, None],
            }
        )
        bundle = DatasetBundle(
            scdb=scdb,
            shepards=pd.DataFrame(
                {
                    "cited_case_us_cite": ["347 U.S. 483"],
                    "citing_case_us_cite": [None],
                    "agree": [None],
                    "shepards": [None],
                }
            ),
            overruled=pd.DataFrame(
                columns=[
                    "overruled_case_us_id",
                    "overruled_case_name",
                    "overruling_case_name",
                    "year_overruled",
                ]
            ),
            fake_cases=pd.DataFrame(columns=["case_name", "us_citation"]),
        )
        builder = DatasetBuilder(bundle)
        builder.build_indexes()

        # Should have 1 case (the one with valid usCite)
        assert len(builder.case_by_us_cite) == 1
