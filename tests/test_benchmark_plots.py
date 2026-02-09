"""Tests for benchmark visualization plots."""

import json
from pathlib import Path

import pytest

from benchmark.plots import (
    compute_pareto_frontier,
    generate_all_plots,
    get_provider,
    get_provider_color,
    get_short_name,
    load_comparison_results,
    plot_category_heatmap,
    plot_cost_comparison,
    plot_cost_vs_score,
    plot_detection_vs_pass,
    plot_latency_distribution,
    plot_micro_vs_macro,
    plot_ranking_table,
    save_plot,
)


@pytest.fixture()
def minimal_comparison_data() -> dict:
    """Minimal valid comparison JSON data with 3 models."""
    return {
        "metadata": {
            "timestamp": "2026-02-06T00:00:00Z",
            "models_evaluated": 3,
            "datasets": ["gtfobins", "harmless"],
            "scaffolding": "standard",
            "gtfobins_count": 431,
            "harmless_count": 310,
        },
        "results": {
            "openai/gpt-5.1": {
                "model": "openai/gpt-5.1",
                "cot": False,
                "status": "success",
                "datasets": {
                    "gtfobins": {
                        "detection_rate": 0.96,
                        "detection_rate_macro": 0.91,
                        "pass_rate": 0.0,
                        "false_positive_rate": 1.0,
                        "accuracy": 0.96,
                        "stderr": 0.01,
                        "total_commands": 431,
                        "correct": 414,
                        "per_category_detection_rates": {
                            "reverse-shell": {"count": 19, "detection_rate": 1.0},
                            "file-read": {"count": 200, "detection_rate": 0.97},
                            "shell": {"count": 150, "detection_rate": 0.95},
                            "command": {"count": 30, "detection_rate": 0.40},
                        },
                        "latency": {
                            "mean": 25000.0,
                            "p50": 22000.0,
                            "p90": 38000.0,
                            "p99": 55000.0,
                            "max": 60000.0,
                        },
                        "cost": {
                            "total_cost": 2.0,
                            "cost_per_1000": 4.64,
                            "cost_per_command": 0.00464,
                        },
                    },
                    "harmless": {
                        "detection_rate": 0.0,
                        "pass_rate": 0.92,
                        "false_positive_rate": 0.08,
                        "accuracy": 0.92,
                        "stderr": 0.015,
                        "total_commands": 310,
                        "correct": 285,
                        "latency": {
                            "mean": 20000.0,
                            "p50": 18000.0,
                            "p90": 32000.0,
                            "p99": 45000.0,
                            "max": 50000.0,
                        },
                        "cost": {
                            "total_cost": 1.5,
                            "cost_per_1000": 4.84,
                            "cost_per_command": 0.00484,
                        },
                    },
                },
                "composite": {
                    "aegish_score": 0.883,
                    "aegish_score_se": 0.015,
                    "total_cost_usd": 3.5,
                    "cost_per_1000_combined": 4.73,
                    "avg_latency_ms": 22500.0,
                },
            },
            "google/gemini-3-flash-preview": {
                "model": "google/gemini-3-flash-preview",
                "cot": False,
                "status": "success",
                "datasets": {
                    "gtfobins": {
                        "detection_rate": 0.89,
                        "detection_rate_macro": 0.85,
                        "pass_rate": 0.0,
                        "false_positive_rate": 1.0,
                        "accuracy": 0.89,
                        "stderr": 0.015,
                        "total_commands": 431,
                        "correct": 384,
                        "per_category_detection_rates": {
                            "reverse-shell": {"count": 19, "detection_rate": 0.95},
                            "file-read": {"count": 200, "detection_rate": 0.90},
                            "shell": {"count": 150, "detection_rate": 0.88},
                            "command": {"count": 30, "detection_rate": 0.50},
                        },
                        "latency": {
                            "mean": 15000.0,
                            "p50": 12000.0,
                            "p90": 25000.0,
                            "p99": 35000.0,
                            "max": 40000.0,
                        },
                        "cost": {
                            "total_cost": 0.0,
                            "cost_per_1000": 0.0,
                            "cost_per_command": 0.0,
                        },
                    },
                    "harmless": {
                        "detection_rate": 0.0,
                        "pass_rate": 0.95,
                        "false_positive_rate": 0.05,
                        "accuracy": 0.95,
                        "stderr": 0.012,
                        "total_commands": 310,
                        "correct": 295,
                        "latency": {
                            "mean": 12000.0,
                            "p50": 10000.0,
                            "p90": 20000.0,
                            "p99": 28000.0,
                            "max": 32000.0,
                        },
                        "cost": {
                            "total_cost": 0.0,
                            "cost_per_1000": 0.0,
                            "cost_per_command": 0.0,
                        },
                    },
                },
                "composite": {
                    "aegish_score": 0.846,
                    "aegish_score_se": 0.018,
                    "total_cost_usd": 0.0,
                    "cost_per_1000_combined": 0.0,
                    "avg_latency_ms": 13500.0,
                },
            },
            "anthropic/claude-sonnet-4-5-20250929": {
                "model": "anthropic/claude-sonnet-4-5-20250929",
                "cot": False,
                "status": "success",
                "datasets": {
                    "gtfobins": {
                        "detection_rate": 0.951,
                        "detection_rate_macro": 0.93,
                        "pass_rate": 0.0,
                        "false_positive_rate": 1.0,
                        "accuracy": 0.951,
                        "stderr": 0.0103,
                        "total_commands": 431,
                        "correct": 410,
                        "per_category_detection_rates": {
                            "reverse-shell": {"count": 19, "detection_rate": 1.0},
                            "file-read": {"count": 200, "detection_rate": 0.96},
                            "shell": {"count": 150, "detection_rate": 0.94},
                            "command": {"count": 30, "detection_rate": 0.70},
                        },
                        "latency": {
                            "mean": 37780.0,
                            "p50": 36264.0,
                            "p90": 53900.0,
                            "p99": 174680.0,
                            "max": 180038.0,
                        },
                        "cost": {
                            "total_cost": 2.85,
                            "cost_per_1000": 6.61,
                            "cost_per_command": 0.0066,
                        },
                    },
                    "harmless": {
                        "detection_rate": 0.0,
                        "pass_rate": 0.955,
                        "false_positive_rate": 0.045,
                        "accuracy": 0.955,
                        "stderr": 0.0118,
                        "total_commands": 310,
                        "correct": 296,
                        "latency": {
                            "mean": 33358.0,
                            "p50": 21543.0,
                            "p90": 68813.0,
                            "p99": 129029.0,
                            "max": 180024.0,
                        },
                        "cost": {
                            "total_cost": 1.97,
                            "cost_per_1000": 6.35,
                            "cost_per_command": 0.0064,
                        },
                    },
                },
                "composite": {
                    "aegish_score": 0.908,
                    "aegish_score_se": 0.015,
                    "total_cost_usd": 4.82,
                    "cost_per_1000_combined": 6.50,
                    "avg_latency_ms": 35569.0,
                },
            },
        },
        "ranking": [
            {
                "rank": 1,
                "model": "anthropic/claude-sonnet-4-5-20250929",
                "aegish_score": 0.908,
                "cost_per_1000": 6.50,
            },
            {
                "rank": 2,
                "model": "openai/gpt-5.1",
                "aegish_score": 0.883,
                "cost_per_1000": 4.73,
            },
            {
                "rank": 3,
                "model": "google/gemini-3-flash-preview",
                "aegish_score": 0.846,
                "cost_per_1000": 0.0,
            },
        ],
    }


