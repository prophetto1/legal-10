# API Reference

Detailed API documentation for Legal-10.

## ChainExecutor

The main entry point for running evaluations.

### Constructor

```python
ChainExecutor(backend, steps=None)
```

**Parameters:**

- `backend` - The LLM backend to use
- `steps` - Optional list of steps (uses defaults if not provided)

### Methods

#### execute

```python
def execute(self, instance: ChainInstance) -> ChainResult
```

Runs all steps on a single instance.

**Parameters:**

- `instance` - The chain instance to evaluate

**Returns:**

- `ChainResult` with step-by-step scores

---

## Steps

All steps inherit from the base `Step` class.

### S1KnownAuthority

Retrieves citation and metadata for a given case.

| Input | Output | Ground Truth |
|-------|--------|--------------|
| Case name | Citation | `cited_case.us_cite` |

### S2UnknownAuthority

Finds cases that cite the anchor case.

### S3ValidateAuthority

Determines if a case has been overruled.

### S4FactExtraction

Extracts disposition and winning party.

### S5DistinguishCB

Determines doctrinal relationship using metadata.

### S5DistinguishRAG

Determines doctrinal relationship using full text.

### S6IRACSynthesis

Generates structured legal analysis.

### S7CitationIntegrity

Verifies no fabricated citations exist.

---

## Backends

### MockBackend

For testing without API calls.

```python
backend = MockBackend()
```

### Creating Custom Backends

Implement the `Backend` protocol:

```python
class MyBackend:
    def complete(self, prompt: str) -> str:
        # Your implementation
        pass
```
