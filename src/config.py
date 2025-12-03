"""Configuration management for the review analyzer."""

import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# PROJECT PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
NOTES_DIR = OUTPUTS_DIR / "notes"
EMAILS_DIR = OUTPUTS_DIR / "emails"
LOGS_DIR = PROJECT_ROOT / "logs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# ============================================================================
# APP CONFIGURATION
# ============================================================================
# Support for generic Play Store app (defaults to Groww)
APP_ID = os.getenv("APP_PACKAGE_NAME", "com.nextbillion.groww")
APP_NAME = os.getenv("APP_NAME", "Groww")

# Review fetching
REVIEW_LANG = os.getenv("REVIEW_LANG", "en")
REVIEW_COUNTRY = os.getenv("REVIEW_COUNTRY", "in")
REVIEW_COUNT = 500

# ============================================================================
# REVIEW TIME WINDOW
# ============================================================================
WEEKS_LOOKBACK_MIN = 8
WEEKS_LOOKBACK_MAX = 12
WEEKS_LOOKBACK = int(os.getenv("WEEKS_LOOKBACK", "10"))  # Default to 10 weeks

# ============================================================================
# THEME CONFIGURATION
# ============================================================================
MAX_THEMES = 5
TOP_THEMES_FOR_REPORT = 3

# Theme taxonomy with descriptions
THEME_TAXONOMY = {
    "Onboarding": "Account creation, sign-up flow, first-time user experience",
    "KYC/Account": "KYC verification, document upload, account issues",
    "Trading/Orders": "Buying/selling stocks, order execution, prices, delays",
    "Withdrawals/Payments": "Withdrawal issues, payment failures, bank linking",
    "App UX/Performance": "UI bugs, app crashes, speed, navigation"
}

# ============================================================================
# WORD LIMITS
# ============================================================================
WEEKLY_NOTE_MAX_WORDS = 250
EMAIL_DRAFT_MAX_WORDS = 350

# ============================================================================
# GEMINI API CONFIGURATION
# ============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model names
GEMINI_FLASH_MODEL = "gemini-1.5-flash"  # For classification
GEMINI_PRO_MODEL = "gemini-1.5-pro"      # For summarization

# API settings
GEMINI_TEMPERATURE = 0.3
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY = 2  # seconds

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",") if os.getenv("EMAIL_TO") else []
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SUBJECT = "Weekly Groww App Review Pulse"

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log file paths
PIPELINE_LOG_FILE = LOGS_DIR / "pipeline.log"
EMAIL_LOG_FILE = LOGS_DIR / "email_sent.log"

# ============================================================================
# FILE PATH HELPER FUNCTIONS
# ============================================================================

def get_raw_data_path(week_date: datetime) -> Path:
    """
    Get path for raw review data CSV file.

    Args:
        week_date: Date representing the week (typically Monday)

    Returns:
        Path to raw data CSV file

    Example:
        >>> get_raw_data_path(datetime(2024, 1, 15))
        Path('.../data/raw/reviews_2024-01-15.csv')
    """
    date_str = week_date.strftime("%Y-%m-%d")
    return RAW_DATA_DIR / f"reviews_{date_str}.csv"


def get_processed_data_path(week_date: datetime) -> Path:
    """
    Get path for processed review data CSV file (with themes).

    Args:
        week_date: Date representing the week (typically Monday)

    Returns:
        Path to processed data CSV file

    Example:
        >>> get_processed_data_path(datetime(2024, 1, 15))
        Path('.../data/processed/reviews_classified_2024-01-15.csv')
    """
    date_str = week_date.strftime("%Y-%m-%d")
    return PROCESSED_DATA_DIR / f"reviews_classified_{date_str}.csv"


def get_output_note_path(week_date: datetime, format: str = "json") -> Path:
    """
    Get path for weekly pulse note output file.

    Args:
        week_date: Date representing the week (typically Monday)
        format: Output format ('json' or 'md')

    Returns:
        Path to note output file

    Example:
        >>> get_output_note_path(datetime(2024, 1, 15), "json")
        Path('.../outputs/notes/weekly_pulse_2024-01-15.json')
    """
    date_str = week_date.strftime("%Y-%m-%d")
    return NOTES_DIR / f"weekly_pulse_{date_str}.{format}"


def get_output_email_path(week_date: datetime) -> Path:
    """
    Get path for email draft output file.

    Args:
        week_date: Date representing the week (typically Monday)

    Returns:
        Path to email draft text file

    Example:
        >>> get_output_email_path(datetime(2024, 1, 15))
        Path('.../outputs/emails/email_draft_2024-01-15.txt')
    """
    date_str = week_date.strftime("%Y-%m-%d")
    return EMAILS_DIR / f"email_draft_{date_str}.txt"


# ============================================================================
# LOGGING SETUP FUNCTION
# ============================================================================

def setup_logging(log_file: Path = None, name: str = None) -> logging.Logger:
    """
    Configure logging with console and file handlers.

    Args:
        log_file: Optional specific log file path (defaults to PIPELINE_LOG_FILE)
        name: Logger name (defaults to root logger)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file is None:
        log_file = PIPELINE_LOG_FILE

    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def setup_email_logging() -> logging.Logger:
    """
    Configure logging specifically for email delivery tracking.

    Returns:
        Configured email logger instance
    """
    return setup_logging(log_file=EMAIL_LOG_FILE, name="email_sender")


# ============================================================================
# VALIDATION
# ============================================================================

def validate_config() -> tuple[bool, list[str]]:
    """
    Validate that required configuration variables are set.

    Returns:
        Tuple of (is_valid, list_of_missing_vars)
    """
    required_vars = {
        'GEMINI_API_KEY': GEMINI_API_KEY,
        'EMAIL_FROM': EMAIL_FROM,
        'EMAIL_TO': EMAIL_TO,
        'EMAIL_PASSWORD': EMAIL_PASSWORD,
    }

    missing = []
    for key, value in required_vars.items():
        if not value or (isinstance(value, list) and len(value) == 0):
            missing.append(key)

    return (len(missing) == 0, missing)


# ============================================================================
# DIRECTORY INITIALIZATION
# ============================================================================

def ensure_directories():
    """Create all required directories if they don't exist."""
    directories = [
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        NOTES_DIR,
        EMAILS_DIR,
        LOGS_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# Initialize directories on import
ensure_directories()
