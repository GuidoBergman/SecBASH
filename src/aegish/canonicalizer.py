"""Command canonicalization module.

Pure text transforms that normalize shell commands before validation.
No execution occurs here — only syntactic normalization so the LLM
sees what bash will actually execute.

Transforms (in bash expansion order):
1. ANSI-C quote resolution ($'\\xHH', $'\\uHHHH', $'\\UHHHHHHHH')
2. Quote normalization (ba""sh → bash)
3. Backtick → $() conversion
4. Brace expansion ({a,b} → variants)
5. Glob resolution (wildcards → matched paths)
6. Here-string extraction (<<<)
"""

import glob as glob_mod
import logging
import re
import shlex
from dataclasses import dataclass, field

import braceexpand

logger = logging.getLogger(__name__)

# Maximum number of brace expansion variants before annotating
_BRACE_VARIANT_LIMIT = 64

# Maximum number of glob matches per token before truncating
_GLOB_MATCH_LIMIT = 64


@dataclass
class CanonicalResult:
    """Result of command canonicalization."""

    text: str                                     # Canonical command text
    variants: list[str] = field(default_factory=list)  # Brace expansion variants
    here_strings: list[str] = field(default_factory=list)  # Extracted <<< content
    annotations: list[str] = field(default_factory=list)   # Normalization notes
    original: str = ""                            # Original raw input


def canonicalize(command: str) -> CanonicalResult:
    """Canonicalize a shell command through pure text transforms.

    Args:
        command: Raw shell command string.

    Returns:
        CanonicalResult with canonical text and metadata.
    """
    result = CanonicalResult(text=command, original=command)

    # Step 1: ANSI-C quote resolution
    result.text = _resolve_ansi_c_quotes(result.text, result.annotations)

    # Step 2: Quote normalization
    result.text = _normalize_quotes(result.text, result.annotations)

    # Step 3: Backtick → $() conversion
    result.text = _convert_backticks(result.text)

    # Step 4: Brace expansion
    result.text, result.variants = _expand_braces(
        result.text, result.annotations,
    )

    # Step 5: Glob resolution
    result.text = _resolve_globs(result.text, result.annotations)

    # Step 6: Here-string extraction
    result.here_strings = _extract_here_strings(result.text)

    return result


# ---------------------------------------------------------------------------
# Step 1: ANSI-C quote resolution
# ---------------------------------------------------------------------------

# Matches $'...' strings (ANSI-C quoting)
_ANSI_C_RE = re.compile(r"""\$'([^'\\]*(?:\\.[^'\\]*)*)'""")

# Named escape sequences inside $'...'
_ANSI_C_ESCAPES = {
    "a": "\a",
    "b": "\b",
    "e": "\x1b",
    "E": "\x1b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "?": "?",
}

# Individual escape sequence inside an ANSI-C string body
_ANSI_ESCAPE_RE = re.compile(
    r"""\\(?:"""
    r"""x([0-9a-fA-F]{1,2})"""       # \xHH
    r"""|([0-7]{1,3})"""              # \NNN (octal)
    r"""|u([0-9a-fA-F]{4})"""         # \uHHHH
    r"""|U([0-9a-fA-F]{8})"""         # \UHHHHHHHH
    r"""|([abeEfnrtv\\\'"?])"""       # named escapes
    r""")"""
)


def _decode_ansi_escape(m: re.Match) -> str:
    """Decode a single escape sequence match."""
    if m.group(1) is not None:      # \xHH
        return chr(int(m.group(1), 16))
    if m.group(2) is not None:      # \NNN octal
        return chr(int(m.group(2), 8))
    if m.group(3) is not None:      # \uHHHH
        return chr(int(m.group(3), 16))
    if m.group(4) is not None:      # \UHHHHHHHH
        return chr(int(m.group(4), 16))
    if m.group(5) is not None:      # named escape
        return _ANSI_C_ESCAPES[m.group(5)]
    return m.group(0)  # pragma: no cover


def _resolve_single_ansi_c(m: re.Match) -> str:
    """Resolve a single $'...' string to its literal content."""
    body = m.group(1)
    try:
        resolved = _ANSI_ESCAPE_RE.sub(_decode_ansi_escape, body)
    except (ValueError, OverflowError):
        return m.group(0)  # Return original on failure
    # If resolved content contains shell expansion chars ($ or `),
    # wrap in single quotes to preserve ANSI-C literal semantics.
    if "$" in resolved or "`" in resolved:
        escaped = resolved.replace("'", "'\\''")
        return f"'{escaped}'"
    return resolved


def _resolve_ansi_c_quotes(text: str, annotations: list[str]) -> str:
    """Resolve all ANSI-C $'...' quoting to literal characters."""
    if "$'" not in text:
        return text

    resolved, count = _ANSI_C_RE.subn(_resolve_single_ansi_c, text)
    if count > 0 and resolved != text:
        logger.debug("ANSI-C resolved %d quote(s)", count)
    # Check for partial/unmatched $' sequences
    if "$'" in resolved:
        annotations.append("ANSI_C_PARTIAL")
    return resolved


