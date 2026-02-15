"""Tests for the aegish LLM comparison framework.

Tests cover:
- Model list parsing (comma-separated string to list)
- Results aggregation with mock eval logs
- Ranking calculation with known scores
- JSON output format matches expected schema
- CoT vs standard scaffolding flags
- Partial run detection (existing results check)
- Comparison table formatting
- Dataset selection (gtfobins-only, harmless-only, both)
"""

import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from inspect_ai.scorer import CORRECT, Score

from benchmark.compare import (
    DEFAULT_MODELS,
    _build_tasks,
    _detect_log_dataset,
    _process_logs,
    calculate_composite,
    check_existing_results,
    extract_metrics_from_log,
    find_models_with_timeouts,
    generate_ranking,
    parse_models,
    print_comparison_table,
)


# --- Model list parsing tests (Task 8.1) ---


class TestParseModels:
    """Tests for parse_models() CLI argument parsing."""

    def test_none_returns_all_defaults(self):
        result = parse_models(None)
        assert result == DEFAULT_MODELS
        assert len(result) == 11

    def test_single_model(self):
        result = parse_models("openai/gpt-5.1")
        assert result == ["openai/gpt-5.1"]

    def test_comma_separated(self):
        result = parse_models("openai/gpt-5.1,openai/gpt-5-mini")
        assert result == ["openai/gpt-5.1", "openai/gpt-5-mini"]

    def test_whitespace_trimmed(self):
        result = parse_models("openai/gpt-5.1 , openai/gpt-5-mini ")
        assert result == ["openai/gpt-5.1", "openai/gpt-5-mini"]

    def test_empty_entries_filtered(self):
        result = parse_models("openai/gpt-5.1,,openai/gpt-5-mini,")
        assert result == ["openai/gpt-5.1", "openai/gpt-5-mini"]

    def test_empty_string(self):
        result = parse_models("")
        assert result == []


# --- Results aggregation tests (Task 8.2) ---


def _make_mock_eval_log(
    model: str = "openai/gpt-5.1",
    task_name: str = "aegish_gtfobins",
    malicious_detection_rate: float = 0.97,
    harmless_acceptance_rate_val: float = 0.0,
    accuracy: float = 0.97,
) -> MagicMock:
    """Create a mock EvalLog for testing."""
    log = MagicMock()
    log.eval = MagicMock()
    log.eval.model = model
    log.eval.task = task_name
    log.status = "success"

    sample1 = MagicMock()
    sample1.total_time = 0.847
    sample1.scores = {
        "scorer": Score(
            value=CORRECT,
            answer="BLOCK",
            metadata={"expected": "BLOCK", "actual": "BLOCK"},
        )
    }
    sample2 = MagicMock()
    sample2.total_time = 1.234
    sample2.scores = {
        "scorer": Score(
            value=CORRECT,
            answer="WARN",
            metadata={"expected": "BLOCK", "actual": "WARN"},
        )
    }
    log.samples = [sample1, sample2]

    log.stats = MagicMock()
    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 500
    log.stats.model_usage = {model: usage}

    log.results = MagicMock()
    score_log = MagicMock()
    # stderr for binomial proportion: sqrt(p*(1-p)/n) where n=2 samples
    stderr_val = (accuracy * (1 - accuracy) / 2) ** 0.5 if accuracy > 0 else 0.0
    score_log.metrics = {
        "accuracy": MagicMock(value=accuracy),
        "stderr": MagicMock(value=stderr_val),
        "malicious_detection_rate": MagicMock(value=malicious_detection_rate),
        "harmless_acceptance_rate": MagicMock(value=harmless_acceptance_rate_val),
        "aegish_score": MagicMock(value=(malicious_detection_rate + harmless_acceptance_rate_val) / 2),
    }
    log.results.scores = [score_log]

    return log


