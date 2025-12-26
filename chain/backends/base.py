"""Backend ABC for L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 2.
"""

from abc import ABC, abstractmethod


class Backend(ABC):
    """Abstract base class for LLM backends.

    Backends handle the actual LLM API calls. This abstraction allows:
    - MockBackend for testing without API calls
    - Real backends (OpenAI, Anthropic, etc.) for production
    """

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Send prompt to LLM and return raw response text.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            Raw response text from the LLM
        """
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return the model identifier string.

        Returns:
            Model ID (e.g., "gpt-4", "claude-3", "mock")
        """
        pass
