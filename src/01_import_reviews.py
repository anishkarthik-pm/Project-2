"""Step 1: Import and clean reviews from Google Play Store."""

import argparse
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from google_play_scraper import reviews_all, Sort
from tqdm import tqdm

from src.config import (
    APP_ID,
    APP_NAME,
    REVIEW_LANG,
    REVIEW_COUNTRY,
    RAW_DATA_DIR,
    setup_logging,
)
from src.utils import (
    scrub_all_pii,
    ensure_dir_exists,
    log_pipeline_step,
    Timer,
)

# Setup logging
logger = setup_logging(name=__name__)


# ============================================================================
# FETCH REVIEWS FROM PLAY STORE
# ============================================================================

def fetch_reviews(
    app_id: str,
    lang: str = 'en',
    country: str = 'in',
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Fetch all reviews from Google Play Store with retry logic.

    Args:
        app_id: Google Play app ID
        lang: Language code
        country: Country code
        max_retries: Number of retry attempts

    Returns:
        List of review dictionaries

    Raises:
        Exception: If all retry attempts fail
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching reviews from Google Play Store (attempt {attempt}/{max_retries})...")
            logger.info(f"App ID: {app_id}, Language: {lang}, Country: {country}")

            # Fetch all reviews with NEWEST sort
            with Timer() as t:
                reviews = reviews_all(
                    app_id,
                    sleep_milliseconds=0,
                    lang=lang,
                    country=country,
                    sort=Sort.NEWEST
                )

            logger.info(f"Fetched {len(reviews)} reviews in {t.duration:.2f}s")
            return reviews

        except Exception as e:
            logger.error(f"Attempt {attempt} failed: {str(e)}")

            if attempt < max_retries:
                # Exponential backoff: 2s, 4s, 8s
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("All retry attempts failed")
                raise Exception(f"Failed to fetch reviews after {max_retries} attempts: {str(e)}")


# ============================================================================
# TEXT CLEANING FUNCTIONS
# ============================================================================

def remove_html_tags(text: str) -> str:
    """
    Remove HTML tags from text.

    Args:
        text: Input text with potential HTML

    Returns:
        Text without HTML tags
    """
    if not text:
        return text
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text


def remove_urls(text: str) -> str:
    """
    Remove URLs from text.

    Args:
        text: Input text with potential URLs

    Returns:
        Text without URLs
    """
    if not text:
        return text
    # Remove http/https URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    # Remove www URLs
    text = re.sub(r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),])+', '', text)
    return text


def remove_emojis(text: str) -> str:
    """
    Remove emojis while keeping basic punctuation.

    Args:
        text: Input text with potential emojis

    Returns:
        Text without emojis
    """
    if not text:
        return text

    # Emoji pattern (covers most emojis)
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002500-\U00002BEF"  # chinese char
        u"\U00002702-\U000027B0"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"  # dingbats
        u"\u3030"
        "]+",
        flags=re.UNICODE
    )

    return emoji_pattern.sub(r'', text)


def clean_whitespace(text: str) -> str:
    """
    Clean excessive whitespace from text.

    Args:
        text: Input text

    Returns:
        Text with normalized whitespace
    """
    if not text:
        return text

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def clean_review_text(text: str) -> str:
    """
    Apply full cleaning pipeline to review text.

    Steps:
    1. Remove HTML tags
    2. Remove URLs
    3. Remove emojis
    4. Clean whitespace
    5. Remove PII

    Args:
        text: Raw review text

    Returns:
        Cleaned review text
    """
    if not text:
        return text

    text = remove_html_tags(text)
    text = remove_urls(text)
    text = remove_emojis(text)
    text = clean_whitespace(text)
    text = scrub_all_pii(text)

    return text


# ============================================================================
# DATA PROCESSING
# ============================================================================