class TestExtractMetricsFromLog:
    """Tests for extract_metrics_from_log()."""

    def test_extracts_malicious_detection_rate(self):
        log = _make_mock_eval_log(malicious_detection_rate=0.97)
        metrics = extract_metrics_from_log(log)
        assert metrics["malicious_detection_rate"] == 0.97

    def test_extracts_latency(self):
        log = _make_mock_eval_log()
        metrics = extract_metrics_from_log(log)
        assert metrics["latency"]["mean"] > 0
        assert metrics["latency"]["max"] >= metrics["latency"]["mean"]

    def test_extracts_cost(self):
        log = _make_mock_eval_log()
        metrics = extract_metrics_from_log(log)
        assert metrics["cost"]["total_cost"] >= 0

    def test_extracts_correct_count(self):
        log = _make_mock_eval_log()
        metrics = extract_metrics_from_log(log)
        assert metrics["total_commands"] == 2
        assert metrics["correct"] == 2

    def test_extracts_stderr(self):
        log = _make_mock_eval_log(accuracy=0.97)
        metrics = extract_metrics_from_log(log)
        assert metrics["stderr"] is not None
        assert metrics["stderr"] > 0


# --- Ranking calculation tests (Task 8.3) ---


class TestGenerateRanking:
    """Tests for generate_ranking() with known scores."""

    def test_ranking_order(self):
        results = {
            "model-a": {
                "status": "success",
                "composite": {"aegish_score": 0.8, "cost_per_1000_combined": 3.0},
            },
            "model-b": {
                "status": "success",
                "composite": {"aegish_score": 0.95, "cost_per_1000_combined": 5.0},
            },
            "model-c": {
                "status": "success",
                "composite": {"aegish_score": 0.85, "cost_per_1000_combined": 2.0},
            },
        }
        ranking = generate_ranking(results)
        assert len(ranking) == 3
        assert ranking[0]["model"] == "model-b"
        assert ranking[0]["rank"] == 1
        assert ranking[1]["model"] == "model-c"
        assert ranking[2]["model"] == "model-a"

    def test_excludes_failed_models(self):
        results = {
            "model-a": {
                "status": "success",
                "composite": {"aegish_score": 0.9, "cost_per_1000_combined": 3.0},
            },
            "model-b": {
                "status": "error",
                "error": "API key missing",
            },
        }
        ranking = generate_ranking(results)
        assert len(ranking) == 1
        assert ranking[0]["model"] == "model-a"

    def test_empty_results(self):
        ranking = generate_ranking({})
        assert ranking == []

    def test_all_failed(self):
        results = {
            "model-a": {"status": "error"},
            "model-b": {"status": "error"},
        }
        ranking = generate_ranking(results)
        assert ranking == []

    def test_ranking_includes_cost(self):
        results = {
            "model-a": {
                "status": "success",
                "composite": {"aegish_score": 0.9, "cost_per_1000_combined": 3.16},
            },
        }
        ranking = generate_ranking(results)
        assert ranking[0]["cost_per_1000"] == 3.16


# --- JSON output format tests (Task 8.4) ---


class TestJsonOutputFormat:
    """Tests for comparison JSON output schema."""

    def test_comparison_schema(self):
        """Verify the comparison output matches expected schema."""
        comparison = {
            "metadata": {
                "timestamp": "2026-02-04T14:30:00Z",
                "models_evaluated": 2,
                "datasets": ["gtfobins", "harmless"],
                "scaffolding": "standard",
                "gtfobins_count": 431,
                "harmless_count": 310,
                "skipped_models": [],
            },
            "results": {
                "openai/gpt-5.1": {
                    "model": "openai/gpt-5.1",
                    "cot": False,
                    "status": "success",
                    "datasets": {
                        "gtfobins": {"malicious_detection_rate": 0.97},
                        "harmless": {"harmless_acceptance_rate": 0.92},
                    },
                    "composite": {
                        "aegish_score": 0.89,
                        "total_cost_usd": 2.34,
                        "cost_per_1000_combined": 3.16,
                        "avg_latency_ms": 800,
                    },
                }
            },
            "ranking": [
                {
                    "rank": 1,
                    "model": "openai/gpt-5.1",
                    "aegish_score": 0.89,
                    "cost_per_1000": 3.16,
                }
            ],
        }

        # Verify top-level keys
        assert "metadata" in comparison
        assert "results" in comparison
        assert "ranking" in comparison

        # Verify metadata
        meta = comparison["metadata"]
        assert "timestamp" in meta
        assert "models_evaluated" in meta
        assert "datasets" in meta
        assert "scaffolding" in meta

        # Verify result structure
        result = comparison["results"]["openai/gpt-5.1"]
        assert result["model"] == "openai/gpt-5.1"
        assert result["status"] == "success"
        assert "datasets" in result
        assert "composite" in result
        assert "aegish_score" in result["composite"]

        # Verify ranking structure
        rank = comparison["ranking"][0]
        assert "rank" in rank
        assert "model" in rank
        assert "aegish_score" in rank

    def test_json_serializable(self):
        """Ensure comparison results can be serialized to JSON."""
        comparison = {
            "metadata": {"timestamp": "2026-02-04T14:30:00Z", "models_evaluated": 1},
            "results": {
                "test/model": {
                    "status": "success",
                    "composite": {"aegish_score": 0.9},
                }
            },
            "ranking": [{"rank": 1, "model": "test/model", "aegish_score": 0.9}],
        }
        serialized = json.dumps(comparison)
        deserialized = json.loads(serialized)
        assert deserialized == comparison


