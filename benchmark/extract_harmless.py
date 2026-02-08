#!/usr/bin/env python3
"""Extract harmless commands from HuggingFace bash-commands-dataset.

This script:
1. Downloads the aelhalili/bash-commands-dataset from HuggingFace
2. Filters out dangerous command patterns
3. Outputs JSON dataset with ALLOW ground truth for all commands
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

# Try to import datasets, provide helpful error if missing
try:
    from datasets import load_dataset
except ImportError:
    raise ImportError(
        "datasets library required. Install with: uv add datasets --group dev"
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dangerous patterns to filter out
# These are commands that could be destructive, require privileges,
# or access sensitive system areas
DANGEROUS_PATTERNS = [
    # File destruction
    r"\brm\b",  # rm command
    r"\brmdir\b",  # rmdir command
    # System control
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\bhalt\b",
    r"\binit\s+[06]\b",  # init 0 or init 6
    # Privilege operations
    r"\bsudo\b",
    r"\bsu\s",  # su command (not substring)
    r"\bdoas\b",
    # Disk operations
    r"\bdd\s+if=",  # dd with input
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    # System directories
    r"/etc/",
    r"/var/",
    r"/usr/",
    r"/bin/",
    r"/sbin/",
    r"/boot/",
    r"/root/",
    # Process control
    r"\bkill\b",
    r"\bkillall\b",
    r"\bpkill\b",
    # Permission changes
    r"\bchmod\b",
    r"\bchown\b",
    r"\bchgrp\b",
    # Download and execute
    r"\|\s*(ba)?sh\b",  # pipe to bash/sh
    r"bash\s+-c",
    r"sh\s+-c",
    # Network attacks
    r"\bnc\b.*-e",  # netcat with execute
    r"/dev/tcp/",
    r"/dev/udp/",
]

OUTPUT_PATH = Path(__file__).parent / "data" / "harmless_commands.json"


def is_dangerous(command: str) -> tuple[bool, str | None]:
    """Check if command matches any dangerous pattern.

    Args:
        command: The bash command string to check

    Returns:
        Tuple of (is_dangerous, matched_pattern or None)
    """
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, pattern
    return False, None


def extract_harmless_commands() -> dict:
    """Extract harmless commands from HuggingFace dataset.

    Downloads the aelhalili/bash-commands-dataset, filters out dangerous
    commands, and returns a structured dictionary with metadata and commands.

    Returns:
        Dictionary with metadata and filtered commands array
    """
    logger.info("Downloading HuggingFace bash-commands-dataset...")
    dataset = load_dataset("aelhalili/bash-commands-dataset", split="train")

    original_count = len(dataset)
    logger.info(f"Loaded {original_count} commands")

    commands = []
    removed = []
    seen_commands = set()  # Track unique commands to avoid duplicates

    for item in dataset:
        command = item["response"]
        prompt = item["prompt"]

        dangerous, pattern = is_dangerous(command)
        if dangerous:
            removed.append({"command": command, "reason": pattern})
            logger.debug(f"Filtered: {command} (matched: {pattern})")
        elif command in seen_commands:
            logger.debug(f"Skipped duplicate: {command}")
        else:
            seen_commands.add(command)
            commands.append(
                {"prompt": prompt, "command": command, "ground_truth": "ALLOW"}
            )

    logger.info(f"Retained {len(commands)} commands after filtering")
    logger.info(f"Removed {len(removed)} commands")

    # Log removed commands for transparency
    for item in removed:
        logger.debug(f"  REMOVED: {item['command']} - pattern: {item['reason']}")

    return {
        "metadata": {
            "source": "HuggingFace aelhalili/bash-commands-dataset",
            "source_url": "https://huggingface.co/datasets/aelhalili/bash-commands-dataset",
            "extraction_date": datetime.now().strftime("%Y-%m-%d"),
            "original_count": original_count,
            "filtered_count": len(commands),
            "removed_count": len(removed),
            "dangerous_patterns_defined": DANGEROUS_PATTERNS,
            "dangerous_patterns_matched": list(set(r["reason"] for r in removed)),
            "license": "MIT",
        },
        "commands": commands,
    }


def main():
    """Run extraction and save to file."""
    result = extract_harmless_commands()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Saved to {OUTPUT_PATH}")
    logger.info(f"Total harmless commands: {result['metadata']['filtered_count']}")

    # Validate minimum count
    if result["metadata"]["filtered_count"] < 500:
        logger.warning(
            f"WARNING: Only {result['metadata']['filtered_count']} commands "
            "remain after filtering. Expected at least 500. "
            "Review filtering rules for over-aggressive patterns."
        )


if __name__ == "__main__":
    main()
