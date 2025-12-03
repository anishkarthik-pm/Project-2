"""
Unit tests for review type classifier.
"""

import pytest
from src.models.review_type_classifier import (
    ReviewTypeClassifier,
    get_review_type_distribution,
    REVIEW_TYPES
)


def test_review_types_defined():
    """Test that review types are properly defined."""
    assert len(REVIEW_TYPES) == 10
    assert "Bug Report" in REVIEW_TYPES
    assert "Feature Request" in REVIEW_TYPES
    assert "Positive Feedback" in REVIEW_TYPES


def test_get_review_type_distribution():
    """Test review type distribution calculation."""
    review_types = [
        "Bug Report",
        "Bug Report",
        "Feature Request",
        "Positive Feedback"
    ]

    distribution = get_review_type_distribution(review_types)

    assert distribution["Bug Report"] == 2
    assert distribution["Feature Request"] == 1
    assert distribution["Positive Feedback"] == 1
    assert distribution["Negative Feedback"] == 0


@pytest.mark.skipif(
    not pytest.config.getoption("--run-integration"),
    reason="Integration test - requires API key"
)
def test_classifier_single_review():
    """Integration test for classifying a single review."""
    import os
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")

    classifier = ReviewTypeClassifier(api_key=api_key)

    # Test positive feedback
    result = classifier.classify_single("Great app! Love using it.")
    assert result in REVIEW_TYPES

    # Test bug report
    result = classifier.classify_single("App crashes when I try to login")
    assert result in REVIEW_TYPES


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests"
    )