# --- CoT scaffolding tests (Task 8.5) ---


class TestCoTScaffolding:
    """Tests for Chain-of-Thought scaffolding flag handling."""

    def test_standard_task_has_2_solvers(self):
        from benchmark.tasks.aegish_eval import aegish_gtfobins

        task = aegish_gtfobins(cot=False)
        assert len(task.solver) == 2  # system_message + generate

    def test_cot_task_has_3_solvers(self):
        from benchmark.tasks.aegish_eval import aegish_gtfobins

        task = aegish_gtfobins(cot=True)
        assert len(task.solver) == 3  # system_message + chain_of_thought + generate


# --- Partial run detection tests (Task 8.6) ---


class TestPartialRunDetection:
    """Tests for check_existing_results() resume support."""

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_existing_results(Path(tmpdir))
            assert result == {}

    def test_nonexistent_dir_returns_empty(self):
        result = check_existing_results(Path("/nonexistent/path"))
        assert result == {}

    def test_loads_existing_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            comparison = {
                "results": {
                    "openai/gpt-5.1": {
                        "status": "success",
                        "composite": {"aegish_score": 0.9},
                    },
                    "openai/gpt-5-mini": {
                        "status": "error",
                        "error": "API failure",
                    },
                }
            }
            filepath = Path(tmpdir) / "comparison_20260204_143000.json"
            with open(filepath, "w") as f:
                json.dump(comparison, f)

            result = check_existing_results(Path(tmpdir))
            # Only successful results are loaded
            assert "openai/gpt-5.1" in result
            assert "openai/gpt-5-mini" not in result

    def test_ignores_non_comparison_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "other_file.json"
            with open(filepath, "w") as f:
                json.dump({"data": "test"}, f)

            result = check_existing_results(Path(tmpdir))
            assert result == {}

    def test_handles_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "comparison_20260204_143000.json"
            with open(filepath, "w") as f:
                f.write("not valid json{{{")

            result = check_existing_results(Path(tmpdir))
            assert result == {}


# --- Comparison table formatting tests (Task 8.8) ---


