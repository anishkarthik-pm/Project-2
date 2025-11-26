"""Configuration management for the review analyzer."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
NOTES_DIR = OUTPUTS_DIR / "notes"
EMAILS_DIR = OUTPUTS_DIR / "emails"
LOGS_DIR = PROJECT_ROOT / "logs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# App configuration
APP_ID = os.getenv("APP_ID", "com.nextbillion.groww")
APP_NAME = os.getenv("APP_NAME", "Groww")

# Review fetching
REVIEW_LANG = os.getenv("REVIEW_LANG", "en")
REVIEW_COUNTRY = os.getenv("REVIEW_COUNTRY", "in")
REVIEW_COUNT = int(os.getenv("REVIEW_COUNT", "500"))

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")
EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "Weekly Groww App Review Pulse")

# Report configuration
WEEKS_LOOKBACK = int(os.getenv("WEEKS_LOOKBACK", "10"))
MAX_THEMES = int(os.getenv("MAX_THEMES", "5"))
TOP_THEMES_FOR_REPORT = int(os.getenv("TOP_THEMES_FOR_REPORT", "3"))
WEEKLY_NOTE_MAX_WORDS = int(os.getenv("WEEKLY_NOTE_MAX_WORDS", "250"))
EMAIL_DRAFT_MAX_WORDS = int(os.getenv("EMAIL_DRAFT_MAX_WORDS", "350"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
