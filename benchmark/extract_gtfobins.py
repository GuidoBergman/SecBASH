#!/usr/bin/env python3
"""Extract GTFOBins commands for SecBASH benchmark evaluation.

This script:
1. Clones GTFOBins repository (shallow)
2. Parses YAML files for each binary
3. Filters to monitor-only suitable categories
4. Normalizes placeholders with example values
5. Outputs JSON dataset for evaluation harness
"""

import json
import logging
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# GTFOBins repository URL
GTFOBINS_REPO = "https://github.com/GTFOBins/GTFOBins.github.io.git"

# Categories to include (monitor-only suitable)
INCLUDED_CATEGORIES = {
    "file-read",
    "file-write",
    "reverse-shell",
    "bind-shell",
    "upload",
    "download",
    "command",
    "shell",
}

# Categories to exclude (require system context)
EXCLUDED_CATEGORIES = {
    "suid",
    "sudo",
    "capabilities",
    "library-load",
}

# Placeholder replacements - normalize with realistic values
# Order matters: longer/more specific patterns first
PLACEHOLDERS = {
    # IP addresses
    "attacker.com": "10.0.0.1",
    # Ports (various formats)
    "12345": "4444",
    # File paths - specific patterns first
    "/path/to/input-file": "/etc/shadow",
    "/path/to/output-file": "/etc/cron.d/update",
    "/path/to/temp-file": "/tmp/tempfile",
    "/path/to/lib.so": "/usr/lib/libutils.so",
    "/path/to/file-input": "/etc/shadow",
    "/path/to/ouput-file": "/etc/cron.d/update",  # Note: typo in GTFOBins source
    "/path/to/output-dir/": "/tmp/outdir/",
    "/path/to/input-dir/": "/etc/",
    "/path/to/empty-dir": "/tmp/empty",
    "/path/to/temp-dir/": "/tmp/tempdir/",
    "/path/to/temp-socket": "/tmp/socket",
    "/path/to/wordlist": "/usr/share/wordlists/rockyou.txt",
    "/path/to/hash": "/tmp/hash.txt",
    "/path/to/command": "/usr/local/bin/service-check",
    "/path/to/CMakeLists.txt": "/tmp/build/CMakeLists.txt",
    "/path/to/ld.so": "/lib64/ld-linux-x86-64.so.2",
    "/path/to/socket": "/tmp/socket",
    "/path/to/dir/": "/tmp/dir/",
    "/path/to/OUTPUT": "/tmp/output",
    "/path/to/": "/tmp/build/",
    "DATA": "c2VydmljZS1jb25maWc=",
}

# Regex-based placeholder replacements for variable patterns
PLACEHOLDER_PATTERNS = [
    # Shell variable patterns: $VAR, ${VAR}
    (r"\$\{?LHOST\}?", "10.0.0.1"),
    (r"\$\{?RHOST\}?", "10.0.0.1"),
    (r"\$\{?LPORT\}?", "4444"),
    (r"\$\{?RPORT\}?", "4444"),
    (r"\$\{?TF\}?", "/etc/sudoers.d/custom"),
    (r"\$\{?URL\}?", "http://10.0.0.1/update.tar.gz"),
    (r"\$\{?LFILE\}?", "/etc/shadow"),
]


def normalize_command(cmd: str) -> str:
    """Replace placeholders with realistic values for evaluation."""
    result = cmd

    # Apply string replacements
    for placeholder, value in PLACEHOLDERS.items():
        result = result.replace(placeholder, value)

    # Apply regex pattern replacements
    for pattern, value in PLACEHOLDER_PATTERNS:
        result = re.sub(pattern, value, result)

    # Clean up whitespace while preserving multiline structure
    lines = [line.rstrip() for line in result.split("\n")]
    result = "\n".join(lines).strip()

    return result


def parse_gtfobins_file(file_path: Path) -> list[dict]:
    """Parse a single GTFOBins YAML file and extract relevant commands.

    Args:
        file_path: Path to the GTFOBins YAML file

    Returns:
        List of command dictionaries with binary, category, and command
    """
    commands = []
    binary_name = file_path.name  # Filename is the binary name

    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        if data is None:
            return commands

        # Skip alias files (they just reference another binary)
        if "alias" in data and "functions" not in data:
            logger.debug(f"Skipping alias file: {binary_name}")
            return commands

        functions = data.get("functions", {})

        for category, entries in functions.items():
            # Skip excluded categories
            if category in EXCLUDED_CATEGORIES:
                continue

            # Skip non-included categories
            if category not in INCLUDED_CATEGORIES:
                continue

            # Skip inherit entries (they reference other binaries)
            if category == "inherit":
                continue

            if entries is None:
                continue

            for entry in entries:
                if entry is None:
                    continue

                # Get the code field
                code = entry.get("code")
                if not code:
                    continue

                # Normalize the command
                normalized_cmd = normalize_command(code)

                # Skip empty commands after normalization
                if not normalized_cmd:
                    continue

                commands.append(
                    {
                        "command": normalized_cmd,
                        "binary": binary_name,
                        "category": category,
                    }
                )

    except yaml.YAMLError as e:
        logger.warning(f"YAML parse error in {binary_name}: {e}")
    except Exception as e:
        logger.warning(f"Error parsing {binary_name}: {e}")

    return commands


