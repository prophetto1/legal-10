"""Dataset builder for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 3.
Builds indexes, joins to ChainInstance, computes coverage flags.
"""

from dataclasses import dataclass
from typing import Iterator

import pandas as pd

from chain.datasets.loaders import DatasetBundle
from core.ids.canonical import pair_id
from core.schemas.case import CourtCase, OverruleRecord, ShepardsEdge
from core.schemas.chain import ChainInstance


@dataclass
class CoverageReport:
    """Coverage statistics for the dataset.

    Attributes:
        total_edges: Total Shepard's edges in dataset
        cited_resolved: Edges where cited_case found in SCDB
        citing_resolved: Edges where citing_case found in SCDB
        chain_core: Instances with cited_case text (Tier A)
        chain_rag_subset: Instances with both case texts (Tier A + B)
    """

    total_edges: int
    cited_resolved: int
    citing_resolved: int
    chain_core: int
    chain_rag_subset: int

    @property
    def cited_percent(self) -> float:
        """Percentage of edges with cited_case resolved."""
        if self.total_edges == 0:
            return 0.0
        return 100.0 * self.cited_resolved / self.total_edges

    @property
    def citing_percent(self) -> float:
        """Percentage of edges with citing_case resolved."""
        if self.total_edges == 0:
            return 0.0
        return 100.0 * self.citing_resolved / self.total_edges

    def __str__(self) -> str:
        """Format coverage report for display."""
        return (
            f"Total Shepard's edges:     {self.total_edges:,}\n"
            f"cited_case resolved:       {self.cited_resolved:,} ({self.cited_percent:.1f}%)\n"
            f"citing_case resolved:      {self.citing_resolved:,} ({self.citing_percent:.1f}%)\n"
            f"CHAIN_CORE:                {self.chain_core:,}\n"
            f"CHAIN_RAG_SUBSET:          {self.chain_rag_subset:,}"
        )


