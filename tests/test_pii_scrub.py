"""Tests for PII scrubbing functionality."""

import pytest
from src.utils import scrub_email, scrub_phone, scrub_username, scrub_all_pii


class TestEmailScrubbing:
    """Tests for email address scrubbing."""

    def test_simple_email(self):
        """Test simple email address removal."""
        text = "Contact me at john.doe@example.com for help"
        result = scrub_email(text)
        assert "john.doe@example.com" not in result
        assert "[EMAIL]" in result

    def test_multiple_emails(self):
        """Test multiple email addresses."""
        text = "Email me at test@test.com or admin@company.org"
        result = scrub_email(text)
        assert result.count("[EMAIL]") == 2
        assert "test@test.com" not in result
        assert "admin@company.org" not in result

    def test_email_with_numbers(self):
        """Test email with numbers."""
        text = "Reach me at user123@example.com"
        result = scrub_email(text)
        assert "user123@example.com" not in result
        assert "[EMAIL]" in result

    def test_no_email(self):
        """Test text without email."""
        text = "This has no email address"
        result = scrub_email(text)
        assert result == text

    def test_empty_text(self):
        """Test empty text handling."""
        assert scrub_email("") == ""
        assert scrub_email(None) == None


class TestPhoneScrubbing:
    """Tests for phone number scrubbing."""

    def test_indian_phone_basic(self):
        """Test basic 10-digit Indian phone."""
        text = "Call me at 9876543210"
        result = scrub_phone(text)
        assert "9876543210" not in result
        assert "[PHONE]" in result

    def test_indian_phone_with_plus91(self):
        """Test Indian phone with +91 prefix."""
        text = "My number is +919876543210"
        result = scrub_phone(text)
        assert "+919876543210" not in result
        assert "[PHONE]" in result

    def test_indian_phone_with_plus91_dash(self):
        """Test Indian phone with +91- prefix."""
        text = "Reach out at +91-9876543210"
        result = scrub_phone(text)
        assert "+91-9876543210" not in result
        assert "[PHONE]" in result

    def test_indian_phone_with_leading_zero(self):
        """Test Indian phone with leading zero."""
        text = "Contact: 09876543210"
        result = scrub_phone(text)
        assert "09876543210" not in result
        assert "[PHONE]" in result

    def test_international_phone(self):
        """Test international phone format."""
        text = "Call +1-234-567-8900"
        result = scrub_phone(text)
        assert "+1-234-567-8900" not in result
        assert "[PHONE]" in result

    def test_no_phone(self):
        """Test text without phone."""
        text = "This has no phone number"
        result = scrub_phone(text)
        assert result == text

    def test_empty_text(self):
        """Test empty text handling."""
        assert scrub_phone("") == ""
        assert scrub_phone(None) == None


class TestUsernameScrubbing:
    """Tests for username/@mention scrubbing."""

    def test_simple_username(self):
        """Test simple @mention removal."""
        text = "Thanks @support for helping me!"
        result = scrub_username(text)
        assert "@support" not in result
        assert "[USER]" in result

    def test_username_with_underscore(self):
        """Test @mention with underscore."""
        text = "Contact @groww_support for assistance"
        result = scrub_username(text)
        assert "@groww_support" not in result
        assert "[USER]" in result

    def test_multiple_usernames(self):
        """Test multiple @mentions."""
        text = "Thanks @admin and @support for help"
        result = scrub_username(text)
        assert "@admin" not in result
        assert "@support" not in result
        assert result.count("[USER]") == 2

    def test_no_username(self):
        """Test text without username."""
        text = "This has no username"
        result = scrub_username(text)
        assert result == text

    def test_empty_text(self):
        """Test empty text handling."""
        assert scrub_username("") == ""
        assert scrub_username(None) == None


class TestAllPiiScrubbing:
    """Tests for complete PII scrubbing."""

    def test_all_pii_types(self):
        """Test removal of all PII types together."""
        text = "My email is test@example.com and phone is 9876543210. Contact @admin"
        result = scrub_all_pii(text)
        assert "test@example.com" not in result
        assert "9876543210" not in result
        assert "@admin" not in result
        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[USER]" in result

    def test_complex_text_with_pii(self):
        """Test complex text with multiple PII instances."""
        text = (
            "Please contact john@example.com or call +919876543210. "
            "You can also reach @support_team or email admin@company.com"
        )
        result = scrub_all_pii(text)
        assert "john@example.com" not in result
        assert "admin@company.com" not in result
        assert "+919876543210" not in result
        assert "@support_team" not in result
        assert result.count("[EMAIL]") == 2
        assert result.count("[PHONE]") == 1
        assert result.count("[USER]") == 1

    def test_no_pii_unchanged(self):
        """Test that text without PII remains largely unchanged."""
        text = "This is a great app for investing in stocks and mutual funds!"
        result = scrub_all_pii(text)
        assert "great app for investing" in result
        assert "[EMAIL]" not in result
        assert "[PHONE]" not in result
        assert "[USER]" not in result

    def test_empty_text(self):
        """Test empty text handling."""
        assert scrub_all_pii("") == ""
        assert scrub_all_pii(None) == None

    def test_review_like_text(self):
        """Test realistic review text."""
        text = (
            "Terrible experience! My account verification has been pending for 2 weeks. "
            "I tried emailing support@groww.in and calling 9876543210 but no response. "
            "Even @groww on Twitter is not helping!"
        )
        result = scrub_all_pii(text)
        assert "support@groww.in" not in result
        assert "9876543210" not in result
        assert "@groww" not in result
        assert "Terrible experience" in result
        assert "account verification" in result