class TestComparisonTableFormatting:
    """Tests for print_comparison_table() console output."""

    def test_table_output(self, capsys):
        results = {
            "openai/gpt-5.1": {
                "status": "success",
                "datasets": {
                    "gtfobins": {"malicious_detection_rate": 0.97},
                    "harmless": {"harmless_acceptance_rate": 0.92},
                },
                "composite": {
                    "aegish_score": 0.893,
                    "total_cost_usd": 2.34,
                    "cost_per_1000_combined": 3.16,
                    "avg_latency_ms": 800,
                },
            },
        }
        ranking = [
            {
                "rank": 1,
                "model": "openai/gpt-5.1",
                "aegish_score": 0.893,
                "cost_per_1000": 3.16,
            }
        ]

        print_comparison_table(results, ranking)
        captured = capsys.readouterr()

        assert "aegish LLM Comparison Results" in captured.out
        assert "openai/gpt-5.1" in captured.out
        assert "97.0%" in captured.out  # Detection rate
        assert "92.0%" in captured.out  # Pass rate
        assert "0.893" in captured.out  # Score
        assert "$2.34" in captured.out  # Cost

    def test_table_with_zero_cost_model(self, capsys):
        results = {
            "test/free-model": {
                "status": "success",
                "datasets": {
                    "gtfobins": {"malicious_detection_rate": 0.5},
                    "harmless": {"harmless_acceptance_rate": 0.5},
                },
                "composite": {
                    "aegish_score": 0.25,
                    "total_cost_usd": 0.0,
                    "cost_per_1000_combined": 0.0,
                    "avg_latency_ms": 500,
                },
            },
        }
        ranking = [
            {
                "rank": 1,
                "model": "test/free-model",
                "aegish_score": 0.25,
                "cost_per_1000": 0.0,
            }
        ]

        print_comparison_table(results, ranking)
        captured = capsys.readouterr()
        assert "$0.00" in captured.out

    def test_table_with_failed_models(self, capsys):
        results = {
            "model-ok": {
                "status": "success",
                "datasets": {
                    "gtfobins": {"malicious_detection_rate": 0.9},
                    "harmless": {"harmless_acceptance_rate": 0.9},
                },
                "composite": {
                    "aegish_score": 0.81,
                    "total_cost_usd": 1.0,
                    "cost_per_1000_combined": 2.0,
                    "avg_latency_ms": 600,
                },
            },
            "model-fail": {
                "status": "error",
                "error": "API key missing",
            },
        }
        ranking = [
            {
                "rank": 1,
                "model": "model-ok",
                "aegish_score": 0.81,
                "cost_per_1000": 2.0,
            }
        ]

        print_comparison_table(results, ranking)
        captured = capsys.readouterr()
        assert "Failed models" in captured.out
        assert "API key missing" in captured.out

    def test_table_highlights_passing_targets(self, capsys):
        results = {
            "model-a": {
                "status": "success",
                "datasets": {
                    "gtfobins": {"malicious_detection_rate": 0.96},
                    "harmless": {"harmless_acceptance_rate": 0.91},
                },
                "composite": {
                    "aegish_score": 0.874,
                    "total_cost_usd": 1.0,
                    "cost_per_1000_combined": 2.0,
                    "avg_latency_ms": 600,
                },
            },
        }
        ranking = [
            {
                "rank": 1,
                "model": "model-a",
                "aegish_score": 0.874,
                "cost_per_1000": 2.0,
            }
        ]

        print_comparison_table(results, ranking)
        captured = capsys.readouterr()
        assert "96.0%*" in captured.out  # Detection meets target (96% >= 95%)
        assert "91.0%" in captured.out  # Pass rate below target (91% < 95%)
        assert "91.0%*" not in captured.out  # Confirm no asterisk
        assert "0.874" in captured.out  # Score below target (0.874 < 0.95)
        assert "0.874*" not in captured.out  # Confirm no asterisk


# --- Dataset selection tests (Task 8.9) ---


class TestDatasetSelection:
    """Tests for dataset selection logic."""

    def test_default_models_list_has_10(self):
        assert len(DEFAULT_MODELS) == 11

    def test_hf_models_are_in_defaults(self):
        hf_models = [
            m for m in DEFAULT_MODELS if m.startswith("hf-inference-providers/")
        ]
        assert len(hf_models) >= 2


# --- Composite calculation tests ---


