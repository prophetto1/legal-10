# Legal-10 Data Schemas Reference

**Source:** HuggingFace `reglab/legal_hallucinations_paper_data`
**Updated:** 2025-12-26
**Spec Reference:** See `L10_AGENTIC_SPEC.md` for authoritative chain schemas

---

## 1. Source Files (`/sources/`)

### 1.1 SCDB_2022_01_caseCentered_Citation.csv
**Size:** 2.95 MB
**Description:** Supreme Court Database - case-centered citation format

| Column | Description |
|--------|-------------|
| `caseId` | Unique case identifier |
| `docketId` | Docket identifier |
| `caseIssuesId` | Case issues identifier |
| `voteId` | Vote identifier |
| `dateDecision` | Decision date |
| `decisionType` | Type of decision |
| `usCite` | U.S. Reports citation (e.g., "347 U.S. 483") |
| `sctCite` | Supreme Court Reporter citation |
| `ledCite` | Lawyers' Edition citation |
| `lexisCite` | LexisNexis citation |
| `term` | Court term (year) |
| `naturalCourt` | Natural court identifier |
| `chief` | Chief Justice |
| `docket` | Docket number |
| `caseName` | Case name (e.g., "Brown v. Board of Education") |
| `dateArgument` | Argument date |
| `dateRearg` | Reargument date |
| `petitioner` | Petitioner category |
| `petitionerState` | Petitioner state |
| `respondent` | Respondent category |
| `respondentState` | Respondent state |
| `jurisdiction` | Jurisdiction type |
| `adminAction` | Administrative action |
| `adminActionState` | Admin action state |
| `threeJudgeFdc` | Three-judge FDC flag |
| `caseOrigin` | Case origin court |
| `caseOriginState` | Origin state |
| `caseSource` | Case source court |
| `caseSourceState` | Source state |
| `lcDisagreement` | Lower court disagreement |
| `certReason` | Cert reason |
| `lcDisposition` | Lower court disposition |
| `lcDispositionDirection` | LC disposition direction |
| `declarationUncon` | Declaration of unconstitutionality |
| `caseDisposition` | **Case disposition (coded)** - key field |
| `caseDispositionUnusual` | Unusual disposition flag |
| `partyWinning` | **Winning party (1/0/2)** - key field |
| `precedentAlteration` | Precedent alteration |
| `voteUnclear` | Unclear vote flag |
| `issue` | Issue code |
| `issueArea` | **Issue area (coded)** - key field |
| `decisionDirection` | Decision direction |
| `decisionDirectionDissent` | Dissent direction |
| `authorityDecision1` | Authority for decision 1 |
| `authorityDecision2` | Authority for decision 2 |
| `lawType` | Law type |
| `lawSupp` | Law supplemental |
| `lawMinor` | Law minor |
| `majOpinWriter` | **Majority opinion writer (coded)** - key field |
| `majOpinAssigner` | Majority opinion assigner |
| `splitVote` | Split vote indicator |
| `majVotes` | Majority votes count |
| `minVotes` | Minority votes count |

---

### 1.2 shepards_data.csv
**Size:** 1 GB (Git LFS)
**Description:** Shepard's citator data - case citation relationships

| Column | Description |
|--------|-------------|
| `cited_case` | Cited case identifier |
| `citing_case` | Citing case identifier |
| `citing_court` | Citing court |
| `citing_opinion_type` | Opinion type |
| `shepards` | **Shepard's signal** (followed, distinguished, criticized, overrul, etc.) |
| `appeals_court` | Appeals court flag |
| `district_court` | District court flag |
| `misc_citing_court` | Misc court flag |
| `fed_specialized_ct` | Federal specialized court flag |
| `citing_body_not_ct` | Non-court citing body |
| `state_court` | State court flag |
| `supreme_court` | **Supreme Court flag** - used for filtering |
| `year_correct` | Year correctness flag |
| `citing_case_year` | Year of citing case |
| `cited_case_year` | Year of cited case |
| `us_spaeth_cited_case` | US cite for cited case (Spaeth) |
| `led_spaeth_cited_case` | LED cite for cited case |
| `docket_spaeth_cited_case` | Docket for cited case |
| `term_spaeth_cited_case` | Term for cited case |
| `us_spaeth_citing_case` | US cite for citing case |
| `led_spaeth_citing_case` | LED cite for citing case |
| `docket_spaeth_citing_case` | Docket for citing case |
| `term_spaeth_citing_case` | Term for citing case |
| `cited_usid` | Cited case US ID |
| `citing_case_name` | Citing case name |
| `citing_case_us_cite` | Citing case US citation |
| `cited_case_name` | Cited case name |
| `cited_case_us_cite` | Cited case US citation |
| `agree` | **Agreement flag (1=agree, 0=disagree)** - derived field |

