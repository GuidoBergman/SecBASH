"""LLM client module.

Handles API calls to LLM providers with fallback chain:
1. OpenRouter (LlamaGuard)
2. OpenAI
3. Anthropic
4. Fail-open on exhausted retries
"""


def query_llm(prompt: str) -> str:
    """Query the LLM with fallback chain.

    Args:
        prompt: The prompt to send to the LLM.

    Returns:
        The LLM response text.

    Raises:
        ConnectionError: If all providers fail.
    """
    raise NotImplementedError("LLM client not yet implemented")


def query_openrouter(prompt: str) -> str:
    """Query OpenRouter with LlamaGuard model."""
    raise NotImplementedError("OpenRouter client not yet implemented")


def query_openai(prompt: str) -> str:
    """Query OpenAI API."""
    raise NotImplementedError("OpenAI client not yet implemented")


def query_anthropic(prompt: str) -> str:
    """Query Anthropic API."""
    raise NotImplementedError("Anthropic client not yet implemented")
