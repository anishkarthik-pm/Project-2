"""Utility functions for PII scrubbing, logging, and helpers."""

import re
import logging
from pathlib import Path
from typing import Optional
from src.config import LOGS_DIR, LOG_LEVEL


def setup_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger with console and file handlers.

    Args:
        name: Logger name
        log_file: Optional log file path

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOGS_DIR / log_file)
        file_handler.setLevel(getattr(logging, LOG_LEVEL))
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)

    return logger


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


def validate_config() -> bool:
    """
    Validate that required configuration variables are set.

    Returns:
        True if configuration is valid, False otherwise
    """
    from src.config import GEMINI_API_KEY, SMTP_USERNAME, SMTP_PASSWORD

    required_vars = {
        'GEMINI_API_KEY': GEMINI_API_KEY,
        'SMTP_USERNAME': SMTP_USERNAME,
        'SMTP_PASSWORD': SMTP_PASSWORD,
    }

    missing = [key for key, value in required_vars.items() if not value]

    if missing:
        logger = setup_logger(__name__)
        logger.error(f"Missing required configuration: {', '.join(missing)}")
        return False

    return True


def count_words(text: str) -> int:
    """
    Count words in text.

    Args:
        text: Input text

    Returns:
        Word count
    """
    return len(text.split())
