# Story 5.5: Fix GTFOBins Dataset

Status: done

## Story

As a **developer**,
I want **the GTFOBins dataset to use realistic placeholder values and include the Shell category**,
so that **the benchmark tests whether models understand exploit techniques rather than pattern-matching on scary words, and covers the most critical threat category**.

## Acceptance Criteria

1. **AC1: Realistic placeholders** - `extract_gtfobins.py` PLACEHOLDERS and PLACEHOLDER_PATTERNS are updated so output paths use security-sensitive locations (e.g., `/etc/cron.d/update`, `/usr/lib/libutils.so`, `/etc/sudoers.d/custom`) instead of names containing "evil", "malware", or "backdoor".
2. **AC2: Banned-name validation** - `validate_output()` in `extract_gtfobins.py` rejects any command containing banned names ("evil", "backdoor", "malware", "payload", "exploit", "hack") with a clear error message.
3. **AC3: Shell category included** - `shell` is added to `INCLUDED_CATEGORIES` and removed from `EXCLUDED_CATEGORIES`. The dataset grows from ~432 to ~690 commands (after deduplication) with 8 categories instead of 7.
4. **AC4: No banned names in output** - `grep -ci "evil" benchmark/data/gtfobins_commands.json` returns 0. Same for "malware" and "backdoor".
5. **AC5: Commands syntactically valid** - Spot-check of 20 shell commands and 10 file-write commands confirms all commands read naturally, the exploit technique is apparent, and placeholder replacement produced valid syntax.
6. **AC6: Dataset regenerated** - Running `uv run python -m benchmark.extract_gtfobins` produces a clean, validated dataset file at `benchmark/data/gtfobins_commands.json`.

## Tasks / Subtasks

