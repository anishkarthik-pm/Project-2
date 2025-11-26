"""Utility functions for PII scrubbing and helpers."""

import re


def scrub_pii(text: str) -> str:
    """
    Remove personally identifiable information from text.

    Removes:
    - Email addresses
    - Phone numbers (Indian and international formats)
    - Potential usernames (@mentions)

    Args:
        text: Input text potentially containing PII

    Returns:
        Scrubbed text with PII removed
    """
    if not text:
        return text

    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)

    # Remove phone numbers (Indian: 10 digits, with optional +91/0)
    text = re.sub(r'\+?91[-.\s]?\d{10}\b', '[PHONE]', text)
    text = re.sub(r'\b0?\d{10}\b', '[PHONE]', text)

    # Remove international phone numbers
    text = re.sub(r'\+\d{1,3}[-.\s]?\d{6,14}\b', '[PHONE]', text)

    # Remove @mentions (potential usernames)
    text = re.sub(r'@\w+', '[USER]', text)

    return text


def count_words(text: str) -> int:
    """
    Count words in text.

    Args:
        text: Input text

    Returns:
        Word count
    """
    return len(text.split())


def truncate_to_word_limit(text: str, max_words: int) -> str:
    """
    Truncate text to a maximum word count.

    Args:
        text: Input text
        max_words: Maximum number of words

    Returns:
        Truncated text
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    return ' '.join(words[:max_words]) + '...'
