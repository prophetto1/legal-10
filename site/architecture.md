# Architecture

Overview of the Legal-10 codebase structure.

## Directory Layout

```
legal-10/
├── core/           # Frozen contracts
├── chain/          # Execution engine
├── scripts/        # CLI tools
├── tests/          # 247 tests
└── legal-10-notes/ # Specifications
```

## Core Module

Contains the foundational schemas and contracts.

### Schemas

- `CourtCase` - Represents a legal case
- `ChainInstance` - A single evaluation instance
- `StepResult` - Output from each step

### Scoring

Deterministic scoring logic for each step type.

## Chain Module

The execution engine that runs evaluations.

### Steps

| Step | Name | Purpose |
|------|------|---------|
| S1 | Known Authority | Retrieve citation |
| S2 | Unknown Authority | Find citing cases |
| S3 | Validate Authority | Check overruling |
| S4 | Fact Extraction | Extract disposition |
| S5 | Distinguish Cases | Doctrinal relationship |
| S6 | IRAC Synthesis | Generate analysis |
| S7 | Citation Integrity | Verify citations |

### Backends

- `MockBackend` - For testing
- `DahlBackend` - Real LLM integration

## Data Flow

1. Load datasets from HuggingFace
2. Build chain instances
3. Execute through steps
4. Score and aggregate results