def clone_gtfobins(target_dir: Path) -> Path:
    """Clone GTFOBins repository to target directory (shallow clone).

    Args:
        target_dir: Directory to clone into

    Returns:
        Path to the cloned repository
    """
    logger.info("Cloning GTFOBins repository (shallow clone)...")
    repo_dir = target_dir / "GTFOBins.github.io"

    subprocess.run(
        ["git", "clone", "--depth", "1", GTFOBINS_REPO, str(repo_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    return repo_dir


def extract_gtfobins() -> dict:
    """Main extraction logic.

    Returns:
        Dictionary containing metadata and commands list
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Clone the repository
        repo_dir = clone_gtfobins(temp_path)

        # Find _gtfobins directory
        gtfobins_dir = repo_dir / "_gtfobins"
        if not gtfobins_dir.exists():
            raise FileNotFoundError(f"_gtfobins directory not found in {repo_dir}")

        logger.info(f"Processing files from {gtfobins_dir}")

        # Process all YAML files
        all_commands = []
        binary_count = 0

        for file_path in sorted(gtfobins_dir.iterdir()):
            if file_path.is_file():
                commands = parse_gtfobins_file(file_path)
                all_commands.extend(commands)
                if commands:
                    binary_count += 1
                    logger.debug(
                        f"Extracted {len(commands)} commands from {file_path.name}"
                    )

        logger.info(
            f"Extracted {len(all_commands)} commands from {binary_count} binaries"
        )

        # Deduplicate commands (keep first occurrence, preserve order)
        seen_commands = set()
        unique_commands = []
        for cmd in all_commands:
            cmd_text = cmd["command"]
            if cmd_text not in seen_commands:
                seen_commands.add(cmd_text)
                unique_commands.append(cmd)

        if len(unique_commands) < len(all_commands):
            logger.info(
                f"Removed {len(all_commands) - len(unique_commands)} duplicate commands"
            )
        all_commands = unique_commands

        # Build output structure
        output = {
            "metadata": {
                "source": "GTFOBins",
                "repository": "https://github.com/GTFOBins/GTFOBins.github.io",
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "categories_included": sorted(list(INCLUDED_CATEGORIES)),
                "categories_excluded": sorted(list(EXCLUDED_CATEGORIES)),
                "total_commands": len(all_commands),
                "total_binaries": binary_count,
            },
            "commands": all_commands,
        }

        return output


def validate_output(data: dict) -> bool:
    """Validate the extracted data meets requirements.

    Args:
        data: The extracted data dictionary

    Returns:
        True if validation passes, False otherwise
    """
    errors = []

    # Check metadata exists
    if "metadata" not in data:
        errors.append("Missing metadata section")
    else:
        metadata = data["metadata"]
        required_fields = [
            "source",
            "extraction_date",
            "categories_included",
            "categories_excluded",
            "total_commands",
        ]
        for field in required_fields:
            if field not in metadata:
                errors.append(f"Missing metadata field: {field}")

    # Check commands exist and have required fields
    if "commands" not in data:
        errors.append("Missing commands array")
    else:
        commands = data["commands"]
        if not commands:
            errors.append("No commands extracted")

        for i, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                errors.append(f"Command {i} is not a dictionary")
                continue

            for field in ["command", "binary", "category"]:
                if field not in cmd:
                    errors.append(f"Command {i} missing field: {field}")

            # Verify category is in included list
            if cmd.get("category") in EXCLUDED_CATEGORIES:
                errors.append(
                    f"Command {i} has excluded category: {cmd.get('category')}"
                )

            # Check for un-normalized placeholders
            command_text = cmd.get("command", "")
            if "$LHOST" in command_text or "$RHOST" in command_text:
                errors.append(f"Command {i} has un-normalized placeholder: {cmd}")
            if "$TF" in command_text:
                errors.append(f"Command {i} has un-normalized $TF placeholder")

        # Check for banned names in commands
        banned_names = ["evil", "backdoor", "malware", "payload", "exploit", "hack"]
        for i, cmd in enumerate(commands):
            cmd_lower = cmd.get("command", "").lower()
            for banned in banned_names:
                if banned in cmd_lower:
                    errors.append(
                        f"Command {i} contains banned name '{banned}': "
                        f"{cmd.get('command', '')[:80]}"
                    )

        # Check for duplicate commands
        command_texts = [cmd.get("command", "") for cmd in commands]
        if len(command_texts) != len(set(command_texts)):
            duplicate_count = len(command_texts) - len(set(command_texts))
            errors.append(f"Found {duplicate_count} duplicate command(s)")

        # Verify count matches (only if metadata exists)
        if "metadata" in data:
            if len(commands) != data["metadata"].get("total_commands"):
                errors.append("Command count does not match metadata")

    if errors:
        for error in errors:
            logger.error(f"Validation error: {error}")
        return False

    logger.info("Validation passed")
    return True


def main() -> dict:
    """Main entry point for the extraction script."""
    # Determine output path
    script_dir = Path(__file__).parent
    output_file = script_dir / "data" / "gtfobins_commands.json"

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Starting GTFOBins extraction...")

    # Extract commands
    data = extract_gtfobins()

    # Validate
    if not validate_output(data):
        logger.error("Validation failed - output may be incomplete or incorrect")
        # Still save for inspection
    else:
        logger.info("Extraction and validation successful")

    # Save to file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Output saved to: {output_file}")
    logger.info(f"Total commands: {data['metadata']['total_commands']}")

    # Print category breakdown
    category_counts = {}
    for cmd in data["commands"]:
        cat = cmd["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    logger.info("Commands by category:")
    for cat, count in sorted(category_counts.items()):
        logger.info(f"  {cat}: {count}")

    return data


if __name__ == "__main__":
    main()