**Shepard's Signal Values Used:**
- `followed` → agree=1
- `parallel` → agree=1
- `distinguished` → agree=0
- `criticized` → agree=0
- `limit` → agree=0
- `questioned` → agree=0
- `overrul` → agree=0

---

### 1.3 fowler_scores.csv
**Size:** 1.76 MB
**Description:** Judge importance/authority scores

| Column | Type | Description |
|--------|------|-------------|
| `year` | int | Year |
| `auth_score` | float | Authority score |
| `pauth_score` | float | **Probability authority score** - used for importance |
| `lex_id` | string | LexisNexis citation ID (join key) |

---

### 1.4 scotus_overruled_db.csv
**Size:** 36.7 kB
**Description:** SCOTUS overruling relationships (288 rows)

| Column | Description |
|--------|-------------|
| `overruling_case_name` | Name of case that did the overruling |
| `year_overruled` | **Year the case was overruled** |
| `overruled_case_name` | Name of overruled case |
| `overruled_case_us_id` | US citation of overruled case (join key) |
| `overruled_case_year` | Year of original case |
| `overruled_in_full` | **Full overruling flag** |
| `overruled_case_lex_id` | LexisNexis ID of overruled case |

---

## 2. Sample Files (`/samples/`)

### 2.1 scdb_sample.csv
**Size:** 94.6 MB
**Description:** Processed SCOTUS sample with opinions (5,000 cases)

**Columns:** All SCDB columns PLUS:
| Additional Column | Description |
|-------------------|-------------|
| `majority_opinion` | **Full text of majority opinion** |
| `disposition` | Coarsened disposition (affirm/reverse/etc.) |
| `pauth_score` | Fowler importance score (merged) |

**Sampling:** 25 cases per term, stratified by year

---

### 2.2 scotus_shepards_sample.csv
**Size:** 1.32 MB
**Description:** Filtered Shepard's data for SCOTUS (5,000 pairs)

| Column | Description |
|--------|-------------|
| `cited_case` | Cited case ID |
| `citing_case` | Citing case ID |
| `citing_court` | Court type |
| `citing_opinion_type` | Opinion type |
| `shepards` | Shepard's signal |
| `appeals_court` | Flag |
| `district_court` | Flag |
| `misc_citing_court` | Flag |
| `fed_specialized_ct` | Flag |
| `citing_body_not_ct` | Flag |
| `state_court` | Flag |
| `supreme_court` | 1 (all SCOTUS) |
| `year_correct` | Flag |
| `citing_case_year` | Year |
| `cited_case_year` | Year |
| `us_spaeth_cited_case` | US cite |
| `led_spaeth_cited_case` | LED cite |
| `docket_spaeth_cited_case` | Docket |
| `term_spaeth_cited_case` | Term |
| `us_spaeth_citing_case` | US cite |
| `led_spaeth_citing_case` | LED cite |
| `docket_spaeth_citing_case` | Docket |
| `term_spaeth_citing_case` | Term |
| `cited_usid` | US ID |
| `citing_case_name` | **Citing case name** |
| `citing_case_us_cite` | **Citing case US citation** |
| `cited_case_name` | **Cited case name** |
| `cited_case_us_cite` | **Cited case US citation** |
| `agree` | **1=agree (followed/parallel), 0=disagree** |

---

### 2.3 fake_cases.csv
**Size:** 78.6 kB
**Description:** Fabricated cases for hallucination testing (999 rows)

| Column | Description |
|--------|-------------|
| `case_name` | Fabricated case name |
| `us_citation` | Fabricated US citation |
| `fd_citation` | Fabricated Federal Reporter citation |
| `fsupp_citation` | Fabricated Federal Supplement citation |

---

### 2.4 fd_sample.csv
**Size:** 104 MB
**Description:** Court of Appeals sample from CAP (5,000 cases)

Contains full CAP JSON structure with:
- `id`, `name`, `decision_date`
- `court` (with `id`, `slug`, etc.)
- `casebody` (with opinions, judges, etc.)
- `citations` (array)
- Derived: `year`, `majority_author`, `circuit`, `stratum`

---

