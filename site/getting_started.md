# Getting Started

How to install and run Legal-10.

## Installation

Clone the repository and install dependencies.

```bash
git clone https://github.com/jbchoo/legal-10.git
cd legal-10
pip install -r requirements.txt
```

## Verify Installation

Run the test suite to confirm everything works.

```bash
pytest tests/ -v
```

## Run Your First Chain

Here's a minimal example:

```python
from chain.runner.executor import ChainExecutor
from chain.backends.mock_backend import MockBackend

executor = ChainExecutor(backend=MockBackend())
result = executor.execute(instance)
```

## Next Steps

- Read the Architecture docs
- Explore the API Reference
- Check out the Roadmap
