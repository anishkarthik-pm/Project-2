"""Tests for PII scrubbing functionality."""

import pytest
from src.utils import scrub_pii


def test_scrub_email():
    """Test email address removal."""
    text = "Contact me at john.doe@example.com for help"
    result = scrub_pii(text)
    assert "john.doe@example.com" not in result
    assert "[EMAIL]" in result


def test_scrub_indian_phone():
    """Test Indian phone number removal."""
    test_cases = [
        "Call me at 9876543210",
        "My number is +919876543210",
        "Reach out at +91-9876543210",
        "Contact: 09876543210",
    ]
    for text in test_cases:
        result = scrub_pii(text)
        assert "[PHONE]" in result
        assert "9876543210" not in result


def test_scrub_username():
    """Test @mention username removal."""
    text = "Thanks @groww_support for helping me!"
    result = scrub_pii(text)
    assert "@groww_support" not in result
    assert "[USER]" in result


def test_scrub_multiple_pii():
    """Test removal of multiple PII types."""
    text = "My email is test@example.com and phone is 9876543210. Contact @admin"
    result = scrub_pii(text)
    assert "test@example.com" not in result
    assert "9876543210" not in result
    assert "@admin" not in result
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "[USER]" in result


def test_scrub_empty_text():
    """Test handling of empty text."""
    assert scrub_pii("") == ""
    assert scrub_pii(None) == None


def test_no_pii_unchanged():
    """Test that text without PII remains largely unchanged."""
    text = "This is a great app for investing!"
    result = scrub_pii(text)
    assert "great app for investing" in result
