"""Inspect evaluation tasks for SecBASH security classifier.

Defines tasks for evaluating LLM classification of dangerous (GTFOBins)
and harmless commands using Inspect's Task/Dataset/Solver/Scorer architecture.

Both tasks are configured with GenerateConfig(max_retries=3, seed=42) by default:
- max_retries=3: API-level retries for transient failures (timeouts, rate limits)
- seed=42: Reproducible results across identical runs (for providers that support it:
  OpenAI, Google, Mistral, Groq, HuggingFace, vLLM; Anthropic does NOT support seed)

Usage:
    # Run GTFOBins evaluation
    inspect eval benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-4o-mini

    # Run harmless evaluation
    inspect eval benchmark/tasks/secbash_eval.py@secbash_harmless --model openai/gpt-4o-mini

    # Run with Chain-of-Thought
    inspect eval benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-4o-mini -T cot=true
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import (
    chain_of_thought,
    generate,
    system_message,
)

from secbash.llm_client import SYSTEM_PROMPT
from benchmark.scorers import security_classification_scorer

# Data directory relative to this file
DATA_DIR = Path(__file__).parent.parent / "data"


def load_secbash_dataset(
    path: str | Path, record_to_sample: Callable[[dict], Sample]
) -> MemoryDataset:
    """Load a SecBASH dataset from JSON and convert to Inspect MemoryDataset.

    The JSON files have a nested structure with a top-level 'commands' array
    that doesn't match Inspect's expected flat format, so we extract and
    convert manually.

    Args:
        path: Path to the JSON dataset file.
        record_to_sample: Function to convert a record dict to an Inspect Sample.

    Returns:
        MemoryDataset containing all converted samples.
    """
    with open(path) as f:
        data = json.load(f)
    samples = [record_to_sample(record) for record in data["commands"]]
    return MemoryDataset(samples=samples)


def gtfobins_record_to_sample(record: dict) -> Sample:
    """Convert a GTFOBins record to an Inspect Sample.

    Args:
        record: Dict with keys: command, binary, category.

    Returns:
        Sample with input=command prefixed for validation,
        target=["BLOCK"], and metadata.
    """
    cmd_hash = hashlib.md5(record["command"].encode()).hexdigest()[:8]
    return Sample(
        input=f"Validate this command: {record['command']}",
        target=["BLOCK"],
        id=f"{record['binary']}_{record['category']}_{cmd_hash}",
        metadata={
            "binary": record["binary"],
            "category": record["category"],
            "dataset": "gtfobins",
        },
    )


def harmless_record_to_sample(record: dict) -> Sample:
    """Convert a harmless command record to an Inspect Sample.

    Args:
        record: Dict with keys: command, prompt, ground_truth.

    Returns:
        Sample with input=command prefixed for validation,
        target=["ALLOW"], and metadata.
    """
    return Sample(
        input=f"Validate this command: {record['command']}",
        target=["ALLOW"],
        metadata={
            "prompt": record.get("prompt", ""),
            "dataset": "harmless",
        },
    )


@task
def secbash_gtfobins(cot: bool = False) -> Task:
    """Evaluate security classification of GTFOBins (malicious) commands.

    All commands should be classified as BLOCK.
    Configured with max_retries=3 and seed=42 for resilience and reproducibility.

    Args:
        cot: Enable Chain-of-Thought reasoning (adds "Think step by step"
             instruction before classification). Use -T cot=true on CLI.

    Returns:
        Inspect Task configured for GTFOBins evaluation.
    """
    solvers = [system_message(SYSTEM_PROMPT)]
    if cot:
        solvers.append(chain_of_thought())
    solvers.append(generate())

    return Task(
        dataset=load_secbash_dataset(
            DATA_DIR / "gtfobins_commands.json", gtfobins_record_to_sample
        ),
        solver=solvers,
        scorer=security_classification_scorer(),
        config=GenerateConfig(max_retries=3, seed=42),
    )


@task
def secbash_harmless(cot: bool = False) -> Task:
    """Evaluate security classification of harmless commands.

    All commands should be classified as ALLOW.
    Configured with max_retries=3 and seed=42 for resilience and reproducibility.

    Args:
        cot: Enable Chain-of-Thought reasoning (adds "Think step by step"
             instruction before classification). Use -T cot=true on CLI.

    Returns:
        Inspect Task configured for harmless command evaluation.
    """
    solvers = [system_message(SYSTEM_PROMPT)]
    if cot:
        solvers.append(chain_of_thought())
    solvers.append(generate())

    return Task(
        dataset=load_secbash_dataset(
            DATA_DIR / "harmless_commands.json", harmless_record_to_sample
        ),
        solver=solvers,
        scorer=security_classification_scorer(),
        config=GenerateConfig(max_retries=3, seed=42),
    )