class TestCalculateComposite:
    """Tests for calculate_composite() scoring."""

    def test_both_datasets(self):
        gtfo = {
            "malicious_detection_rate": 0.95,
            "total_commands": 431,
            "cost": {"total_cost": 1.5},
            "latency": {"mean": 800},
        }
        harm = {
            "harmless_acceptance_rate": 0.90,
            "total_commands": 310,
            "cost": {"total_cost": 1.0},
            "latency": {"mean": 700},
        }
        result = calculate_composite(gtfo, harm)
        assert result["aegish_score"] == (0.95 + 0.90) / 2
        assert result["total_cost_usd"] == 2.5
        assert result["avg_latency_ms"] == 750.0

    def test_gtfobins_only(self):
        gtfo = {
            "malicious_detection_rate": 0.95,
            "total_commands": 431,
            "cost": {"total_cost": 1.5},
            "latency": {"mean": 800},
        }
        result = calculate_composite(gtfo, None)
        assert result["aegish_score"] == (0.95 + 0.0) / 2  # No harmless_acceptance_rate defaults to 0
        assert result["total_cost_usd"] == 1.5

    def test_harmless_only(self):
        harm = {
            "harmless_acceptance_rate": 0.90,
            "total_commands": 310,
            "cost": {"total_cost": 1.0},
            "latency": {"mean": 700},
        }
        result = calculate_composite(None, harm)
        assert (
            result["aegish_score"] == (0.0 + 0.90) / 2
        )  # No malicious_detection_rate defaults to 0
        assert result["total_cost_usd"] == 1.0

    def test_both_none(self):
        result = calculate_composite(None, None)
        assert result["aegish_score"] == 0.0
        assert result["total_cost_usd"] == 0.0
        assert result["avg_latency_ms"] == 0.0

    def test_cost_per_1000_calculation(self):
        gtfo = {
            "malicious_detection_rate": 0.95,
            "total_commands": 100,
            "cost": {"total_cost": 1.0},
            "latency": {"mean": 800},
        }
        harm = {
            "harmless_acceptance_rate": 0.90,
            "total_commands": 100,
            "cost": {"total_cost": 1.0},
            "latency": {"mean": 700},
        }
        result = calculate_composite(gtfo, harm)
        # total_cost = 2.0, total_commands = 200
        # cost_per_1000 = 2.0 / 200 * 1000 = 10.0
        assert result["cost_per_1000_combined"] == 10.0

    def test_composite_se_propagated(self):
        gtfo = {
            "malicious_detection_rate": 0.95,
            "stderr": 0.01,
            "total_commands": 431,
            "cost": {"total_cost": 1.5},
            "latency": {"mean": 800},
        }
        harm = {
            "harmless_acceptance_rate": 0.90,
            "stderr": 0.02,
            "total_commands": 310,
            "cost": {"total_cost": 1.0},
            "latency": {"mean": 700},
        }
        result = calculate_composite(gtfo, harm)
        assert result["aegish_score_se"] is not None
        # SE((DR + PR) / 2) = sqrt(SE_dr^2 + SE_pr^2) / 2
        expected_se = ((0.01**2 + 0.02**2) ** 0.5) / 2
        assert abs(result["aegish_score_se"] - expected_se) < 1e-10

    def test_composite_se_none_when_missing(self):
        gtfo = {
            "malicious_detection_rate": 0.95,
            "total_commands": 431,
            "cost": {"total_cost": 1.5},
            "latency": {"mean": 800},
        }
        harm = {
            "harmless_acceptance_rate": 0.90,
            "total_commands": 310,
            "cost": {"total_cost": 1.0},
            "latency": {"mean": 700},
        }
        result = calculate_composite(gtfo, harm)
        assert result["aegish_score_se"] is None


# --- Batch helpers tests ---


class TestBuildTasks:
    """Tests for _build_tasks() helper."""

    def test_both_standard(self):
        tasks = _build_tasks("both", cot=False)
        assert len(tasks) == 2

    def test_gtfobins_only(self):
        tasks = _build_tasks("gtfobins", cot=False)
        assert len(tasks) == 1

    def test_harmless_only(self):
        tasks = _build_tasks("harmless", cot=False)
        assert len(tasks) == 1

    def test_cot_adds_solver(self):
        tasks_no_cot = _build_tasks("gtfobins", cot=False)
        tasks_cot = _build_tasks("gtfobins", cot=True)
        assert len(tasks_cot[0].solver) == len(tasks_no_cot[0].solver) + 1


class TestDetectLogDataset:
    """Tests for _detect_log_dataset() helper."""

    def test_gtfobins(self):
        log = MagicMock()
        log.eval.task = "aegish_gtfobins"
        assert _detect_log_dataset(log) == "gtfobins"

    def test_harmless(self):
        log = MagicMock()
        log.eval.task = "aegish_harmless"
        assert _detect_log_dataset(log) == "harmless"

    def test_unknown(self):
        log = MagicMock()
        log.eval.task = "something_else"
        assert _detect_log_dataset(log) == "unknown"


class TestProcessLogs:
    """Tests for _process_logs() populating results dict."""

    def test_success_populates_results(self):
        log = _make_mock_eval_log(model="openai/gpt-5.1", task_name="aegish_gtfobins")
        log.status = "success"
        results: dict = {}
        _process_logs(
            [log], ["openai/gpt-5.1"], cot=False, dataset="gtfobins", results=results
        )
        assert "openai/gpt-5.1" in results
        assert results["openai/gpt-5.1"]["datasets"]["gtfobins"] is not None
        assert "composite" in results["openai/gpt-5.1"]

    def test_missing_model_marked_error(self):
        results: dict = {}
        _process_logs(
            [], ["openai/gpt-5.1"], cot=False, dataset="both", results=results
        )
        assert results["openai/gpt-5.1"]["status"] == "error"

    def test_partial_when_one_dataset_missing(self):
        log = _make_mock_eval_log(model="openai/gpt-5.1", task_name="aegish_gtfobins")
        log.status = "success"
        results: dict = {}
        _process_logs(
            [log], ["openai/gpt-5.1"], cot=False, dataset="both", results=results
        )
        assert results["openai/gpt-5.1"]["status"] == "partial"
        assert results["openai/gpt-5.1"]["datasets"]["harmless"] is None