# ---------------------------------------------------------------------------
# Step 2: Quote normalization
# ---------------------------------------------------------------------------


def _normalize_quotes(text: str, annotations: list[str]) -> str:
    """Normalize shell quoting: ba""sh → bash, n\\c → nc.

    Uses shlex to split and rejoin, which removes unnecessary quoting.
    Falls back to original text on parse failure.
    """
    # Skip if text contains shell metacharacters that shlex.join would quote,
    # changing semantics (variable expansion, braces, redirections, etc.)
    if any(c in text for c in ("$", "`", "{", "|", ";", "&", "<", ">", "*", "?")):
        return text

    try:
        tokens = shlex.split(text)
        normalized = shlex.join(tokens)
        return normalized
    except ValueError:
        annotations.append("QUOTE_NORM_FAILED")
        return text


# ---------------------------------------------------------------------------
# Step 3: Backtick → $() conversion
# ---------------------------------------------------------------------------

# Matches `...` backtick command substitution (non-nested).
# Nested backticks require escaped inner backticks which is rare;
# the canonicalizer handles the common single-level case.
_BACKTICK_RE = re.compile(r"`([^`]*)`")


def _convert_backticks(text: str) -> str:
    """Convert backtick command substitutions to $() form."""
    if "`" not in text:
        return text
    return _BACKTICK_RE.sub(r"$(\1)", text)


# ---------------------------------------------------------------------------
# Step 4: Brace expansion
# ---------------------------------------------------------------------------


def _expand_braces(
    text: str, annotations: list[str],
) -> tuple[str, list[str]]:
    """Expand brace expressions and return (primary_text, all_variants).

    Uses the braceexpand library. If expansion produces >_BRACE_VARIANT_LIMIT
    variants, annotates but keeps all variants for blocklist checking.
    """
    if "{" not in text:
        return text, []

    try:
        variants = list(braceexpand.braceexpand(text))
    except Exception:
        return text, []

    if len(variants) <= 1:
        # No actual expansion happened
        return text, []

    if len(variants) > _BRACE_VARIANT_LIMIT:
        annotations.append(
            f"BRACE_LIMIT_EXCEEDED ({len(variants)} variants)"
        )

    # Primary variant is the first expansion result
    primary = variants[0]
    return primary, variants[1:]  # First is the canonical text, rest are variants


# ---------------------------------------------------------------------------
# Step 5: Glob resolution
# ---------------------------------------------------------------------------

# Glob metacharacters
_GLOB_META_RE = re.compile(r"[\*\?\[]")


def _resolve_globs(text: str, annotations: list[str]) -> str:
    """Resolve glob patterns to matched filesystem paths.

    Only resolves tokens that contain glob metacharacters and produce
    matches. Non-matching globs are left as-is (bash behavior).

    If a single glob token matches more than _GLOB_MATCH_LIMIT paths,
    the expansion is truncated and an annotation is added so the LLM
    knows the full scope of the expansion.
    """
    if not _GLOB_META_RE.search(text):
        return text

    try:
        tokens = shlex.split(text)
    except ValueError:
        return text

    resolved_tokens = []
    changed = False
    for token in tokens:
        if _GLOB_META_RE.search(token):
            matches = sorted(glob_mod.glob(token))
            if matches:
                if len(matches) > _GLOB_MATCH_LIMIT:
                    annotations.append(
                        f"GLOB_EXPANSION_CAPPED: '{token}' matched "
                        f"{len(matches)} paths, showing first "
                        f"{_GLOB_MATCH_LIMIT}. The actual command "
                        f"will operate on ALL {len(matches)} paths."
                    )
                    matches = matches[:_GLOB_MATCH_LIMIT]
                resolved_tokens.extend(matches)
                changed = True
            else:
                resolved_tokens.append(token)
        else:
            resolved_tokens.append(token)

    if not changed:
        return text
    return shlex.join(resolved_tokens)


# ---------------------------------------------------------------------------
# Step 6: Here-string extraction
# ---------------------------------------------------------------------------

# Matches <<<'content', <<<"content", or <<<content (unquoted word)
_HERE_STRING_RE = re.compile(
    r'<<<\s*(?:'
    r"'([^']*)'"            # single-quoted
    r'|"([^"]*)"'          # double-quoted
    r'|(\S+)'              # unquoted word
    r')'
)


def _extract_here_strings(text: str) -> list[str]:
    """Extract here-string bodies from command text.

    Returns the content of each <<< found. The canonical text retains
    the <<< structure so bash can execute it correctly.
    """
    if "<<<" not in text:
        return []

    bodies = []
    for m in _HERE_STRING_RE.finditer(text):
        # One of the three groups will have matched
        body = m.group(1) or m.group(2) or m.group(3)
        if body:
            bodies.append(body)
    return bodies