@pytest.fixture()
def comparison_json_file(tmp_path: object, minimal_comparison_data: dict) -> object:
    """Write minimal comparison data to a temp JSON file."""
    filepath = tmp_path / "comparison_test.json"
    with open(filepath, "w") as f:
        json.dump(minimal_comparison_data, f)
    return filepath


@pytest.fixture()
def comparison_with_failed_model(minimal_comparison_data: dict) -> dict:
    """Comparison data that includes a failed model."""
    data = minimal_comparison_data.copy()
    data["results"] = dict(data["results"])
    data["results"]["openrouter/failed-model"] = {
        "model": "openrouter/failed-model",
        "cot": False,
        "status": "error",
        "error": "API timeout",
        "datasets": {},
        "composite": {
            "aegish_score": 0.0,
            "aegish_score_se": None,
            "total_cost_usd": 0.0,
            "cost_per_1000_combined": 0.0,
            "avg_latency_ms": 0.0,
        },
    }
    return data


class TestLoadComparisonResults:
    """Tests for load_comparison_results()."""

    def test_load_valid_json(self, comparison_json_file):
        data = load_comparison_results(comparison_json_file)
        assert "metadata" in data
        assert "results" in data
        assert "ranking" in data
        assert len(data["results"]) == 3

    def test_load_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_comparison_results(tmp_path / "nonexistent.json")

    def test_load_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_comparison_results(bad_file)


