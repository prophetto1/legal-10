"""Mock backend for testing L10 Agentic Chain.

From MVP_BUILD_ORDER.md Phase 2.
"""

from chain.backends.base import Backend


class MockBackend(Backend):
    """Mock backend that returns configurable canned responses.

    Responses are matched based on prompt substring matching.
    If no match is found, returns a default response.

    Example:
        backend = MockBackend({
            "S1": '{"holding": "test holding"}',
            "S4": '{"disposition": "reversed"}',
        })
        response = backend.complete("S1: Extract holding...")
        # Returns: '{"holding": "test holding"}'
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default_response: str = "{}",
    ) -> None:
        """Initialize mock backend with canned responses.

        Args:
            responses: Dict mapping prompt substrings to responses.
                       First matching substring wins.
            default_response: Response to return if no match found.
        """
        self._responses = responses or {}
        self._default_response = default_response
        self._call_history: list[str] = []

    def complete(self, prompt: str) -> str:
        """Return canned response based on prompt substring matching.

        Args:
            prompt: The prompt (used to match against response keys)

        Returns:
            Matched response or default_response
        """
        self._call_history.append(prompt)

        for substring, response in self._responses.items():
            if substring in prompt:
                return response

        return self._default_response

    @property
    def model_id(self) -> str:
        """Return mock model identifier."""
        return "mock"

    @property
    def call_history(self) -> list[str]:
        """Return list of prompts sent to this backend.

        Useful for test assertions.
        """
        return self._call_history.copy()

    def clear_history(self) -> None:
        """Clear the call history."""
        self._call_history.clear()
