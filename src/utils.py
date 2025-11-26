"""Utility functions for the review analyzer pipeline."""

import re
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import pandas as pd


# ============================================================================
# PII SCRUBBING FUNCTIONS
# ============================================================================

def scrub_email(text: str) -> str:
    """
    Remove email addresses from text.

    Args:
        text: Input text potentially containing email addresses

    Returns:
        Text with emails replaced by [EMAIL]

    Example:
        >>> scrub_email("Contact me at john@example.com")
        'Contact me at [EMAIL]'
    """
    if not text:
        return text
    return re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL]',
        text
    )


def scrub_phone(text: str) -> str:
    """
    Remove phone numbers from text (including Indian +91 format).

    Handles:
    - Indian mobile: 9876543210, +919876543210, +91-9876543210
    - With leading zero: 09876543210
    - International: +1-234-567-8900

    Args:
        text: Input text potentially containing phone numbers

    Returns:
        Text with phone numbers replaced by [PHONE]

    Example:
        >>> scrub_phone("Call me at +919876543210")
        'Call me at [PHONE]'
    """
    if not text:
        return text

    # International phone numbers with formatting (e.g., +1-234-567-8900, +44 20 1234 5678)
    text = re.sub(r'\+\d{1,3}[-.\s]?[\d\-.\s]{6,20}', '[PHONE]', text)

    # Indian phone numbers with +91 prefix
    text = re.sub(r'\+91[-.\s]?\d{10}\b', '[PHONE]', text)

    # Indian phone numbers (10 digits, optional leading 0)
    text = re.sub(r'\b0?\d{10}\b', '[PHONE]', text)

    return text


def scrub_username(text: str) -> str:
    """
    Remove @mentions and potential usernames from text.

    Args:
        text: Input text potentially containing @mentions

    Returns:
        Text with usernames replaced by [USER]

    Example:
        >>> scrub_username("Thanks @support_team for helping!")
        'Thanks [USER] for helping!'
    """
    if not text:
        return text
    return re.sub(r'@\w+', '[USER]', text)


def scrub_all_pii(text: str) -> str:
    """
    Remove all personally identifiable information from text.

    Runs all PII scrubbers in sequence:
    - Email addresses
    - Phone numbers
    - Usernames/@mentions

    Args:
        text: Input text potentially containing PII

    Returns:
        Text with all PII removed

    Example:
        >>> scrub_all_pii("Email: test@example.com, Phone: 9876543210, User: @admin")
        'Email: [EMAIL], Phone: [PHONE], User: [USER]'
    """
    if not text:
        return text

    text = scrub_email(text)
    text = scrub_phone(text)
    text = scrub_username(text)

    return text


# ============================================================================
# DATE HELPER FUNCTIONS
# ============================================================================

def get_week_range(weeks_ago: int = 0) -> Tuple[datetime, datetime]:
    """
    Get start and end dates for a week (Monday to Sunday).

    Args:
        weeks_ago: Number of weeks in the past (0 = current week)

    Returns:
        Tuple of (start_date, end_date) as datetime objects

    Example:
        >>> start, end = get_week_range(0)  # Current week
        >>> start, end = get_week_range(1)  # Last week
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get the Monday of the current week
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)

    # Calculate the target Monday
    target_monday = current_monday - timedelta(weeks=weeks_ago)

    # Sunday is 6 days after Monday
    target_sunday = target_monday + timedelta(days=6)

    # Set time to end of day for Sunday
    target_sunday = target_sunday.replace(hour=23, minute=59, second=59)

    return target_monday, target_sunday


def format_week_label(start_date: datetime, end_date: datetime) -> str:
    """
    Format week date range as a readable label.

    Args:
        start_date: Week start date
        end_date: Week end date

    Returns:
        Formatted string like "Nov 18-24, 2024"

    Example:
        >>> start = datetime(2024, 11, 18)
        >>> end = datetime(2024, 11, 24)
        >>> format_week_label(start, end)
        'Nov 18-24, 2024'
    """
    month_name = start_date.strftime("%b")
    start_day = start_date.day
    end_day = end_date.day
    year = start_date.year

    # Handle case where week spans two months
    if start_date.month != end_date.month:
        return f"{start_date.strftime('%b %d')}-{end_date.strftime('%b %d, %Y')}"

    return f"{month_name} {start_day}-{end_day}, {year}"


# ============================================================================
# LOGGING HELPER FUNCTIONS
# ============================================================================

def setup_logger(name: str, log_file: Optional[Path] = None) -> logging.Logger:
    """
    Configure a logger with console and optional file handlers.

    Args:
        name: Logger name (typically __name__)
        log_file: Optional path to log file

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger(__name__, Path("logs/app.log"))
        >>> logger.info("This is a test message")
    """
    from src.config import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT, LOGS_DIR

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(getattr(logging, LOG_LEVEL))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_pipeline_step(
    logger: logging.Logger,
    step_name: str,
    status: str,
    duration: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a pipeline step with structured information.

    Args:
        logger: Logger instance
        step_name: Name of the pipeline step
        status: Status (START, SUCCESS, FAILED)
        duration: Optional duration in seconds
        metadata: Optional dictionary of additional data

    Example:
        >>> logger = setup_logger(__name__)
        >>> log_pipeline_step(logger, "Import Reviews", "START")
        >>> # ... do work ...
        >>> log_pipeline_step(logger, "Import Reviews", "SUCCESS", duration=5.2,
        ...                   metadata={"reviews_count": 150})
    """
    msg_parts = [f"[{step_name}]", status]

    if duration is not None:
        msg_parts.append(f"({duration:.2f}s)")

    if metadata:
        metadata_str = ", ".join(f"{k}={v}" for k, v in metadata.items())
        msg_parts.append(f"| {metadata_str}")

    message = " ".join(msg_parts)

    if status == "START":
        logger.info(message)
    elif status == "SUCCESS":
        logger.info(message)
    elif status == "FAILED":
        logger.error(message)
    else:
        logger.info(message)