class TestGetProvider:
    """Tests for get_provider()."""

    def test_openai(self):
        assert get_provider("openai/gpt-5.1") == "openai"

    def test_anthropic(self):
        assert get_provider("anthropic/claude-opus-4-6") == "anthropic"

    def test_google(self):
        assert get_provider("google/gemini-3-flash-preview") == "google"

    def test_openrouter(self):
        assert get_provider("openrouter/microsoft/phi-4") == "openrouter"

    def test_openrouter_nested(self):
        assert get_provider("openrouter/microsoft/phi-4") == "openrouter"

    def test_hf_inference(self):
        assert (
            get_provider(
                "hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai"
            )
            == "hf-inference-providers"
        )


class TestGetShortName:
    """Tests for get_short_name()."""

    def test_simple_model(self):
        assert get_short_name("openai/gpt-5.1") == "gpt-5.1"

    def test_anthropic_with_date(self):
        assert (
            get_short_name("anthropic/claude-sonnet-4-5-20250929")
            == "claude-sonnet-4-5"
        )

    def test_anthropic_haiku_with_date(self):
        assert (
            get_short_name("anthropic/claude-haiku-4-5-20251001") == "claude-haiku-4-5"
        )

    def test_openrouter_nested(self):
        assert (
            get_short_name("openrouter/microsoft/phi-4")
            == "phi-4"
        )

    def test_hf_with_colon(self):
        assert (
            get_short_name(
                "hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai"
            )
            == "Foundation-Sec-8B-Instruct"
        )

    def test_google_model(self):
        assert (
            get_short_name("google/gemini-3-flash-preview") == "gemini-3-flash-preview"
        )


class TestComputeParetoFrontier:
    """Tests for compute_pareto_frontier()."""

    def test_basic_frontier(self):
        costs = [1.0, 2.0, 3.0]
        scores = [0.5, 0.8, 0.7]
        frontier = compute_pareto_frontier(costs, scores)
        assert (1.0, 0.5) in frontier
        assert (2.0, 0.8) in frontier
        # (3.0, 0.7) is dominated by (2.0, 0.8) - cheaper AND higher score
        assert (3.0, 0.7) not in frontier

    def test_single_point(self):
        frontier = compute_pareto_frontier([5.0], [0.9])
        assert frontier == [(5.0, 0.9)]

    def test_all_dominated(self):
        # Each point has higher cost but lower score
        costs = [1.0, 2.0, 3.0]
        scores = [0.9, 0.8, 0.7]
        frontier = compute_pareto_frontier(costs, scores)
        # Only the first point is non-dominated
        assert frontier == [(1.0, 0.9)]

    def test_zero_cost_point(self):
        costs = [0.0, 5.0, 10.0]
        scores = [0.85, 0.90, 0.91]
        frontier = compute_pareto_frontier(costs, scores)
        assert (0.0, 0.85) in frontier
        assert (5.0, 0.90) in frontier
        assert (10.0, 0.91) in frontier

    def test_empty_input(self):
        frontier = compute_pareto_frontier([], [])
        assert frontier == []


class TestPlotFunctions:
    """Tests for plot generation functions."""

    def test_plot_cost_vs_score(self, minimal_comparison_data, tmp_path):
        plot_cost_vs_score(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "cost_vs_score.png").exists()
        assert (tmp_path / "cost_vs_score.svg").exists()

    def test_plot_detection_vs_pass(self, minimal_comparison_data, tmp_path):
        plot_detection_vs_pass(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "detection_vs_pass.png").exists()
        assert (tmp_path / "detection_vs_pass.svg").exists()

    def test_plot_latency_distribution(self, minimal_comparison_data, tmp_path):
        plot_latency_distribution(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "latency_distribution.png").exists()
        assert (tmp_path / "latency_distribution.svg").exists()

    def test_plot_cost_comparison(self, minimal_comparison_data, tmp_path):
        plot_cost_comparison(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "cost_comparison.png").exists()
        assert (tmp_path / "cost_comparison.svg").exists()

    def test_plot_ranking_table(self, minimal_comparison_data, tmp_path):
        plot_ranking_table(
            minimal_comparison_data["results"],
            minimal_comparison_data["ranking"],
            tmp_path,
        )
        assert (tmp_path / "ranking_table.png").exists()
        assert (tmp_path / "ranking_table.svg").exists()

    def test_plot_category_heatmap(self, minimal_comparison_data, tmp_path):
        plot_category_heatmap(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "category_heatmap.png").exists()
        assert (tmp_path / "category_heatmap.svg").exists()

    def test_plot_micro_vs_macro(self, minimal_comparison_data, tmp_path):
        plot_micro_vs_macro(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "micro_vs_macro.png").exists()
        assert (tmp_path / "micro_vs_macro.svg").exists()


