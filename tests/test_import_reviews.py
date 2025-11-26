"""Tests for review import and cleaning functionality."""

import pytest
import importlib.util
from datetime import datetime

# Load the module (can't import directly due to numeric prefix)
spec = importlib.util.spec_from_file_location('import_reviews', 'src/01_import_reviews.py')
import_reviews = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_reviews)


class TestTextCleaning:
    """Tests for text cleaning functions."""

    def test_remove_html_tags(self):
        """Test HTML tag removal."""
        text = "This is <b>bold</b> and <i>italic</i>"
        result = import_reviews.remove_html_tags(text)
        assert "<b>" not in result
        assert "<i>" not in result
        assert "bold" in result
        assert "italic" in result

    def test_remove_html_tags_empty(self):
        """Test HTML removal with empty text."""
        assert import_reviews.remove_html_tags("") == ""
        assert import_reviews.remove_html_tags(None) == None

    def test_remove_urls_http(self):
        """Test HTTP URL removal."""
        text = "Check https://example.com for info"
        result = import_reviews.remove_urls(text)
        assert "https://example.com" not in result
        assert "Check" in result
        assert "for info" in result

    def test_remove_urls_www(self):
        """Test www URL removal."""
        text = "Visit www.example.com today"
        result = import_reviews.remove_urls(text)
        assert "www.example.com" not in result
        assert "Visit" in result
        assert "today" in result

    def test_remove_urls_empty(self):
        """Test URL removal with empty text."""
        assert import_reviews.remove_urls("") == ""
        assert import_reviews.remove_urls(None) == None

    def test_remove_emojis_basic(self):
        """Test basic emoji removal."""
        text = "Great app! 😊👍"
        result = import_reviews.remove_emojis(text)
        assert "😊" not in result
        assert "👍" not in result
        assert "Great app!" in result

    def test_remove_emojis_keeps_punctuation(self):
        """Test that punctuation is preserved."""
        text = "Love it! Works great."
        result = import_reviews.remove_emojis(text)
        assert "!" in result
        assert "." in result

    def test_remove_emojis_empty(self):
        """Test emoji removal with empty text."""
        assert import_reviews.remove_emojis("") == ""
        assert import_reviews.remove_emojis(None) == None

    def test_clean_whitespace_multiple_spaces(self):
        """Test excessive whitespace removal."""
        text = "Too   many    spaces"
        result = import_reviews.clean_whitespace(text)
        assert result == "Too many spaces"

    def test_clean_whitespace_leading_trailing(self):
        """Test leading/trailing whitespace removal."""
        text = "  trimmed  "
        result = import_reviews.clean_whitespace(text)
        assert result == "trimmed"

    def test_clean_whitespace_newlines(self):
        """Test newline normalization."""
        text = "Line1\n\n\nLine2"
        result = import_reviews.clean_whitespace(text)
        assert result == "Line1 Line2"

    def test_clean_whitespace_empty(self):
        """Test whitespace cleaning with empty text."""
        assert import_reviews.clean_whitespace("") == ""
        assert import_reviews.clean_whitespace(None) == None

    def test_clean_review_text_full_pipeline(self):
        """Test complete cleaning pipeline."""
        text = (
            "<p>Contact test@example.com or call 9876543210</p>\n"
            "Visit https://example.com 😊\n"
            "Thanks @support!"
        )
        result = import_reviews.clean_review_text(text)

        # Check cleaning
        assert "<p>" not in result
        assert "https://" not in result
        assert "😊" not in result

        # Check PII scrubbing
        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[USER]" in result
        assert "test@example.com" not in result
        assert "9876543210" not in result
        assert "@support" not in result

    def test_clean_review_text_preserves_content(self):
        """Test that meaningful content is preserved."""
        text = "Great app for investing! Highly recommended."
        result = import_reviews.clean_review_text(text)
        assert "Great app" in result
        assert "investing" in result
        assert "recommended" in result

    def test_clean_review_text_empty(self):
        """Test cleaning with empty text."""
        assert import_reviews.clean_review_text("") == ""
        assert import_reviews.clean_review_text(None) == None


class TestReviewProcessing:
    """Tests for review data processing."""

    def test_process_reviews_basic(self):
        """Test basic review processing."""
        # This would require mocking google_play_scraper
        # Skipped for now as it needs complex setup
        pass

    def test_date_filtering(self):
        """Test date range filtering logic."""
        # This would require creating mock DataFrame
        # Skipped for now
        pass


class TestDataValidation:
    """Tests for data validation."""

    def test_empty_content_removal(self):
        """Test that empty reviews are removed."""
        # Would need DataFrame setup
        pass

    def test_required_columns(self):
        """Test required column validation."""
        # Would need DataFrame setup
        pass
