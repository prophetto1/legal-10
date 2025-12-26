# Legal-10

**A Chained Legal Reasoning Benchmark for Large Language Models**

---

## The Problem

Existing legal AI benchmarks evaluate models on **independent, parallel tasks**. But legal reasoning doesn't work that way.

A lawyer researching case law performs **sequential, dependent operations**: find relevant authority → verify it's still good law → extract the holding → apply it to new facts → synthesize into analysis.

## The Chain

The benchmark consists of seven steps across three phases.

### Rule Phase

This phase establishes the legal foundation.

### Application Phase

This phase applies rules to facts.

### Conclusion Phase

This phase synthesizes the analysis.

---

## Quick Start

```bash
git clone https://github.com/prophetto1/legal-10.git
cd legal-10
pip install -r requirements.txt
```