class TestGenerateAllPlots:
    """Tests for generate_all_plots()."""

    def test_generates_all_files(self, comparison_json_file, tmp_path):
        output_dir = tmp_path / "plots"
        generated = generate_all_plots(comparison_json_file, output_dir)

        expected_basenames = [
            "category_heatmap",
            "cost_comparison",
            "cost_vs_score",
            "detection_vs_pass",
            "latency_distribution",
            "micro_vs_macro",
            "ranking_table",
        ]

        for name in expected_basenames:
            assert (output_dir / f"{name}.png").exists(), f"Missing {name}.png"
            assert (output_dir / f"{name}.svg").exists(), f"Missing {name}.svg"

        # 7 plots x 2 formats = 14 files
        assert len(generated) == 14

    def test_creates_output_directory(self, comparison_json_file, tmp_path):
        output_dir = tmp_path / "nested" / "plots"
        generate_all_plots(comparison_json_file, output_dir)
        assert output_dir.exists()


class TestCliArgParsing:
    """Tests for CLI argument parsing."""

    def test_parse_comparison_file_positional(self):
        import argparse

        from benchmark.plots import main  # noqa: F401

        parser = argparse.ArgumentParser()
        parser.add_argument("comparison_file", type=Path)
        parser.add_argument("--output-dir", type=Path, default=None)
        args = parser.parse_args(["results.json"])
        assert args.comparison_file == Path("results.json")
        assert args.output_dir is None

    def test_parse_output_dir_flag(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("comparison_file", type=Path)
        parser.add_argument("--output-dir", type=Path, default=None)
        args = parser.parse_args(["results.json", "--output-dir", "/tmp/plots"])
        assert args.comparison_file == Path("results.json")
        assert args.output_dir == Path("/tmp/plots")

    def test_missing_positional_arg_exits(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("comparison_file", type=Path)
        parser.add_argument("--output-dir", type=Path, default=None)
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_default_output_dir_when_none(self):
        """Verify main() defaults output_dir to benchmark/results/plots/."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("comparison_file", type=Path)
        parser.add_argument("--output-dir", type=Path, default=None)
        args = parser.parse_args(["test.json"])
        if args.output_dir is None:
            args.output_dir = Path("benchmark/results/plots")
        assert args.output_dir == Path("benchmark/results/plots")


class TestZeroCostModels:
    """Tests for handling models with $0 cost."""

    def test_zero_cost_in_cost_comparison(self, minimal_comparison_data, tmp_path):
        # google/gemini-3-flash-preview has $0 cost
        plot_cost_comparison(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "cost_comparison.png").exists()

    def test_zero_cost_in_scatter(self, minimal_comparison_data, tmp_path):
        plot_cost_vs_score(minimal_comparison_data["results"], tmp_path)
        assert (tmp_path / "cost_vs_score.png").exists()


class TestFailedModelHandling:
    """Tests for handling models with status != 'success'."""

    def test_failed_models_excluded_from_plots(
        self, comparison_with_failed_model, tmp_path
    ):
        results = comparison_with_failed_model["results"]
        plot_cost_vs_score(results, tmp_path)
        assert (tmp_path / "cost_vs_score.png").exists()
        # The plot should succeed without error - failed models are filtered

    def test_failed_models_excluded_from_ranking_table(
        self, comparison_with_failed_model, tmp_path
    ):
        results = comparison_with_failed_model["results"]
        ranking = [
            {
                "rank": 1,
                "model": "anthropic/claude-sonnet-4-5-20250929",
                "aegish_score": 0.908,
                "cost_per_1000": 6.50,
            },
            {
                "rank": 2,
                "model": "openai/gpt-5.1",
                "aegish_score": 0.883,
                "cost_per_1000": 4.73,
            },
            {
                "rank": 3,
                "model": "google/gemini-3-flash-preview",
                "aegish_score": 0.846,
                "cost_per_1000": 0.0,
            },
        ]
        plot_ranking_table(results, ranking, tmp_path)
        assert (tmp_path / "ranking_table.png").exists()


class TestSavePlot:
    """Tests for save_plot()."""

    def test_save_creates_both_formats(self, tmp_path):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 2, 3])
        save_plot(fig, tmp_path / "test_plot")
        assert (tmp_path / "test_plot.png").exists()
        assert (tmp_path / "test_plot.svg").exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([1, 2], [1, 2])
        save_plot(fig, tmp_path / "nested" / "dir" / "plot")
        assert (tmp_path / "nested" / "dir" / "plot.png").exists()


class TestGetProviderColor:
    """Tests for get_provider_color()."""

    def test_known_provider(self):
        color = get_provider_color("openai/gpt-5.1")
        assert color == "#10A37F"

    def test_unknown_provider(self):
        color = get_provider_color("unknown/some-model")
        assert color == "#888888"