# --- find_models_with_timeouts tests ---


def _create_eval_zip(
    path: Path,
    model: str,
    task: str,
    samples: list[dict],
) -> None:
    """Helper to create a minimal .eval zip for testing."""
    start_json = json.dumps({"eval": {"model": model, "task": task}})
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("_journal/start.json", start_json)
        for i, sample in enumerate(samples):
            zf.writestr(f"samples/sample_{i}_epoch_1.json", json.dumps(sample))


class TestFindModelsWithTimeouts:
    """Tests for find_models_with_timeouts() log scanning."""

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_models_with_timeouts(Path(tmpdir))
            assert result == {}

    def test_nonexistent_dir(self):
        result = find_models_with_timeouts(Path("/nonexistent/path"))
        assert result == {}

    def test_no_timeouts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_eval_zip(
                Path(tmpdir) / "2026-02-05T14-56-35+00-00_aegish-gtfobins_abc123.eval",
                model="openai/gpt-5.1",
                task="aegish_gtfobins",
                samples=[{"id": "s1", "scores": {}}],
            )
            result = find_models_with_timeouts(Path(tmpdir))
            assert result == {}

    def test_detects_timeouts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_eval_zip(
                Path(tmpdir) / "2026-02-05T14-56-35+00-00_aegish-gtfobins_abc123.eval",
                model="google/gemini-3-pro-preview",
                task="aegish_gtfobins",
                samples=[
                    {"id": "s1", "limit": {"type": "time", "limit": 60.0}},
                    {"id": "s2", "scores": {}},
                    {"id": "s3", "limit": {"type": "time", "limit": 60.0}},
                ],
            )
            result = find_models_with_timeouts(Path(tmpdir))
            assert result == {"google/gemini-3-pro-preview": 2}

    def test_aggregates_across_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_eval_zip(
                Path(tmpdir) / "2026-02-05T14-56-35+00-00_aegish-gtfobins_abc.eval",
                model="anthropic/claude-opus-4-6",
                task="aegish_gtfobins",
                samples=[{"id": "s1", "limit": {"type": "time", "limit": 60.0}}],
            )
            _create_eval_zip(
                Path(tmpdir) / "2026-02-05T14-56-35+00-00_aegish-harmless_def.eval",
                model="anthropic/claude-opus-4-6",
                task="aegish_harmless",
                samples=[
                    {"id": "s1", "limit": {"type": "time", "limit": 60.0}},
                    {"id": "s2", "limit": {"type": "time", "limit": 60.0}},
                ],
            )
            result = find_models_with_timeouts(Path(tmpdir))
            assert result == {"anthropic/claude-opus-4-6": 3}

    def test_uses_most_recent_eval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Older eval with timeouts
            _create_eval_zip(
                Path(tmpdir) / "2026-02-04T10-00-00+00-00_aegish-gtfobins_old.eval",
                model="openai/gpt-5.1",
                task="aegish_gtfobins",
                samples=[{"id": "s1", "limit": {"type": "time", "limit": 60.0}}],
            )
            # Newer eval without timeouts
            _create_eval_zip(
                Path(tmpdir) / "2026-02-05T10-00-00+00-00_aegish-gtfobins_new.eval",
                model="openai/gpt-5.1",
                task="aegish_gtfobins",
                samples=[{"id": "s1", "scores": {}}],
            )
            result = find_models_with_timeouts(Path(tmpdir))
            assert result == {}

    def test_ignores_bad_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = (
                Path(tmpdir) / "2026-02-05T14-56-35+00-00_aegish-gtfobins_bad.eval"
            )
            bad_path.write_text("not a zip file")
            result = find_models_with_timeouts(Path(tmpdir))
            assert result == {}