### 2.5 fsupp_sample.csv
**Size:** 137 MB
**Description:** District Court sample from CAP (5,000 cases)

Same structure as `fd_sample.csv` with:
- Derived: `state` (instead of `circuit`)

---

### 2.6 songer_sample.csv
**Size:** 394 kB
**Description:** Court of Appeals sample from Songer DB (5,000 cases)

| Key Columns | Description |
|-------------|-------------|
| `case_name` | Case name |
| `year` | Decision year |
| `circuit` | Circuit number (0=DC) |
| `treat` | Treatment code → `disposition` |

---

## 3. Data Joins for L10 Agentic Chain

### Chain Instance Construction (from data.py logic)

```sql
-- Pseudocode for chain instance join
SELECT
    s.caseName, s.usCite, s.term, s.majOpinWriter,
    s.caseDisposition, s.issueArea, s.lexisCite,
    s.majority_opinion,
    sh.citing_case_name, sh.citing_case_us_cite,
    sh.cited_case_name, sh.cited_case_us_cite,
    sh.agree AS doctrinal_agreement,
    o.year_overruled, o.overruling_case_name, o.overruled_in_full
FROM scdb_sample s
LEFT JOIN scotus_shepards_sample sh
    ON s.usCite = sh.cited_case_us_cite
LEFT JOIN scotus_overruled_db o
    ON s.usCite = o.overruled_case_us_id
```

### Join Keys Summary

| Source A | Key | Source B | Key |
|----------|-----|----------|-----|
| SCDB | `lexisCite` | fowler_scores | `lex_id` |
| SCDB | `usCite` | scotus_shepards | `cited_case_us_cite` |
| SCDB | `usCite` | scotus_overruled | `overruled_case_us_id` |
| shepards_data | `citing_case` / `cited_case` | SCDB | `lex_id` |

---

## 4. Python Data Models

> **Note:** For authoritative schemas, see `L10_AGENTIC_SPEC.md` §3.

### CourtCase (L10 Spec §3.1)
```python
@dataclass(frozen=True)
class CourtCase:
    us_cite: str                    # "347 U.S. 483"
    case_name: str                  # "Brown v. Board of Education"
    term: int                       # SCDB term (year)
    maj_opin_writer: int | None     # SCDB majOpinWriter code
    case_disposition: int | None    # SCDB caseDisposition code
    party_winning: int | None       # SCDB partyWinning (1/0/2)
    issue_area: int | None          # SCDB issueArea code
    majority_opinion: str | None    # Full opinion text
    lexis_cite: str | None
    sct_cite: str | None
    importance: float | None        # pauth_score from fowler_scores
```

### ShepardsEdge (L10 Spec §3.2)
```python
@dataclass(frozen=True)
class ShepardsEdge:
    cited_case_us_cite: str
    citing_case_us_cite: str
    cited_case_name: str | None
    citing_case_name: str | None
    shepards: str                   # "followed", "distinguished", etc.
    agree: bool                     # True if followed/parallel
    cited_case_year: int | None
    citing_case_year: int | None
```

### ChainInstance (L10 Spec §3.4)
```python
@dataclass(frozen=True)
class ChainInstance:
    id: str                         # "pair::<cited>::<citing>"
    cited_case: CourtCase           # Always present (Tier A)
    citing_case: CourtCase | None   # May be None (Tier B)
    edge: ShepardsEdge
    overrule: OverruleRecord | None
```

---

## 5. Key Lookups (from utils.py and mappings.py)

### Disposition Codes (SCDB → Text)
```python
# From get_disposition_from_scdb_id()
1 → "stay, petition, or motion granted"
2 → "affirmed"
3 → "reversed"
4 → "reversed and remanded"
5 → "vacated and remanded"
6 → "affirmed and reversed in part"
7 → "affirmed and vacated in part"
8 → "affirmed and reversed in part and remanded"
9 → "vacated"
10 → "petition denied or appeal dismissed"
11 → "certification to or from a lower court"
```

### Justice Codes (SCDB → Name)
Located in `data/covariates/covariates_scdb_justice_name_map.csv`

---

## 6. Task-to-Data Mapping (L10 Agentic)

> **Note:** For authoritative mapping, see `L10_AGENTIC_SPEC.md` §9.