def process_reviews(
    reviews: List[Dict[str, Any]],
    weeks_back: int
) -> pd.DataFrame:
    """
    Process raw reviews into cleaned DataFrame.

    Args:
        reviews: List of review dictionaries from google_play_scraper
        weeks_back: Number of weeks to look back from today

    Returns:
        Cleaned DataFrame with filtered reviews
    """
    logger.info("Processing reviews...")

    # Convert to DataFrame
    df = pd.DataFrame(reviews)

    initial_count = len(df)
    logger.info(f"Initial review count: {initial_count}")

    # Extract required columns
    if 'reviewId' in df.columns:
        df = df.rename(columns={'reviewId': 'review_id'})
    if 'content' in df.columns:
        df = df.rename(columns={'content': 'text'})
    if 'score' in df.columns:
        df = df.rename(columns={'score': 'rating'})
    if 'at' in df.columns:
        df = df.rename(columns={'at': 'date'})

    # Keep only required columns
    required_cols = ['review_id', 'text', 'rating', 'date']
    df = df[required_cols]

    # Convert date to datetime
    if df['date'].dtype == 'object':
        df['date'] = pd.to_datetime(df['date'])

    # Remove reviews with empty content
    df = df[df['text'].notna()]
    df = df[df['text'].str.strip() != '']
    logger.info(f"After removing empty reviews: {len(df)}")

    # Filter by date range
    today = datetime.now()
    start_date = today - timedelta(weeks=weeks_back)
    end_date = today - timedelta(days=7)  # Exclude last 7 days

    df = df[df['date'] >= start_date]
    df = df[df['date'] <= end_date]

    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"After date filtering: {len(df)}")

    # Clean review text with progress bar
    logger.info("Cleaning review text...")
    tqdm.pandas(desc="Cleaning reviews")
    df['text'] = df['text'].progress_apply(clean_review_text)

    # Remove any reviews that became empty after cleaning
    df = df[df['text'].str.strip() != '']
    logger.info(f"After cleaning: {len(df)}")

    # Sort by date (newest first)
    df = df.sort_values('date', ascending=False)

    # Reset index
    df = df.reset_index(drop=True)

    return df


# ============================================================================
# OUTPUT
# ============================================================================

def save_reviews(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save reviews DataFrame to CSV.

    Args:
        df: Reviews DataFrame
        output_path: Path to output CSV file
    """
    ensure_dir_exists(output_path.parent)

    df.to_csv(output_path, index=False, encoding='utf-8')

    logger.info(f"Saved {len(df)} reviews to: {output_path}")


def print_summary(df: pd.DataFrame) -> None:
    """
    Print summary statistics of imported reviews.

    Args:
        df: Reviews DataFrame
    """
    logger.info("=" * 60)
    logger.info("IMPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total reviews: {len(df)}")
    logger.info(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    logger.info(f"Rating distribution:")

    rating_counts = df['rating'].value_counts().sort_index(ascending=False)
    for rating, count in rating_counts.items():
        percentage = (count / len(df)) * 100
        logger.info(f"  {rating}⭐: {count} ({percentage:.1f}%)")

    logger.info(f"Average rating: {df['rating'].mean():.2f}")
    logger.info("=" * 60)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Import and clean Groww app reviews from Google Play Store'
    )
    parser.add_argument(
        '--weeks-back',
        type=int,
        default=12,
        help='Number of weeks to look back (default: 12)'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"Starting Review Import for {APP_NAME}")
    logger.info("=" * 60)

    with Timer() as total_timer:
        try:
            # Step 1: Fetch reviews
            log_pipeline_step(logger, "Fetch Reviews", "START")
            with Timer() as t:
                reviews = fetch_reviews(
                    app_id=APP_ID,
                    lang=REVIEW_LANG,
                    country=REVIEW_COUNTRY
                )
            log_pipeline_step(
                logger, "Fetch Reviews", "SUCCESS",
                duration=t.duration,
                metadata={"count": len(reviews)}
            )

            if not reviews:
                logger.warning("No reviews found!")
                return

            # Step 2: Process reviews
            log_pipeline_step(logger, "Process Reviews", "START")
            with Timer() as t:
                df = process_reviews(reviews, weeks_back=args.weeks_back)
            log_pipeline_step(
                logger, "Process Reviews", "SUCCESS",
                duration=t.duration,
                metadata={"final_count": len(df)}
            )

            if df.empty:
                logger.warning(f"No reviews found in the last {args.weeks_back} weeks!")
                return

            # Step 3: Save to CSV
            today_str = datetime.now().strftime("%Y-%m-%d")
            output_path = RAW_DATA_DIR / f"reviews_{today_str}.csv"

            log_pipeline_step(logger, "Save Reviews", "START")
            with Timer() as t:
                save_reviews(df, output_path)
            log_pipeline_step(
                logger, "Save Reviews", "SUCCESS",
                duration=t.duration,
                metadata={"path": str(output_path)}
            )

            # Print summary
            print_summary(df)

        except Exception as e:
            logger.error(f"Import failed: {str(e)}", exc_info=True)
            log_pipeline_step(logger, "Import Reviews", "FAILED")
            raise

    logger.info(f"Total execution time: {total_timer.duration:.2f}s")
    logger.info("Review import completed successfully!")


if __name__ == "__main__":
    main()
