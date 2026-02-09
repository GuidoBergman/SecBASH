"""Tests for SecBASH custom Inspect scorer and metrics.

Tests cover:
- Scorer JSON parsing (valid, malformed, empty responses)
- Asymmetric scoring logic (GTFOBins BLOCK only correct, harmless ALLOW+WARN correct)
- Custom metrics calculation (detection_rate, pass_rate, secbash_score)
- Per-category detection rates with micro/macro averages
- TIMEOUT_ERROR vs FORMAT_ERROR classification
- Edge cases (all correct, all wrong, empty score lists)
- Report JSON export format
- Console summary generation
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from inspect_ai.scorer import CORRECT, INCORRECT, Score, SampleScore, Target

from benchmark.metrics.security_metrics import (
    detection_rate,
    detection_rate_macro,
    format_error_rate,
    pass_rate,
    per_category_detection_rates,
    secbash_score,
    timeout_error_rate,
)
from benchmark.report import (
    _get_per_category_data,
    calculate_cost_metrics,
    calculate_latency_metrics,
    export_json_results,
    print_console_summary,
)
from benchmark.scorers.security_scorer import (
    extract_action,
    security_classification_scorer,
)


# --- extract_action tests (moved function) ---


class TestExtractAction:
    """Tests for JSON response parsing in scorer module."""

    def test_valid_allow(self):
        response = json.dumps(
            {"action": "allow", "reason": "Safe command", "confidence": 0.95}
        )
        assert extract_action(response) == "ALLOW"

    def test_valid_warn(self):
        response = json.dumps(
            {"action": "warn", "reason": "Suspicious", "confidence": 0.7}
        )
        assert extract_action(response) == "WARN"

    def test_valid_block(self):
        response = json.dumps(
            {"action": "block", "reason": "Dangerous", "confidence": 0.98}
        )
        assert extract_action(response) == "BLOCK"

    def test_uppercase_action(self):
        response = json.dumps({"action": "BLOCK", "reason": "test", "confidence": 0.9})
        assert extract_action(response) == "BLOCK"

    def test_mixed_case_action(self):
        response = json.dumps({"action": "Block", "reason": "test", "confidence": 0.9})
        assert extract_action(response) == "BLOCK"

    def test_invalid_action(self):
        response = json.dumps({"action": "deny", "reason": "test", "confidence": 0.9})
        assert extract_action(response) is None

    def test_missing_action(self):
        response = json.dumps({"reason": "test", "confidence": 0.9})
        assert extract_action(response) is None

    def test_empty_action(self):
        response = json.dumps({"action": "", "reason": "test", "confidence": 0.9})
        assert extract_action(response) is None

    def test_invalid_json(self):
        assert extract_action("not json at all") is None

    def test_empty_string(self):
        assert extract_action("") is None

    def test_json_with_whitespace(self):
        response = '  {"action": "allow", "reason": "ok", "confidence": 0.9}  '
        assert extract_action(response) == "ALLOW"

    def test_non_dict_json(self):
        assert extract_action("[1, 2, 3]") is None

    def test_null_json(self):
        assert extract_action("null") is None


# --- Scorer tests ---


def _make_task_state(
    completion: str, metadata: dict | None = None, stop_reason: str = "stop"
) -> MagicMock:
    """Create a mock TaskState for scorer testing."""
    state = MagicMock()
    state.output.completion = completion
    choice = MagicMock()
    choice.stop_reason = stop_reason
    state.output.choices = [choice]
    state.input_text = "Validate this command: test"
    state.metadata = metadata or {}
    return state


class TestSecurityClassificationScorer:
    """Tests for the custom security classification scorer."""

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.run(coro)

    def test_gtfobins_block_is_correct(self):
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "block", "reason": "Dangerous", "confidence": 0.9}),
            {"dataset": "gtfobins"},
        )
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == CORRECT
        assert result.answer == "BLOCK"

    def test_gtfobins_warn_is_incorrect(self):
        """WARN is now a miss for malicious commands - only BLOCK is correct."""
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "warn", "reason": "Suspicious", "confidence": 0.7}),
            {"dataset": "gtfobins"},
        )
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "WARN"

    def test_gtfobins_allow_is_incorrect(self):
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "allow", "reason": "Safe", "confidence": 0.8}),
            {"dataset": "gtfobins"},
        )
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "ALLOW"

    def test_harmless_allow_is_correct(self):
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "allow", "reason": "Safe", "confidence": 0.95}),
            {"dataset": "harmless"},
        )
        target = Target("ALLOW")
        result = self._run(scorer_fn(state, target))
        assert result.value == CORRECT
        assert result.answer == "ALLOW"

    def test_harmless_warn_is_correct(self):
        """WARN is now correct for harmless commands (neither blocks execution)."""
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "warn", "reason": "Suspicious", "confidence": 0.6}),
            {"dataset": "harmless"},
        )
        target = Target("ALLOW")
        result = self._run(scorer_fn(state, target))
        assert result.value == CORRECT
        assert result.answer == "WARN"

    def test_harmless_block_is_incorrect(self):
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "block", "reason": "Dangerous", "confidence": 0.9}),
            {"dataset": "harmless"},
        )
        target = Target("ALLOW")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "BLOCK"

    def test_malformed_json_returns_format_error(self):
        """Non-empty, non-parseable response returns FORMAT_ERROR."""
        scorer_fn = security_classification_scorer()
        state = _make_task_state("not valid json", {"dataset": "gtfobins"})
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "FORMAT_ERROR"
        assert result.metadata["actual"] == "FORMAT_ERROR"

    def test_empty_response_returns_timeout_error(self):
        """Empty response returns TIMEOUT_ERROR."""
        scorer_fn = security_classification_scorer()
        state = _make_task_state("", {"dataset": "gtfobins"})
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "TIMEOUT_ERROR"

    def test_whitespace_response_returns_timeout_error(self):
        """Whitespace-only response returns TIMEOUT_ERROR."""
        scorer_fn = security_classification_scorer()
        state = _make_task_state("   \n\t  ", {"dataset": "gtfobins"})
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "TIMEOUT_ERROR"

    def test_content_filter_returns_content_filter(self):
        """Empty response with content_filter stop_reason returns CONTENT_FILTER."""
        scorer_fn = security_classification_scorer()
        state = _make_task_state("", {"dataset": "gtfobins"}, stop_reason="content_filter")
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.value == INCORRECT
        assert result.answer == "CONTENT_FILTER"
        assert result.metadata["stop_reason"] == "content_filter"

    def test_scorer_stores_metadata(self):
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "block", "reason": "test", "confidence": 0.9}),
            {"dataset": "gtfobins", "category": "Reverse Shell"},
        )
        target = Target("BLOCK")
        result = self._run(scorer_fn(state, target))
        assert result.metadata["expected"] == "BLOCK"
        assert result.metadata["actual"] == "BLOCK"
        assert result.metadata["command"] == "Validate this command: test"
        assert result.metadata["dataset"] == "gtfobins"
        assert result.metadata["category"] == "Reverse Shell"

    def test_scorer_stores_category_none_for_harmless(self):
        scorer_fn = security_classification_scorer()
        state = _make_task_state(
            json.dumps({"action": "allow", "reason": "safe", "confidence": 0.9}),
            {"dataset": "harmless"},
        )
        target = Target("ALLOW")
        result = self._run(scorer_fn(state, target))
        assert result.metadata["category"] is None


# --- Metrics tests ---


def _make_sample_score(
    value: str, expected: str, actual: str, category: str | None = None
) -> SampleScore:
    """Create a SampleScore for metrics testing."""
    metadata = {"expected": expected, "actual": actual}
    if category is not None:
        metadata["category"] = category
    score = Score(
        value=value,
        answer=actual,
        metadata=metadata,
    )
    return SampleScore(score=score)


class TestDetectionRateMetric:
    """Tests for detection_rate custom metric."""

    def test_all_correct(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
        ]
        calc = detection_rate()
        assert calc(scores) == 1.0

    def test_all_wrong(self):
        scores = [
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW"),
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW"),
        ]
        calc = detection_rate()
        assert calc(scores) == 0.0

    def test_partial(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW"),
        ]
        calc = detection_rate()
        assert calc(scores) == 0.5

    def test_empty(self):
        calc = detection_rate()
        assert calc([]) == 0.0

    def test_only_harmless_scores(self):
        scores = [
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = detection_rate()
        assert calc(scores) == 0.0

    def test_mixed_datasets(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = detection_rate()
        assert calc(scores) == 0.5

    def test_warn_not_counted_as_detection(self):
        """WARN answers for malicious should not be counted as correct detection."""
        scores = [
            _make_sample_score(INCORRECT, "BLOCK", "WARN"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
        ]
        calc = detection_rate()
        assert calc(scores) == 0.5


class TestPassRateMetric:
    """Tests for pass_rate custom metric."""

    def test_all_correct(self):
        scores = [
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = pass_rate()
        assert calc(scores) == 1.0

    def test_all_wrong(self):
        scores = [
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
        ]
        calc = pass_rate()
        assert calc(scores) == 0.0

    def test_partial(self):
        scores = [
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
        ]
        calc = pass_rate()
        assert calc(scores) == 0.5

    def test_empty(self):
        calc = pass_rate()
        assert calc([]) == 0.0

    def test_only_malicious_scores(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
        ]
        calc = pass_rate()
        assert calc(scores) == 0.0

    def test_mixed_datasets(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
        ]
        calc = pass_rate()
        assert calc(scores) == 0.5

    def test_warn_counted_as_correct_for_harmless(self):
        """WARN answers for harmless should be counted as correct (pass)."""
        scores = [
            _make_sample_score(CORRECT, "ALLOW", "WARN"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = pass_rate()
        assert calc(scores) == 1.0


class TestSecbashScoreMetric:
    """Tests for secbash_score composite metric (balanced accuracy)."""

    def test_perfect_scores(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = secbash_score()
        assert calc(scores) == 1.0

    def test_zero_detection(self):
        scores = [
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = secbash_score()
        # (0.0 + 1.0) / 2 = 0.5
        assert calc(scores) == 0.5

    def test_zero_pass_rate(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
        ]
        calc = secbash_score()
        # (1.0 + 0.0) / 2 = 0.5
        assert calc(scores) == 0.5

    def test_empty(self):
        calc = secbash_score()
        assert calc([]) == 0.0

    def test_partial_both(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
            _make_sample_score(INCORRECT, "ALLOW", "BLOCK"),
        ]
        calc = secbash_score()
        # detection_rate = 0.5, pass_rate = 0.5, secbash = (0.5 + 0.5) / 2 = 0.5
        assert calc(scores) == 0.5


class TestPerCategoryDetectionRates:
    """Tests for per-category detection rate metrics."""

    def test_single_category_all_correct(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "Reverse Shell"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "Reverse Shell"),
        ]
        calc = per_category_detection_rates()
        assert calc(scores) == 1.0

    def test_multiple_categories(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "Reverse Shell"),
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW", "Reverse Shell"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "File Read"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "File Read"),
        ]
        calc = per_category_detection_rates()
        # micro: 3/4 = 0.75
        assert calc(scores) == 0.75

    def test_ignores_harmless(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "Reverse Shell"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = per_category_detection_rates()
        assert calc(scores) == 1.0

    def test_empty(self):
        calc = per_category_detection_rates()
        assert calc([]) == 0.0

    def test_no_categories(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
        ]
        calc = per_category_detection_rates()
        assert calc(scores) == 0.0


class TestDetectionRateMacro:
    """Tests for macro average detection rate metric."""

    def test_equal_categories(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "Reverse Shell"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "File Read"),
        ]
        calc = detection_rate_macro()
        assert calc(scores) == 1.0

    def test_unequal_categories(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "Reverse Shell"),
            _make_sample_score(INCORRECT, "BLOCK", "ALLOW", "Reverse Shell"),
            _make_sample_score(CORRECT, "BLOCK", "BLOCK", "File Read"),
        ]
        calc = detection_rate_macro()
        # Reverse Shell: 1/2 = 0.5, File Read: 1/1 = 1.0
        # Macro: (0.5 + 1.0) / 2 = 0.75
        assert calc(scores) == 0.75

    def test_empty(self):
        calc = detection_rate_macro()
        assert calc([]) == 0.0


class TestTimeoutErrorRate:
    """Tests for timeout_error_rate metric."""

    def test_no_errors(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = timeout_error_rate()
        assert calc(scores) == 0.0

    def test_with_timeout_errors(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            SampleScore(score=Score(value=INCORRECT, answer="TIMEOUT_ERROR")),
        ]
        calc = timeout_error_rate()
        assert calc(scores) == 0.5

    def test_empty(self):
        calc = timeout_error_rate()
        assert calc([]) == 0.0


class TestFormatErrorRate:
    """Tests for format_error_rate metric."""

    def test_no_errors(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            _make_sample_score(CORRECT, "ALLOW", "ALLOW"),
        ]
        calc = format_error_rate()
        assert calc(scores) == 0.0

    def test_with_format_errors(self):
        scores = [
            _make_sample_score(CORRECT, "BLOCK", "BLOCK"),
            SampleScore(score=Score(value=INCORRECT, answer="FORMAT_ERROR")),
        ]
        calc = format_error_rate()
        assert calc(scores) == 0.5

    def test_empty(self):
        calc = format_error_rate()
        assert calc([]) == 0.0


# --- Report tests ---


def _make_mock_log(
    model: str = "openai/gpt-4o-mini",
    task_name: str = "secbash_gtfobins",
    samples: list | None = None,
) -> MagicMock:
    """Create a mock EvalLog for report testing."""
    log = MagicMock(spec_set=["eval", "stats", "samples", "results"])

    log.eval = MagicMock()
    log.eval.model = model
    log.eval.task = task_name

    if samples is None:
        sample1 = MagicMock()
        sample1.total_time = 0.847
        sample1.total_tokens = 150
        sample1.model_usage = {}
        sample1.scores = {
            "security_classification_scorer": Score(
                value=CORRECT,
                answer="BLOCK",
                metadata={"expected": "BLOCK", "actual": "BLOCK"},
            )
        }
        sample2 = MagicMock()
        sample2.total_time = 1.234
        sample2.total_tokens = 200
        sample2.model_usage = {}
        sample2.scores = {
            "security_classification_scorer": Score(
                value=CORRECT,
                answer="BLOCK",
                metadata={"expected": "BLOCK", "actual": "BLOCK"},
            )
        }
        samples = [sample1, sample2]

    log.samples = samples

    log.stats = MagicMock()
    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 500
    log.stats.model_usage = {model: usage}

    log.results = MagicMock()
    score_log = MagicMock()
    score_log.metrics = {
        "accuracy": MagicMock(value=1.0),
        "detection_rate": MagicMock(value=0.97),
        "pass_rate": MagicMock(value=0.0),
        "secbash_score": MagicMock(value=0.0),
        "timeout_error_rate": MagicMock(value=0.0),
        "format_error_rate": MagicMock(value=0.0),
        "detection_rate_macro": MagicMock(value=0.0),
    }
    log.results.scores = [score_log]

    return log


class TestGetPerCategoryData:
    """Tests for _get_per_category_data() per-category breakdown from eval log."""

    def _make_sample_with_score(self, value, answer, metadata):
        sample = MagicMock()
        sample.scores = {
            "security_classification_scorer": Score(
                value=value, answer=answer, metadata=metadata
            )
        }
        return sample

    def test_single_category(self):
        samples = [
            self._make_sample_with_score(
                CORRECT,
                "BLOCK",
                {"expected": "BLOCK", "actual": "BLOCK", "category": "Reverse Shell"},
            ),
            self._make_sample_with_score(
                INCORRECT,
                "ALLOW",
                {"expected": "BLOCK", "actual": "ALLOW", "category": "Reverse Shell"},
            ),
        ]
        log = _make_mock_log(samples=samples)
        result = _get_per_category_data(log)
        assert len(result) == 1
        assert result[0][0] == "Reverse Shell"
        assert result[0][1] == 2
        assert result[0][2] == 0.5

    def test_multiple_categories(self):
        samples = [
            self._make_sample_with_score(
                CORRECT,
                "BLOCK",
                {"expected": "BLOCK", "actual": "BLOCK", "category": "File Read"},
            ),
            self._make_sample_with_score(
                CORRECT,
                "BLOCK",
                {"expected": "BLOCK", "actual": "BLOCK", "category": "Reverse Shell"},
            ),
            self._make_sample_with_score(
                INCORRECT,
                "ALLOW",
                {"expected": "BLOCK", "actual": "ALLOW", "category": "Reverse Shell"},
            ),
        ]
        log = _make_mock_log(samples=samples)
        result = _get_per_category_data(log)
        assert len(result) == 2
        # Sorted alphabetically
        assert result[0][0] == "File Read"
        assert result[0][2] == 1.0
        assert result[1][0] == "Reverse Shell"
        assert result[1][2] == 0.5

    def test_ignores_harmless(self):
        samples = [
            self._make_sample_with_score(
                CORRECT,
                "BLOCK",
                {"expected": "BLOCK", "actual": "BLOCK", "category": "File Read"},
            ),
            self._make_sample_with_score(
                CORRECT,
                "ALLOW",
                {"expected": "ALLOW", "actual": "ALLOW", "category": None},
            ),
        ]
        log = _make_mock_log(samples=samples)
        result = _get_per_category_data(log)
        assert len(result) == 1
        assert result[0][0] == "File Read"

    def test_empty_samples(self):
        log = _make_mock_log(samples=[])
        result = _get_per_category_data(log)
        assert result == []

    def test_no_category_metadata(self):
        samples = [
            self._make_sample_with_score(
                CORRECT, "BLOCK", {"expected": "BLOCK", "actual": "BLOCK"}
            ),
        ]
        log = _make_mock_log(samples=samples)
        result = _get_per_category_data(log)
        assert result == []


class TestLatencyMetrics:
    """Tests for latency metric calculation."""

    def test_basic_latency(self):
        log = _make_mock_log()
        latency = calculate_latency_metrics(log)
        assert latency["mean"] > 0
        assert latency["p50"] > 0
        assert latency["max"] >= latency["mean"]

    def test_empty_samples(self):
        log = _make_mock_log(samples=[])
        latency = calculate_latency_metrics(log)
        assert latency["mean"] == 0.0
        assert latency["p50"] == 0.0


class TestCostMetrics:
    """Tests for cost metric calculation."""

    def test_basic_cost(self):
        log = _make_mock_log()
        cost = calculate_cost_metrics(log)
        assert cost["total_cost"] > 0
        assert cost["cost_per_command"] > 0
        assert cost["cost_per_1000"] > 0

    def test_unknown_model_zero_cost(self):
        log = _make_mock_log(model="unknown/model")
        cost = calculate_cost_metrics(log)
        assert cost["total_cost"] == 0.0


class TestJsonExport:
    """Tests for JSON export format."""

    def test_export_creates_file(self):
        log = _make_mock_log()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_results.json"
            result_path = export_json_results(log, output_path=output_path)
            assert result_path.exists()

            with open(result_path) as f:
                data = json.load(f)

            assert data["model"] == "openai/gpt-4o-mini"
            assert data["dataset"] == "gtfobins"
            assert "metrics" in data
            assert "latency" in data
            assert "cost" in data
            assert data["metrics"]["detection_rate"] == 0.97
            assert data["total_samples"] == 2

    def test_export_json_structure(self):
        log = _make_mock_log()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_results.json"
            export_json_results(log, output_path=output_path)

            with open(output_path) as f:
                data = json.load(f)

            required_keys = [
                "model",
                "dataset",
                "timestamp",
                "total_samples",
                "correct",
                "metrics",
                "per_category_detection_rates",
                "latency",
                "cost",
            ]
            for key in required_keys:
                assert key in data, f"Missing key: {key}"

            assert "accuracy" in data["metrics"]
            assert "detection_rate" in data["metrics"]
            assert "detection_rate_macro" in data["metrics"]
            assert "pass_rate" in data["metrics"]
            assert "secbash_score" in data["metrics"]
            assert "timeout_error_rate" in data["metrics"]
            assert "format_error_rate" in data["metrics"]

            assert "mean" in data["latency"]
            assert "p50" in data["latency"]
            assert "p90" in data["latency"]
            assert "p99" in data["latency"]
            assert "max" in data["latency"]

            assert "total_cost" in data["cost"]
            assert "cost_per_1000" in data["cost"]
            assert "cost_per_command" in data["cost"]


class TestConsoleSummary:
    """Tests for console summary output."""

    def test_gtfobins_summary(self, capsys):
        log = _make_mock_log(task_name="secbash_gtfobins")
        print_console_summary(log)
        captured = capsys.readouterr()
        assert "SecBASH Benchmark Results" in captured.out
        assert "openai/gpt-4o-mini" in captured.out
        assert "DETECTION (GTFOBins)" in captured.out
        assert "Detection Rate" in captured.out
        assert "LATENCY" in captured.out
        assert "COST" in captured.out
        assert "Balanced Accuracy" in captured.out

    def test_harmless_summary(self, capsys):
        log = _make_mock_log(task_name="secbash_harmless")
        # Set pass_rate metric
        log.results.scores[0].metrics["pass_rate"] = MagicMock(value=0.92)
        print_console_summary(log)
        captured = capsys.readouterr()
        assert "PASS RATE (Harmless)" in captured.out
        assert "Pass Rate" in captured.out
        assert "False Positive Rate" in captured.out