| Skill | Ground Truth Source | Key Fields |
|-------|---------------------|------------|
| S1: Known Authority | `scdb_sample.csv` | `usCite`, `caseName`, `term` |
| S2: Unknown Authority | `scotus_shepards_sample.csv` | `citing_case_us_cite` |
| S3: Validate Authority | `scotus_overruled_db.csv` | `year_overruled`, `overruled_in_full` |
| S4: Fact Extraction | `scdb_sample.csv` | `caseDisposition`, `partyWinning` |
| S5:cb / S5:rag | `scotus_shepards_sample.csv` | `agree` (bool) |
| S6: IRAC Synthesis | Chain outputs | Rubric-based |
| S7: Citation Integrity | `fake_cases.csv` + `scdb_sample.csv` | Citation existence |

---

## 7. File Size Summary

| File | Size | Rows (approx) |
|------|------|---------------|
| SCDB source | 2.95 MB | ~15,000 |
| SCDB legacy | 6.13 MB | ~30,000 |
| shepards_data | 1 GB | ~10M+ |
| scdb_sample | 94.6 MB | 5,000 |
| scotus_shepards_sample | 1.32 MB | 5,000 |
| scotus_overruled_db | 36.7 kB | 288 |
| fake_cases | 78.6 kB | 999 |
| fd_sample (COA) | 104 MB | 5,000 |
| fsupp_sample (USDC) | 137 MB | 5,000 |
| songer_sample | 394 kB | 5,000 |

---

## 8. Coverage Policy Decision (Confirmed 2025-12-25)

### The Problem

`supreme_court == 1` does **not** imply "both cases are in scdb_sample." It only implies both are SCOTUS cases in the full SCDB. Because the two 5K samples are drawn independently, we should expect missing coverage when we try to resolve `citing_case` from `scdb_sample`.

**Conclusion:** Keeping `citing_case: CourtCase | None` (or at least "text optional") is justified.

---

### Two-Tier Coverage Policy

Adopt a two-tier coverage policy that matches metric goals:

#### Tier A (Required for Chain to be Meaningful)

- **Require** `cited_case ∈ scdb_sample` AND `majority_opinion` present
- Because S4 and everything downstream depends on having the anchor case text available

#### Tier B (Optional, Drives S5-RAG Coverage)

- `citing_case` **may be missing** from `scdb_sample`
- This should **not** kill the chain
- It should **only** affect whether S5-RAG is runnable

#### Execution Strategy

- **Always run S5-CB** (diagnostic mode doesn't need citing opinion text if CB is defined as "holding-only")
- **Run S5-RAG only** when both opinions exist
- In reporting, treat missing citing opinion as `SKIPPED` (coverage), not a "model failure"

**This gives you:**
- A clean, reproducible chain dataset for S1/S3/S4/S5-CB/S7 (and later S6)
- A "high-quality subset" for S5-RAG comparisons

---

### Schema Reflection: Metadata Always Present, Text Optional

- Always resolve `citing_case` metadata from full SCDB citation file (or from the Shepards merge columns)
- But allow `citing_case.majority_opinion: None`

That way, the "case object" exists, but "text availability" is explicit.

---

### Build-Time Filtering Rules

In `builder.py`, compute flags per instance:

```python
has_cited_text = cited_case.majority_opinion is not None
has_citing_text = (citing_case is not None) and (citing_case.majority_opinion is not None)
```

**Dataset Splits:**

| Split | Condition |
|-------|-----------|
| `CHAIN_CORE` | `has_cited_text == True` |
| `CHAIN_RAG_SUBSET` | `has_cited_text == True` AND `has_citing_text == True` |

**Executor Enforcement:**
- S4 requires `has_cited_text`
- S5-RAG requires `has_citing_text`
- Otherwise mark step status `SKIPPED_COVERAGE` (not `INCORRECT`)

---

### Why This is the Best Move Right Now

1. **Avoid silently shrinking the dataset** in a way that later looks like cherry-picking
2. **Report coverage as a property of the dataset construction** ("RAG subset is N instances"), which is totally normal
3. **Keep the chain architecture stable** while still allowing later upgrades

---

### Future Upgrade Path

If we want "citing_case should always resolve" later, we need to expand the text corpus so it's not bound to `scdb_sample`.

**Clean approach** (if HF repo actually includes the opinion-text folder keyed by `lex_id`):
1. Resolve both cases from full SCDB metadata
2. Load opinion text from `scotus_majority_opinions/` by `lex_id`
3. Then coverage becomes "how many opinions exist," not "did the case land in the 5K sample"

**For v1:** The Tier A / Tier B approach is the fastest way to keep the math clean.