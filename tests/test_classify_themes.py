"""Tests for theme classification functionality."""

import pytest
import json
import importlib.util
from pathlib import Path

# Load the module (can't import directly due to numeric prefix)
spec = importlib.util.spec_from_file_location('classify_themes', 'src/02_classify_themes.py')
classify_themes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classify_themes)


class TestPromptBuilding:
    """Tests for batch prompt construction."""

    def test_build_batch_prompt_single_review(self):
        """Test batch prompt with single review."""
        base_prompt = "Classify this review:"
        reviews = [
            {'review_id': 'abc', 'text': 'Great app!', 'rating': 5}
        ]

        prompt = classify_themes.build_batch_prompt(base_prompt, reviews)

        assert 'abc' in prompt
        assert 'Great app!' in prompt
        assert '5/5' in prompt
        assert 'JSON array' in prompt

    def test_build_batch_prompt_multiple_reviews(self):
        """Test batch prompt with multiple reviews."""
        base_prompt = "Classify this review:"
        reviews = [
            {'review_id': 'abc', 'text': 'Review 1', 'rating': 5},
            {'review_id': 'xyz', 'text': 'Review 2', 'rating': 3}
        ]

        prompt = classify_themes.build_batch_prompt(base_prompt, reviews)

        assert 'abc' in prompt
        assert 'xyz' in prompt
        assert 'Review 1' in prompt
        assert 'Review 2' in prompt
        assert '---' in prompt  # Separator


class TestResponseParsing:
    """Tests for JSON response parsing."""

    def test_parse_simple_json_array(self):
        """Test parsing simple JSON array."""
        response = '''[
            {"review_id": "abc", "theme": "Onboarding", "reason": "Sign up issue"},
            {"review_id": "xyz", "theme": "Trading/Orders", "reason": "Order delay"}
        ]'''

        result = classify_themes.parse_classification_response(response)

        assert len(result) == 2
        assert result[0]['review_id'] == 'abc'
        assert result[0]['theme'] == 'Onboarding'
        assert result[1]['review_id'] == 'xyz'

    def test_parse_json_with_markdown_fences(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = '''```json
        [
            {"review_id": "abc", "theme": "KYC/Account", "reason": "KYC pending"}
        ]
        ```'''

        result = classify_themes.parse_classification_response(response)

        assert len(result) == 1
        assert result[0]['review_id'] == 'abc'
        assert result[0]['theme'] == 'KYC/Account'

    def test_parse_json_with_plain_fences(self):
        """Test parsing JSON wrapped in plain code blocks."""
        response = '''```
        [{"review_id": "test", "theme": "App UX/Performance", "reason": "Crash"}]
        ```'''

        result = classify_themes.parse_classification_response(response)

        assert len(result) == 1
        assert result[0]['theme'] == 'App UX/Performance'

    def test_parse_invalid_json_raises_error(self):
        """Test that invalid JSON raises error."""
        response = "This is not JSON"

        with pytest.raises(json.JSONDecodeError):
            classify_themes.parse_classification_response(response)

    def test_parse_non_array_raises_error(self):
        """Test that non-array JSON raises error."""
        response = '{"key": "value"}'

        with pytest.raises(ValueError):
            classify_themes.parse_classification_response(response)


class TestThemeValidation:
    """Tests for theme validation."""

    def test_validate_valid_theme(self):
        """Test validation of valid themes."""
        valid_themes = [
            "Onboarding",
            "KYC/Account",
            "Trading/Orders",
            "Withdrawals/Payments",
            "App UX/Performance"
        ]

        for theme in valid_themes:
            result = classify_themes.validate_theme(theme)
            assert result == theme

    def test_validate_invalid_theme_returns_default(self):
        """Test that invalid theme returns default."""
        invalid_theme = "InvalidTheme"

        result = classify_themes.validate_theme(invalid_theme)

        assert result == classify_themes.DEFAULT_THEME

    def test_validate_empty_theme_returns_default(self):
        """Test that empty theme returns default."""
        result = classify_themes.validate_theme("")

        assert result == classify_themes.DEFAULT_THEME

    def test_validate_case_sensitive(self):
        """Test that validation is case-sensitive."""
        # Wrong case should fail
        wrong_case = "onboarding"  # lowercase

        result = classify_themes.validate_theme(wrong_case)

        assert result == classify_themes.DEFAULT_THEME


class TestFileOperations:
    """Tests for file input/output."""

    def test_get_latest_raw_file(self):
        """Test getting latest raw file."""
        # This test would fail if no files exist
        # Skip if no files in raw directory
        try:
            latest = classify_themes.get_latest_raw_file()
            assert latest.exists()
            assert latest.suffix == '.csv'
            assert 'reviews_' in latest.name
        except FileNotFoundError:
            pytest.skip("No raw review files found")

    def test_load_reviews_with_sample_data(self):
        """Test loading reviews from sample CSV."""
        sample_path = Path("data/raw/sample_reviews_test.csv")

        if not sample_path.exists():
            pytest.skip("Sample test file not found")

        df = classify_themes.load_reviews(sample_path)

        assert len(df) > 0
        assert 'review_id' in df.columns
        assert 'text' in df.columns
        assert 'rating' in df.columns

    def test_load_reviews_missing_file(self):
        """Test loading from non-existent file."""
        fake_path = Path("nonexistent.csv")

        with pytest.raises(FileNotFoundError):
            classify_themes.load_reviews(fake_path)


class TestBatchProcessing:
    """Tests for batch processing logic."""

    def test_batch_size_constant(self):
        """Test that batch size is properly defined."""
        assert classify_themes.BATCH_SIZE == 10

    def test_temperature_constant(self):
        """Test that temperature is properly defined."""
        assert classify_themes.TEMPERATURE == 0.1

    def test_default_theme_constant(self):
        """Test that default theme is valid."""
        assert classify_themes.DEFAULT_THEME == "App UX/Performance"


class TestIntegration:
    """Integration tests (require manual verification)."""

    def test_prompt_file_exists(self):
        """Test that classification prompt file exists."""
        from src.config import PROMPTS_DIR

        prompt_path = PROMPTS_DIR / "classify_theme.txt"
        assert prompt_path.exists()

    def test_prompt_contains_themes(self):
        """Test that prompt file contains all themes."""
        from src.config import PROMPTS_DIR, THEME_TAXONOMY

        prompt_path = PROMPTS_DIR / "classify_theme.txt"

        with open(prompt_path, 'r') as f:
            prompt_content = f.read()

        # Check that all themes are mentioned
        for theme in THEME_TAXONOMY.keys():
            assert theme in prompt_content, f"Theme '{theme}' not in prompt"
