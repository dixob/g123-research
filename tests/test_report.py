"""
Tests for benchmark.report — bootstrap CI and helper functions.
"""
import pytest

from benchmark.report import (
    _bootstrap_ci,
    _fmt_cost,
    _fmt_tokens,
    _get_per_sample_scores,
    _get_per_sample_extraction_recalls,
)


class TestBootstrapCI:
    """Tests for bootstrap confidence interval computation."""

    def test_single_value(self):
        """Single value returns same value for both bounds."""
        lo, hi = _bootstrap_ci([50.0])
        assert lo == 50.0
        assert hi == 50.0

    def test_empty_list(self):
        """Empty list returns (0.0, 0.0)."""
        lo, hi = _bootstrap_ci([])
        assert lo == 0.0
        assert hi == 0.0

    def test_constant_values(self):
        """Identical values have zero-width CI."""
        lo, hi = _bootstrap_ci([75.0] * 20)
        assert lo == 75.0
        assert hi == 75.0

    def test_ci_contains_mean(self):
        """CI should contain the sample mean."""
        values = [60.0, 70.0, 80.0, 90.0, 75.0, 85.0, 65.0, 95.0]
        lo, hi = _bootstrap_ci(values)
        mean = sum(values) / len(values)
        assert lo <= mean <= hi

    def test_ci_width(self):
        """CI should be narrower with less variance."""
        tight = [74.0, 75.0, 76.0, 75.0, 74.5, 75.5] * 5
        wide = [10.0, 90.0, 20.0, 80.0, 30.0, 70.0] * 5
        lo_t, hi_t = _bootstrap_ci(tight)
        lo_w, hi_w = _bootstrap_ci(wide)
        assert (hi_t - lo_t) < (hi_w - lo_w)

    def test_reproducible(self):
        """Fixed seed should give identical results across calls."""
        values = [60.0, 70.0, 80.0, 90.0, 75.0]
        r1 = _bootstrap_ci(values, seed=42)
        r2 = _bootstrap_ci(values, seed=42)
        assert r1 == r2

    def test_different_seeds(self):
        """Different seeds may give different results (unless data is trivial)."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
        r1 = _bootstrap_ci(values, seed=42)
        r2 = _bootstrap_ci(values, seed=99)
        # Not guaranteed to differ but very likely with 8 diverse values
        # At minimum, both should be valid intervals
        assert r1[0] <= r1[1]
        assert r2[0] <= r2[1]


class TestFmtCost:
    """Tests for cost formatting."""

    def test_none(self):
        assert _fmt_cost(None) == "n/a"

    def test_small(self):
        result = _fmt_cost(0.00012)
        assert result.startswith("$0.0001")

    def test_normal(self):
        result = _fmt_cost(0.0523)
        assert result.startswith("$0.05")

    def test_zero(self):
        result = _fmt_cost(0.0)
        assert "$" in result


class TestFmtTokens:
    """Tests for token count formatting."""

    def test_millions(self):
        assert _fmt_tokens(1_500_000) == "1.5M"

    def test_thousands(self):
        assert _fmt_tokens(1_500) == "1.5K"

    def test_small(self):
        assert _fmt_tokens(500) == "500"


class TestGetPerSampleScores:
    """Tests for extracting per-sample scores."""

    def test_basic(self):
        data = {
            "samples": [
                {"scores": {"weighted_score": 8.0, "max_possible": 10.0}},
                {"scores": {"weighted_score": 6.0, "max_possible": 10.0}},
            ]
        }
        scores = _get_per_sample_scores(data)
        assert len(scores) == 2
        assert scores[0] == 80.0
        assert scores[1] == 60.0

    def test_skips_no_scores(self):
        data = {
            "samples": [
                {"error": "api_error"},
                {"scores": {"weighted_score": 5.0, "max_possible": 10.0}},
            ]
        }
        scores = _get_per_sample_scores(data)
        assert len(scores) == 1

    def test_empty(self):
        assert _get_per_sample_scores({"samples": []}) == []

    def test_no_samples_key(self):
        assert _get_per_sample_scores({}) == []


class TestGetPerSampleExtractionRecalls:
    """Tests for extracting per-sample extraction recall scores."""

    def test_basic(self):
        data = {
            "samples": [
                {"scores": {"extraction_recall": 85.0, "weighted_score": 8.0, "max_possible": 10.0}},
                {"scores": {"extraction_recall": 70.0, "weighted_score": 7.0, "max_possible": 10.0}},
            ]
        }
        recalls = _get_per_sample_extraction_recalls(data)
        assert len(recalls) == 2
        assert recalls[0] == 85.0

    def test_skips_none(self):
        data = {
            "samples": [
                {"scores": {"extraction_recall": None, "weighted_score": 8.0, "max_possible": 10.0}},
                {"scores": {"extraction_recall": 90.0, "weighted_score": 9.0, "max_possible": 10.0}},
            ]
        }
        recalls = _get_per_sample_extraction_recalls(data)
        assert len(recalls) == 1
        assert recalls[0] == 90.0
