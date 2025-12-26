# Roadmap

Future development plans for Legal-10.

## v1.0 (Current)

MVP Complete.

- [x] 7-step chain architecture
- [x] All steps implemented (S1-S7)
- [x] ChainExecutor with dependency resolution
- [x] S5 dual-modality (CB + RAG)
- [x] S7 citation integrity gate
- [x] MockBackend for testing
- [x] 247 tests passing
- [x] HuggingFace data integration

## v1.1 — Production Runs

- [ ] Real LLM backend integration
- [ ] Pilot run (100 instances)
- [ ] Full dataset run (CHAIN_CORE)
- [ ] JSONL + Markdown output
- [ ] Results visualization
- [ ] Reasoning Bridge Gap measurement

## v2.0 — External Benchmark Integration

### HELM Integration

| L10 Step | HELM Scenario |
|----------|---------------|
| S3 Validate Authority | LegalBench overruling |
| S4 Fact Extraction | LegalBench definition extraction |
| S5:cb Distinguish | CaseHOLD 5-way MCQ |

### Additional Benchmarks

| Benchmark | Jurisdiction | Integration Point |
|-----------|--------------|-------------------|
| CaseHOLD | US | S5:cb comparison baseline |
| LegalBench | US | S3, S4 task injection |
| LegalAgentBench | Chinese | Tool-calling evaluation |

## v2.1 — Agentic Mode

Model-controlled retrieval with tool-calling capabilities.

```python
class AgenticStep(Step):
    tools: list[Tool]
    max_turns: int = 5
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Ensure all tests pass
4. Submit a pull request