# ============================================================================
# FILE HELPER FUNCTIONS
# ============================================================================

def ensure_dir_exists(path: Path) -> None:
    """
    Create directory if it doesn't exist.

    Args:
        path: Path to directory

    Example:
        >>> ensure_dir_exists(Path("data/raw"))
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)


def save_json(data: Dict[str, Any], path: Path) -> None:
    """
    Save dictionary as formatted JSON file.

    Args:
        data: Dictionary to save
        path: Path to output JSON file

    Raises:
        IOError: If file cannot be written

    Example:
        >>> data = {"reviews": 150, "date": "2024-11-18"}
        >>> save_json(data, Path("output/data.json"))
    """
    try:
        path = Path(path)
        ensure_dir_exists(path.parent)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        raise IOError(f"Failed to save JSON to {path}: {str(e)}")


def load_json(path: Path) -> Dict[str, Any]:
    """
    Load JSON file to dictionary.

    Args:
        path: Path to JSON file

    Returns:
        Loaded dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON

    Example:
        >>> data = load_json(Path("output/data.json"))
        >>> print(data["reviews"])
    """
    try:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in {path}: {str(e)}", e.doc, e.pos)


def save_markdown(content: str, path: Path) -> None:
    """
    Save formatted Markdown content to file.

    Args:
        content: Markdown content string
        path: Path to output MD file

    Raises:
        IOError: If file cannot be written

    Example:
        >>> content = "# Weekly Report\\n\\n**Date:** Nov 18-24\\n"
        >>> save_markdown(content, Path("output/report.md"))
    """
    try:
        path = Path(path)
        ensure_dir_exists(path.parent)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    except Exception as e:
        raise IOError(f"Failed to save Markdown to {path}: {str(e)}")


# ============================================================================
# DATA VALIDATION FUNCTIONS
# ============================================================================

def validate_review_data(df: pd.DataFrame) -> Tuple[bool, list[str]]:
    """
    Validate that review DataFrame has required columns.

    Required columns:
    - content (or reviewText)
    - score (or rating)
    - at (or date)

    Args:
        df: DataFrame to validate

    Returns:
        Tuple of (is_valid, list_of_missing_columns)

    Example:
        >>> df = pd.DataFrame({"content": ["Great app"], "score": [5]})
        >>> is_valid, missing = validate_review_data(df)
        >>> if not is_valid:
        ...     print(f"Missing columns: {missing}")
    """
    # Possible column names for each required field
    content_cols = ['content', 'reviewText', 'review_text', 'text']
    score_cols = ['score', 'rating', 'stars']
    date_cols = ['at', 'date', 'review_date', 'created_at']

    missing = []

    # Check if at least one variant exists for each required field
    if not any(col in df.columns for col in content_cols):
        missing.append('content')

    if not any(col in df.columns for col in score_cols):
        missing.append('score/rating')

    if not any(col in df.columns for col in date_cols):
        missing.append('date')

    return (len(missing) == 0, missing)


def count_words(text: str) -> int:
    """
    Count words in text accurately.

    Handles:
    - Multiple spaces
    - Newlines
    - Punctuation
    - Empty strings

    Args:
        text: Input text

    Returns:
        Word count

    Example:
        >>> count_words("Hello world!  How are you?")
        5
        >>> count_words("")
        0
    """
    if not text or not text.strip():
        return 0

    # Split on whitespace and filter empty strings
    words = [word for word in text.split() if word.strip()]
    return len(words)


def truncate_to_word_limit(text: str, limit: int) -> str:
    """
    Smart truncation to word limit with ellipsis.

    Features:
    - Respects word boundaries
    - Adds ellipsis only when truncated
    - Handles edge cases (empty text, limit=0)

    Args:
        text: Input text
        limit: Maximum number of words

    Returns:
        Truncated text

    Example:
        >>> truncate_to_word_limit("This is a very long sentence", 4)
        'This is a very...'
        >>> truncate_to_word_limit("Short text", 100)
        'Short text'
    """
    if not text or limit <= 0:
        return text if text else ""

    words = text.split()

    if len(words) <= limit:
        return text

    # Truncate and add ellipsis
    truncated = ' '.join(words[:limit])

    # Add ellipsis if we're not at end of sentence
    if not truncated.endswith(('.', '!', '?')):
        truncated += '...'

    return truncated


# ============================================================================
# TIMING CONTEXT MANAGER
# ============================================================================

class Timer:
    """
    Context manager for timing code execution.

    Example:
        >>> with Timer() as t:
        ...     # Do some work
        ...     time.sleep(1)
        >>> print(f"Took {t.duration:.2f} seconds")
    """

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        return False
