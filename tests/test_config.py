"""
Tests for benchmark.config — field spec/prompt alignment and pricing.
"""
import re
import pytest

from benchmark.config import MODELS, FIELD_SPEC, EXTRACT_PROMPT, PRICING, compute_cost


class TestFieldSpecPromptAlignment:
    """Verify FIELD_SPEC fields match what EXTRACT_PROMPT asks the model to extract."""

    def test_all_field_spec_keys_in_prompt(self):
        """Every FIELD_SPEC field should appear in the prompt template."""
        for field_name in FIELD_SPEC:
            assert field_name in EXTRACT_PROMPT, (
                f"FIELD_SPEC field '{field_name}' not found in EXTRACT_PROMPT"
            )

    def test_scoring_types_valid(self):
        """Every scoring type in FIELD_SPEC should be a known scorer."""
        from benchmark.scoring import SCORERS
        for field_name, spec in FIELD_SPEC.items():
            assert spec["scoring"] in SCORERS, (
                f"Field '{field_name}' has unknown scoring type '{spec['scoring']}'"
            )

    def test_weights_positive(self):
        """All weights should be positive."""
        for field_name, spec in FIELD_SPEC.items():
            weight = spec.get("weight", 1.0)
            assert weight > 0, f"Field '{field_name}' has non-positive weight {weight}"

    def test_gt_paths_valid(self):
        """All gt_path values should be non-empty strings."""
        for field_name, spec in FIELD_SPEC.items():
            assert isinstance(spec["gt_path"], str), (
                f"Field '{field_name}' gt_path is not a string"
            )
            assert len(spec["gt_path"]) > 0, (
                f"Field '{field_name}' gt_path is empty"
            )


class TestModelRegistry:
    """Tests for model configuration."""

    def test_all_models_have_provider(self):
        for model_name, cfg in MODELS.items():
            assert "provider" in cfg, f"Model '{model_name}' missing 'provider'"

    def test_all_models_have_model_id(self):
        for model_name, cfg in MODELS.items():
            assert "model_id" in cfg, f"Model '{model_name}' missing 'model_id'"

    def test_providers_valid(self):
        valid_providers = {"openai", "google", "together"}
        for model_name, cfg in MODELS.items():
            assert cfg["provider"] in valid_providers, (
                f"Model '{model_name}' has unknown provider '{cfg['provider']}'"
            )


class TestPricing:
    """Tests for pricing configuration and cost computation."""

    def test_all_models_have_pricing(self):
        for model_name in MODELS:
            assert model_name in PRICING, f"Model '{model_name}' missing pricing entry"

    def test_pricing_format(self):
        for model_name, rates in PRICING.items():
            assert isinstance(rates, tuple) and len(rates) == 2, (
                f"Pricing for '{model_name}' should be (input_rate, output_rate) tuple"
            )
            assert rates[0] >= 0 and rates[1] >= 0, (
                f"Pricing rates for '{model_name}' should be non-negative"
            )

    def test_compute_cost_basic(self):
        cost = compute_cost("gpt-4o", 1000, 100)
        assert cost is not None
        assert cost > 0

    def test_compute_cost_none_tokens(self):
        assert compute_cost("gpt-4o", None, 100) is None
        assert compute_cost("gpt-4o", 1000, None) is None

    def test_compute_cost_unknown_model(self):
        assert compute_cost("unknown-model", 1000, 100) is None

    def test_compute_cost_math(self):
        """Verify cost computation: (in_tok * in_rate + out_tok * out_rate) / 1M."""
        # gpt-4o: $2.50 input, $10.00 output per 1M tokens
        cost = compute_cost("gpt-4o", 1_000_000, 1_000_000)
        assert cost == pytest.approx(2.50 + 10.00)

    def test_compute_cost_small(self):
        """Typical single-image call: ~1500 input, ~300 output."""
        cost = compute_cost("gemini-2.5-flash", 1500, 300)
        # 1500 * 0.15 / 1M + 300 * 0.60 / 1M = 0.000225 + 0.00018 = 0.000405
        assert cost == pytest.approx(0.000405, rel=0.01)
