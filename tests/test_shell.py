"""Tests for shell module."""

from secbash.shell import get_prompt


def test_get_prompt():
    """Test default prompt string."""
    prompt = get_prompt()
    assert "secbash" in prompt.lower()


def test_get_prompt_ends_with_space():
    """Test that prompt ends with a space for readability."""
    prompt = get_prompt()
    assert prompt.endswith(" ")
