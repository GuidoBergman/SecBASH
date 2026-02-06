"""Inspect evaluation tasks for SecBASH security classifier.

Defines tasks for evaluating LLM classification of dangerous (GTFOBins)
and harmless commands using Inspect's Task/Dataset/Solver/Scorer architecture.

Usage:
    # Run GTFOBins evaluation
    inspect eval tests/benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-4o-mini

    # Run harmless evaluation
    inspect eval tests/benchmark/tasks/secbash_eval.py@secbash_harmless --model openai/gpt-4o-mini

    # Run with Chain-of-Thought
    inspect eval tests/benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-4o-mini -T cot=true
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.solver import (
    Generate,
    Solver,
    TaskState,
    chain_of_thought,
    generate,
    solver,
    system_message,
)

from secbash.llm_client import LLAMAGUARD_PROMPT, SYSTEM_PROMPT
from tests.benchmark.scorers import (
    llamaguard_classification_scorer,
    security_classification_scorer,
)

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
        target=["BLOCK", "WARN"], and metadata.
    """
    cmd_hash = hashlib.md5(record["command"].encode()).hexdigest()[:8]
    return Sample(
        input=f"Validate this command: {record['command']}",
        target=["BLOCK", "WARN"],
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

    All commands should be classified as BLOCK or WARN.

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
    )


@task
def secbash_harmless(cot: bool = False) -> Task:
    """Evaluate security classification of harmless commands.

    All commands should be classified as ALLOW.

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
    )


@solver
def llamaguard_formatter() -> Solver:
    """Reformat input for LlamaGuard's single-message prompt format.

    Extracts the command from the "Validate this command: <cmd>" input
    and replaces it with the LlamaGuard-specific prompt template.
    No system message is used for LlamaGuard models.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        cmd = state.user_prompt.text.replace("Validate this command: ", "")
        state.user_prompt.text = LLAMAGUARD_PROMPT.format(command=cmd)
        return state

    return solve


def _is_llamaguard_model(model: str) -> bool:
    """Check if a model string refers to a LlamaGuard model.

    Args:
        model: Model string in Inspect format.

    Returns:
        True if the model contains "llama-guard".
    """
    return "llama-guard" in model.lower()


@task
def secbash_gtfobins_llamaguard(cot: bool = False) -> Task:
    """Evaluate LlamaGuard classification of GTFOBins (malicious) commands.

    Uses LlamaGuard's single-message prompt format and safe/unsafe scorer.

    Args:
        cot: Enable Chain-of-Thought reasoning.

    Returns:
        Inspect Task configured for LlamaGuard GTFOBins evaluation.
    """
    solvers = []
    if cot:
        solvers.append(chain_of_thought())
    solvers.append(llamaguard_formatter())
    solvers.append(generate())

    return Task(
        dataset=load_secbash_dataset(
            DATA_DIR / "gtfobins_commands.json", gtfobins_record_to_sample
        ),
        solver=solvers,
        scorer=llamaguard_classification_scorer(),
    )


@task
def secbash_harmless_llamaguard(cot: bool = False) -> Task:
    """Evaluate LlamaGuard classification of harmless commands.

    Uses LlamaGuard's single-message prompt format and safe/unsafe scorer.

    Args:
        cot: Enable Chain-of-Thought reasoning.

    Returns:
        Inspect Task configured for LlamaGuard harmless command evaluation.
    """
    solvers = []
    if cot:
        solvers.append(chain_of_thought())
    solvers.append(llamaguard_formatter())
    solvers.append(generate())

    return Task(
        dataset=load_secbash_dataset(
            DATA_DIR / "harmless_commands.json", harmless_record_to_sample
        ),
        solver=solvers,
        scorer=llamaguard_classification_scorer(),
    )