class DatasetBuilder:
    """Build indexes and ChainInstances from raw datasets.

    Indexes:
        case_by_us_cite: Map US citation -> CourtCase
        overrule_by_us_cite: Map US citation -> OverruleRecord
        fake_us_cites: Set of fake US citations
        fake_case_names: Set of fake case names
    """

    def __init__(self, bundle: DatasetBundle) -> None:
        """Initialize builder with dataset bundle.

        Args:
            bundle: DatasetBundle containing all raw datasets
        """
        self._bundle = bundle
        self._case_by_us_cite: dict[str, CourtCase] = {}
        self._overrule_by_us_cite: dict[str, OverruleRecord] = {}
        self._fake_us_cites: set[str] = set()
        self._fake_case_names: set[str] = set()
        self._built = False

    def build_indexes(self) -> None:
        """Build all indexes from raw datasets."""
        self._build_case_index()
        self._build_overrule_index()
        self._build_fake_sets()
        self._built = True

    def _build_case_index(self) -> None:
        """Build case_by_us_cite index from SCDB."""
        for _, row in self._bundle.scdb.iterrows():
            us_cite = row.get("usCite")
            if pd.isna(us_cite) or not us_cite:
                continue

            # Extract majority opinion (may be None/NaN)
            majority_opinion = row.get("majority_opinion")
            if pd.isna(majority_opinion):
                majority_opinion = None

            # Extract optional numeric fields
            maj_opin_writer = self._safe_int(row.get("majOpinWriter"))
            case_disposition = self._safe_int(row.get("caseDisposition"))
            party_winning = self._safe_int(row.get("partyWinning"))
            issue_area = self._safe_int(row.get("issueArea"))
            term = self._safe_int(row.get("term")) or 0

            # Extract optional string fields
            lexis_cite = self._safe_str(row.get("lexisCite"))
            sct_cite = self._safe_str(row.get("sctCite"))

            # Extract importance score
            importance = self._safe_float(row.get("pauth_score"))

            case = CourtCase(
                us_cite=str(us_cite),
                case_name=str(row.get("caseName", "")),
                term=term,
                maj_opin_writer=maj_opin_writer,
                case_disposition=case_disposition,
                party_winning=party_winning,
                issue_area=issue_area,
                majority_opinion=majority_opinion,
                lexis_cite=lexis_cite,
                sct_cite=sct_cite,
                importance=importance,
            )
            self._case_by_us_cite[str(us_cite)] = case

    def _build_overrule_index(self) -> None:
        """Build overrule_by_us_cite index from overruled DB."""
        for _, row in self._bundle.overruled.iterrows():
            us_id = row.get("overruled_case_us_id")
            if pd.isna(us_id) or not us_id:
                continue

            year_overruled = self._safe_int(row.get("year_overruled"))
            overruled_in_full = bool(row.get("overruled_in_full", False))

            record = OverruleRecord(
                overruled_case_us_id=str(us_id),
                overruled_case_name=str(row.get("overruled_case_name", "")),
                overruling_case_name=str(row.get("overruling_case_name", "")),
                year_overruled=year_overruled,
                overruled_in_full=overruled_in_full,
            )
            self._overrule_by_us_cite[str(us_id)] = record

    def _build_fake_sets(self) -> None:
        """Build fake_us_cites and fake_case_names sets."""
        for _, row in self._bundle.fake_cases.iterrows():
            us_cite = row.get("us_citation")
            if not pd.isna(us_cite) and us_cite:
                self._fake_us_cites.add(str(us_cite))

            case_name = row.get("case_name")
            if not pd.isna(case_name) and case_name:
                self._fake_case_names.add(str(case_name))

    @staticmethod
    def _safe_int(value) -> int | None:
        """Safely convert value to int or None."""
        if pd.isna(value):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(value) -> float | None:
        """Safely convert value to float or None."""
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_str(value) -> str | None:
        """Safely convert value to str or None."""
        if pd.isna(value):
            return None
        return str(value)

    @property
    def case_by_us_cite(self) -> dict[str, CourtCase]:
        """Get case index (build first if needed)."""
        if not self._built:
            self.build_indexes()
        return self._case_by_us_cite

    @property
    def overrule_by_us_cite(self) -> dict[str, OverruleRecord]:
        """Get overrule index (build first if needed)."""
        if not self._built:
            self.build_indexes()
        return self._overrule_by_us_cite

    @property
    def fake_us_cites(self) -> set[str]:
        """Get fake US citations set (build first if needed)."""
        if not self._built:
            self.build_indexes()
        return self._fake_us_cites

    @property
    def fake_case_names(self) -> set[str]:
        """Get fake case names set (build first if needed)."""
        if not self._built:
            self.build_indexes()
        return self._fake_case_names

    def build_chain_instances(self) -> list[ChainInstance]:
        """Build all ChainInstances from Shepard's edges.

        Returns:
            List of ChainInstance objects
        """
        if not self._built:
            self.build_indexes()

        instances = []
        for _, row in self._bundle.shepards.iterrows():
            instance = self._build_instance_from_row(row)
            if instance is not None:
                instances.append(instance)

        return instances

    def iter_chain_instances(self) -> Iterator[ChainInstance]:
        """Iterate over ChainInstances (memory-efficient).

        Yields:
            ChainInstance objects
        """
        if not self._built:
            self.build_indexes()

        for _, row in self._bundle.shepards.iterrows():
            instance = self._build_instance_from_row(row)
            if instance is not None:
                yield instance

    def _build_instance_from_row(self, row: pd.Series) -> ChainInstance | None:
        """Build a single ChainInstance from a Shepard's row.

        Args:
            row: Row from shepards DataFrame

        Returns:
            ChainInstance or None if cited_case not resolved
        """
        cited_us_cite = row.get("cited_case_us_cite")
        citing_us_cite = row.get("citing_case_us_cite")

        if pd.isna(cited_us_cite) or not cited_us_cite:
            return None

        cited_us_cite = str(cited_us_cite)
        citing_us_cite = str(citing_us_cite) if not pd.isna(citing_us_cite) else ""

        # Lookup cited case (required for Tier A)
        cited_case = self._case_by_us_cite.get(cited_us_cite)
        if cited_case is None:
            return None  # Cannot build instance without cited case

        # Lookup citing case (optional for Tier B)
        citing_case = self._case_by_us_cite.get(citing_us_cite)

        # Build edge
        agree_val = row.get("agree")
        agree = bool(agree_val) if not pd.isna(agree_val) else False

        edge = ShepardsEdge(
            cited_case_us_cite=cited_us_cite,
            citing_case_us_cite=citing_us_cite,
            cited_case_name=self._safe_str(row.get("cited_case_name")),
            citing_case_name=self._safe_str(row.get("citing_case_name")),
            shepards=self._safe_str(row.get("shepards")) or "",
            agree=agree,
            cited_case_year=self._safe_int(row.get("cited_case_year")),
            citing_case_year=self._safe_int(row.get("citing_case_year")),
        )

        # Lookup overrule record
        overrule = self._overrule_by_us_cite.get(cited_us_cite)

        # Generate instance ID
        instance_id = pair_id(cited_us_cite, citing_us_cite)

        return ChainInstance(
            id=instance_id,
            cited_case=cited_case,
            citing_case=citing_case,
            edge=edge,
            overrule=overrule,
        )

    def compute_coverage(self) -> CoverageReport:
        """Compute coverage statistics.

        Returns:
            CoverageReport with all statistics
        """
        if not self._built:
            self.build_indexes()

        total_edges = len(self._bundle.shepards)
        cited_resolved = 0
        citing_resolved = 0
        chain_core = 0
        chain_rag_subset = 0

        for _, row in self._bundle.shepards.iterrows():
            cited_us_cite = row.get("cited_case_us_cite")
            citing_us_cite = row.get("citing_case_us_cite")

            if pd.isna(cited_us_cite) or not cited_us_cite:
                continue

            cited_us_cite = str(cited_us_cite)
            citing_us_cite = str(citing_us_cite) if not pd.isna(citing_us_cite) else ""

            # Check cited case resolution
            cited_case = self._case_by_us_cite.get(cited_us_cite)
            if cited_case is not None:
                cited_resolved += 1

                # Check if cited case has text (Tier A)
                has_cited_text = cited_case.majority_opinion is not None
                if has_cited_text:
                    chain_core += 1

                    # Check citing case resolution and text (Tier B)
                    citing_case = self._case_by_us_cite.get(citing_us_cite)
                    if citing_case is not None:
                        citing_resolved += 1
                        has_citing_text = citing_case.majority_opinion is not None
                        if has_citing_text:
                            chain_rag_subset += 1
                    elif citing_us_cite:
                        # Citing case exists but not in SCDB sample
                        pass
            else:
                # Check citing even if cited not resolved
                citing_case = self._case_by_us_cite.get(citing_us_cite)
                if citing_case is not None:
                    citing_resolved += 1

        return CoverageReport(
            total_edges=total_edges,
            cited_resolved=cited_resolved,
            citing_resolved=citing_resolved,
            chain_core=chain_core,
            chain_rag_subset=chain_rag_subset,
        )