- [x] Task 1: Update PLACEHOLDERS dict in `extract_gtfobins.py` (AC: #1)
  - [x] 1.1: Replace `/tmp/evil` (output-file) with `/etc/cron.d/update`
  - [x] 1.2: Replace `/tmp/evil.so` (lib.so) with `/usr/lib/libutils.so`
  - [x] 1.3: Replace `/tmp/evil.sh` (command) with `/usr/local/bin/service-check`
  - [x] 1.4: Replace `/tmp/evil` (ouput-file typo) with `/etc/cron.d/update`
- [x] Task 2: Update PLACEHOLDER_PATTERNS in `extract_gtfobins.py` (AC: #1)
  - [x] 2.1: Replace `$TF` value from `/tmp/evil` to `/etc/sudoers.d/custom`
  - [x] 2.2: Replace `$URL` value from `http://10.0.0.1/malware` to `http://10.0.0.1/update.tar.gz`
- [x] Task 3: Add DATA placeholder replacement (AC: #1)
  - [x] 3.1: Add `"DATA": "c2VydmljZS1jb25maWc="` to PLACEHOLDERS dict (base64-encoded realistic payload)
- [x] Task 3b: Add additional placeholder entries discovered during shell category integration (AC: #1)
  - [x] 3b.1: Add `/path/to/CMakeLists.txt` → `/tmp/build/CMakeLists.txt`
  - [x] 3b.2: Add `/path/to/ld.so` → `/lib64/ld-linux-x86-64.so.2`
  - [x] 3b.3: Add `/path/to/socket` → `/tmp/socket`
  - [x] 3b.4: Add catch-all `/path/to/` → `/tmp/build/`
- [x] Task 4: Add banned-name validation to `validate_output()` (AC: #2)
  - [x] 4.1: Define BANNED_NAMES list: `["evil", "backdoor", "malware", "payload", "exploit", "hack"]`
  - [x] 4.2: Loop over all commands checking `cmd.get("command", "").lower()` for banned substrings
  - [x] 4.3: Append clear error with command index and offending name on match
- [x] Task 5: Add Shell category to extraction (AC: #3)
  - [x] 5.1: Add `"shell"` to `INCLUDED_CATEGORIES` set
  - [x] 5.2: Remove `"shell"` from `EXCLUDED_CATEGORIES` set
- [x] Task 6: Re-run extraction and validate (AC: #4, #5, #6)
  - [x] 6.1: Run `uv run python -m benchmark.extract_gtfobins`
  - [x] 6.2: Verify total command count is ~690 (±50 for dedup variance) — actual: 696
  - [x] 6.3: Verify `grep -ci "evil" benchmark/data/gtfobins_commands.json` returns 0
  - [x] 6.4: Verify `grep -ci "malware" benchmark/data/gtfobins_commands.json` returns 0
  - [x] 6.5: Verify `grep -ci "backdoor" benchmark/data/gtfobins_commands.json` returns 0
  - [x] 6.6: Spot-check 20 shell commands and 10 file-write commands for validity
  - [x] 6.7: Verify categories_included in metadata now lists 8 categories including "shell"
  - [x] 6.8: Verify `shell` no longer appears in `categories_excluded`

## Dev Notes

### Architecture & Code Patterns

- **File to modify:** `benchmark/extract_gtfobins.py` (single file, 392 lines)
- **File regenerated:** `benchmark/data/gtfobins_commands.json` (output, not manually edited)
- **Module invocation:** `uv run python -m benchmark.extract_gtfobins` (uses `__main__` pattern via `if __name__ == "__main__": main()` at line 390)
- **Code style:** PEP 8 snake_case, standard Python logging, type hints on function signatures
- **YAML parsing:** Uses `yaml.safe_load()` from PyYAML (already in dependencies)
- **No other files need modification** - this story is entirely contained to the extraction script and its output

### Current State of `extract_gtfobins.py`

The script has a clear structure:
1. **Constants at top** (lines 30-85): `INCLUDED_CATEGORIES`, `EXCLUDED_CATEGORIES`, `PLACEHOLDERS` dict, `PLACEHOLDER_PATTERNS` list
2. **`normalize_command()`** (line 88): Applies string replacements then regex patterns
3. **`parse_gtfobins_file()`** (line 107): Reads one YAML file, filters by category, normalizes commands
4. **`extract_gtfobins()`** (line 203): Clones repo, iterates files, deduplicates
5. **`validate_output()`** (line 272): Validates metadata, fields, categories, placeholders, duplicates
6. **`main()`** (line 349): Orchestrates extraction, validation, save, category breakdown

### Exact Values to Change

**PLACEHOLDERS dict** (lines 51-73) - replace these 4 entries:

| Line | Old Key → Old Value | New Value |
|------|---------------------|-----------|
| 58 | `/path/to/output-file` → `/tmp/evil` | `/etc/cron.d/update` |
| 60 | `/path/to/lib.so` → `/tmp/evil.so` | `/usr/lib/libutils.so` |
| 62 | `/path/to/ouput-file` → `/tmp/evil` | `/etc/cron.d/update` |
| 70 | `/path/to/command` → `/tmp/evil.sh` | `/usr/local/bin/service-check` |

**PLACEHOLDER_PATTERNS list** (lines 76-85) - replace these 2 entries:

| Line | Old Pattern → Old Value | New Value |
|------|-------------------------|-----------|
| 82 | `$TF` → `/tmp/evil` | `/etc/sudoers.d/custom` |
| 83 | `$URL` → `http://10.0.0.1/malware` | `http://10.0.0.1/update.tar.gz` |

**Add to PLACEHOLDERS dict:** `"DATA": "c2VydmljZS1jb25maWc="` (base64 string that decodes to "service-config")

**INCLUDED_CATEGORIES** (line 30): Add `"shell"`
**EXCLUDED_CATEGORIES** (line 41): Remove `"shell"`

### Banned-Name Validation Implementation

Add to `validate_output()` after the existing placeholder checks (around line 328):

```python
BANNED_NAMES = ["evil", "backdoor", "malware", "payload", "exploit", "hack"]
for i, cmd in enumerate(commands):
    cmd_lower = cmd.get("command", "").lower()
    for banned in BANNED_NAMES:
        if banned in cmd_lower:
            errors.append(
                f"Command {i} contains banned name '{banned}': "
                f"{cmd.get('command', '')[:80]}"
            )
```

### Why These Specific Replacement Values

| New Value | Rationale |
|-----------|-----------|
| `/etc/cron.d/update` | System prompt Rule 5 lists `/etc/cron.*` as BLOCK target. Location alone sufficient. |
| `/usr/lib/libutils.so` | System library directory enables library injection. Location alone sufficient. |
| `/usr/local/bin/service-check` | System PATH directory enables PATH hijacking. Location alone sufficient. |
| `/etc/sudoers.d/custom` | System prompt Rule 5 lists `/etc/sudoers` as BLOCK target. Location alone sufficient. |
| `http://10.0.0.1/update.tar.gz` | Realistic download URL. Download from private IP flaggable under Rule 11. |
| `c2VydmljZS1jb25maWc=` | Base64-encoded "service-config". Realistic (attackers encode payloads). Tests technique recognition. |

### Shell Category Inclusion Rationale

- Shell spawning is the **#1 threat** for SecBASH (system prompt says "most critical threat")
- Adds ~265 commands from the GTFOBins shell category (~128 from new binaries)
- All shell entries are detectable from command text (binary names like `bash`, `zsh`, `screen`, or shell references in arguments)
- In the LLM-agent context, there is NO legitimate reason for the agent to generate `bash` or `screen` as commands
- Expected final count after dedup: ~690 commands, ~386 binaries, 8 categories

### Critical Constraints

- **Do NOT modify any other benchmark files** (scorer, tasks, report, plots) - those are covered by Story 5.3, 5.4, 5.7
- **Do NOT change the scoring logic** - Story 5.3 handles WARN=ALLOW scoring changes
- **Do NOT modify `src/secbash/llm_client.py`** - Story 5.4 handles system prompt changes
- **Order of PLACEHOLDERS matters** - longer/more-specific patterns must come before shorter ones (existing pattern maintained)
- The script clones GTFOBins via `git clone --depth 1` to a temp directory each run, so no local GTFOBins checkout is needed
- Output file path is auto-resolved: `benchmark/data/gtfobins_commands.json`

### Expected Impact on Metrics

| Metric | Before | After (expected) |
|--------|--------|------------------|
| Total commands | 432 | ~690 |
| Total binaries | 262 | ~386 |
| Category count | 7 | 8 |
| Banned names | 137+ commands with "evil" | 0 |
| Detection rate | Current baseline | Will likely decrease (harder placeholders + new category) |

Detection rate decrease is **expected and desirable** - it means the benchmark is now actually testing technique understanding rather than keyword matching.

### Project Structure Notes

- All changes are in `benchmark/` directory (top-level, moved from `tests/benchmark/` in Story 5.2)
- No alignment conflicts with project structure
- No impact on `src/secbash/` production code
- No impact on `tests/` pytest tests (extraction tests in `tests/test_benchmark_extract_gtfobins.py` may need updating if they assert exact command count or content, but that's test maintenance not story scope)

### References

- [Source: docs/analysis/fix-gtfobins-placeholders.md] - Full placeholder replacement plan with rationale
- [Source: docs/analysis/shell-category-recommendation.md] - Shell category inclusion analysis with data summary
- [Source: docs/analysis/benchmark-improvements.md] - Overall benchmark improvement plan (sections relevant: Part 2 context)
- [Source: docs/epics.md#Story 5.5] - Epic-level acceptance criteria and FR coverage (FR27, FR28, FR29)
- [Source: docs/architecture.md#Project Structure] - Confirms `benchmark/` is top-level directory
- [Source: benchmark/extract_gtfobins.py] - Current implementation to modify

## Dev Agent Record

### Context Reference

<!-- Story created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created
- All 4 PLACEHOLDERS entries updated: `/tmp/evil` → `/etc/cron.d/update`, `/tmp/evil.so` → `/usr/lib/libutils.so`, `/tmp/evil.sh` → `/usr/local/bin/service-check`, `/tmp/evil` (typo key) → `/etc/cron.d/update`
- Both PLACEHOLDER_PATTERNS updated: `$TF` → `/etc/sudoers.d/custom`, `$URL` → `http://10.0.0.1/update.tar.gz`
- Added `DATA` placeholder with base64 value `c2VydmljZS1jb25maWc=`
- Added 3 additional placeholder entries discovered during shell category integration: `/path/to/CMakeLists.txt`, `/path/to/ld.so`, `/path/to/socket`, and catch-all `/path/to/` → `/tmp/build/`
- Banned-name validation added to `validate_output()` checking 6 banned terms case-insensitively
- Shell category moved from EXCLUDED to INCLUDED — dataset grew from ~432 to 696 commands across 8 categories (264 shell commands)
- Zero occurrences of "evil", "malware", or "backdoor" in output dataset
- Updated existing tests to reflect new placeholder values and shell category inclusion
- Added 5 new tests: `test_normalize_data_placeholder`, `test_parse_includes_shell_category`, `test_banned_name_fails`, `test_banned_name_case_insensitive`, `test_no_banned_names_passes`
- Full test suite: 533 passed, 2 pre-existing failures in harmless dataset tests (Story 5.6 scope)

### File List

- `benchmark/extract_gtfobins.py` (modified) — Updated PLACEHOLDERS, PLACEHOLDER_PATTERNS, INCLUDED/EXCLUDED_CATEGORIES, added banned-name validation
- `benchmark/data/gtfobins_commands.json` (regenerated) — 696 commands, 397 binaries, 8 categories
- `tests/test_benchmark_extract_gtfobins.py` (modified) — Updated existing tests for new values, added new tests for DATA placeholder, shell inclusion, banned-name validation

## Senior Developer Review (AI)

**Reviewer:** guido | **Date:** 2026-02-08 | **Outcome:** Approved

**Issues Found:** 1 High, 4 Medium, 2 Low — all ignored per user decision (none affect current dataset)

**Latent issues noted (not blocking):**
- H1: Greedy `DATA` str.replace could corrupt future commands containing DATADIR/DATABASE (0 current hits)
- M1: `$URL` regex could match `$URL_PATH` partial variables (0 current hits)
- M2: `banned_names` defined as local var instead of module-level constant (style)
- M3: No unit tests for 3 extra placeholder entries (CMakeLists.txt, ld.so, socket)
- M4: Banned-name validation only checks `command` field, not `binary` field

**Fixes applied:**
- L1: Fixed Completion Notes test count from "4 new tests" to "5 new tests"
- L2: Added Task 3b documenting the 4 additional placeholder entries added during implementation

**AC Validation:** All 6 ACs verified as implemented. Dataset: 696 commands, 397 binaries, 8 categories, 0 banned names. 40/40 tests pass.

## Change Log

- 2026-02-08: Code review completed — 2 doc fixes applied, story marked done. Latent code issues noted but not blocking (none affect current dataset).
- 2026-02-08: Implemented Story 5.5 — replaced all "evil"/"malware" placeholders with realistic security-sensitive paths, added banned-name validation, included shell category (264 commands), regenerated dataset (696 total commands, 8 categories). Updated and added tests (40/40 pass).
