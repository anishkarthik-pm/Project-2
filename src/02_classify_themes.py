"""Step 2: Classify reviews into themes using Gemini API."""

import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import google.generativeai as genai
from tqdm import tqdm

from src.config import (
    GEMINI_API_KEY,
    GEMINI_FLASH_MODEL,
    THEME_TAXONOMY,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROMPTS_DIR,
    setup_logging,
)
from src.utils import (
    ensure_dir_exists,
    log_pipeline_step,
    Timer,
)

# Setup logging
logger = setup_logging(name=__name__)

# Constants
BATCH_SIZE = 10
TEMPERATURE = 0.1
MAX_RETRIES = 3
DEFAULT_THEME = "App UX/Performance"


# ============================================================================
# GEMINI API SETUP
# ============================================================================

def setup_gemini() -> genai.GenerativeModel:
    """
    Configure Gemini API and return model instance.

    Returns:
        Configured GenerativeModel instance

    Raises:
        ValueError: If API key is not set
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_FLASH_MODEL,
        generation_config={
            "temperature": TEMPERATURE,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
    )

    logger.info(f"Initialized Gemini model: {GEMINI_FLASH_MODEL}")
    logger.info(f"Temperature: {TEMPERATURE}")

    return model


def load_classification_prompt() -> str:
    """
    Load classification prompt template from file.

    Returns:
        Prompt template string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / "classify_theme.txt"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read()

    logger.info(f"Loaded classification prompt from: {prompt_path}")
    return prompt


# ============================================================================
# INPUT HANDLING
# ============================================================================

def get_latest_raw_file() -> Path:
    """
    Get the most recent CSV file from data/raw directory.

    Returns:
        Path to latest CSV file

    Raises:
        FileNotFoundError: If no CSV files found
    """
    # Get all review CSV files, excluding sample files
    csv_files = sorted(RAW_DATA_DIR.glob("reviews_20*.csv"))

    # If no date-stamped files, fall back to any reviews_*.csv
    if not csv_files:
        csv_files = [f for f in RAW_DATA_DIR.glob("reviews_*.csv") if "sample" not in f.name.lower()]
        csv_files.sort()

    if not csv_files:
        raise FileNotFoundError(f"No review CSV files found in {RAW_DATA_DIR}")

    latest_file = csv_files[-1]
    logger.info(f"Found latest raw file: {latest_file.name}")

    return latest_file


def load_reviews(file_path: Path) -> pd.DataFrame:
    """
    Load reviews from CSV file.

    Args:
        file_path: Path to CSV file

    Returns:
        DataFrame with reviews

    Raises:
        FileNotFoundError: If file doesn't exist
        pd.errors.EmptyDataError: If file is empty
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    df = pd.read_csv(file_path)

    logger.info(f"Loaded {len(df)} reviews from: {file_path}")

    # Validate required columns
    required_cols = ['review_id', 'text', 'rating']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    return df


# ============================================================================
# BATCH CLASSIFICATION
# ============================================================================

def build_batch_prompt(
    base_prompt: str,
    reviews: List[Dict[str, Any]]
) -> str:
    """
    Build batch classification prompt for multiple reviews.

    Args:
        base_prompt: Base classification prompt template
        reviews: List of review dictionaries with review_id, text, rating

    Returns:
        Complete batch prompt
    """
    # Build review list
    review_items = []
    for review in reviews:
        review_items.append(
            f"Review ID: {review['review_id']}\n"
            f"Rating: {review['rating']}/5\n"
            f"Text: {review['text']}\n"
        )

    reviews_text = "\n---\n".join(review_items)

    # Modify base prompt for batch processing
    batch_prompt = f"""{base_prompt}

You will classify MULTIPLE reviews. For each review, respond with a JSON object containing:
- review_id: The review ID
- theme: One of the theme names (e.g., "Onboarding", "KYC/Account", etc.)
- reason: Brief 1-sentence explanation

Return a JSON array with all classifications.

Reviews to classify:

{reviews_text}

Respond with ONLY a JSON array like:
[
  {{"review_id": "abc", "theme": "Trading/Orders", "reason": "User complaining about order execution delay"}},
  {{"review_id": "xyz", "theme": "KYC/Account", "reason": "User having KYC verification issues"}}
]
"""

    return batch_prompt


def parse_classification_response(response_text: str) -> List[Dict[str, str]]:
    """
    Parse JSON response from Gemini API.

    Args:
        response_text: Raw response text from API

    Returns:
        List of classification dictionaries

    Raises:
        json.JSONDecodeError: If response is not valid JSON
    """
    # Clean response text
    response_text = response_text.strip()

    # Try to extract JSON array if wrapped in markdown code blocks
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()

    # Parse JSON
    classifications = json.loads(response_text)

    if not isinstance(classifications, list):
        raise ValueError("Expected JSON array, got: " + type(classifications).__name__)

    return classifications


def validate_theme(theme: str) -> str:
    """
    Validate theme against allowed themes.

    Args:
        theme: Theme name to validate

    Returns:
        Validated theme name (or default if invalid)
    """
    valid_themes = list(THEME_TAXONOMY.keys())

    if theme in valid_themes:
        return theme

    # Log invalid theme
    logger.warning(f"Invalid theme '{theme}', using default: {DEFAULT_THEME}")

    return DEFAULT_THEME


def classify_batch(
    model: genai.GenerativeModel,
    base_prompt: str,
    reviews: List[Dict[str, Any]],
    max_retries: int = MAX_RETRIES
) -> List[Dict[str, str]]:
    """
    Classify a batch of reviews with retry logic.

    Args:
        model: Gemini model instance
        base_prompt: Base classification prompt
        reviews: List of reviews to classify
        max_retries: Maximum number of retry attempts

    Returns:
        List of classification results
    """
    for attempt in range(1, max_retries + 1):
        try:
            # Build prompt
            prompt = build_batch_prompt(base_prompt, reviews)

            # Call API
            with Timer() as t:
                response = model.generate_content(prompt)
                response_text = response.text

            logger.debug(f"API call completed in {t.duration:.2f}s")

            # Parse response
            classifications = parse_classification_response(response_text)

            # Validate themes
            for classification in classifications:
                classification['theme'] = validate_theme(classification['theme'])

            # Create mapping for easy lookup
            classification_map = {
                c['review_id']: c for c in classifications
            }

            # Ensure all reviews have classification
            results = []
            for review in reviews:
                review_id = review['review_id']

                if review_id in classification_map:
                    results.append(classification_map[review_id])
                else:
                    # Missing classification
                    logger.warning(f"No classification for review {review_id}, using default")
                    results.append({
                        'review_id': review_id,
                        'theme': DEFAULT_THEME,
                        'reason': 'Classification not returned by API'
                    })

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Attempt {attempt}: JSON parsing error: {str(e)}")
            if attempt < max_retries:
                logger.info(f"Retrying in 2 seconds...")
                time.sleep(2)

        except Exception as e:
            logger.error(f"Attempt {attempt}: API error: {str(e)}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    # All retries failed - return default classifications
    logger.error(f"All {max_retries} attempts failed for batch")
    return [
        {
            'review_id': review['review_id'],
            'theme': DEFAULT_THEME,
            'reason': 'All classification attempts failed'
        }
        for review in reviews
    ]


# ============================================================================
# MAIN CLASSIFICATION PIPELINE
# ============================================================================

def classify_reviews(
    df: pd.DataFrame,
    model: genai.GenerativeModel,
    base_prompt: str
) -> pd.DataFrame:
    """
    Classify all reviews in DataFrame.

    Args:
        df: DataFrame with reviews
        model: Gemini model instance
        base_prompt: Base classification prompt

    Returns:
        DataFrame with theme and classification_reason columns
    """
    logger.info(f"Classifying {len(df)} reviews in batches of {BATCH_SIZE}")

    # Prepare reviews for classification
    reviews = df[['review_id', 'text', 'rating']].to_dict('records')

    # Split into batches
    batches = [
        reviews[i:i + BATCH_SIZE]
        for i in range(0, len(reviews), BATCH_SIZE)
    ]

    logger.info(f"Created {len(batches)} batches")

    # Process batches with progress bar
    all_classifications = []
    api_calls = 0
    total_latency = 0.0

    for batch in tqdm(batches, desc="Classifying batches"):
        with Timer() as t:
            batch_results = classify_batch(model, base_prompt, batch)

        all_classifications.extend(batch_results)
        api_calls += 1
        total_latency += t.duration

    avg_latency = total_latency / api_calls if api_calls > 0 else 0

    logger.info(f"Completed {api_calls} API calls")
    logger.info(f"Average latency: {avg_latency:.2f}s per batch")

    # Convert classifications to DataFrame
    classifications_df = pd.DataFrame(all_classifications)

    # Merge with original DataFrame
    df = df.merge(
        classifications_df[['review_id', 'theme', 'reason']],
        on='review_id',
        how='left'
    )

    # Rename reason column
    df = df.rename(columns={'reason': 'classification_reason'})

    # Fill any missing classifications
    df['theme'] = df['theme'].fillna(DEFAULT_THEME)
    df['classification_reason'] = df['classification_reason'].fillna('Classification failed')

    return df


def print_theme_distribution(df: pd.DataFrame) -> None:
    """
    Print theme distribution statistics.

    Args:
        df: DataFrame with theme column
    """
    logger.info("=" * 60)
    logger.info("THEME DISTRIBUTION")
    logger.info("=" * 60)

    theme_counts = df['theme'].value_counts().sort_values(ascending=False)

    for theme, count in theme_counts.items():
        percentage = (count / len(df)) * 100
        logger.info(f"  {theme}: {count} ({percentage:.1f}%)")

    logger.info("=" * 60)


def print_review_type_distribution(df: pd.DataFrame) -> None:
    """
    Print review type distribution statistics.

    Args:
        df: DataFrame with review_type column
    """
    if 'review_type' not in df.columns:
        logger.warning("No review_type column found")
        return

    logger.info("=" * 60)
    logger.info("REVIEW TYPE DISTRIBUTION")
    logger.info("=" * 60)

    type_counts = df['review_type'].value_counts().sort_values(ascending=False)

    for review_type, count in type_counts.items():
        percentage = (count / len(df)) * 100
        logger.info(f"  {review_type}: {count} ({percentage:.1f}%)")

    logger.info("=" * 60)


# ============================================================================
# OUTPUT
# ============================================================================

def save_classified_reviews(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save classified reviews to CSV.

    Args:
        df: DataFrame with classifications
        output_path: Path to output CSV file
    """
    ensure_dir_exists(output_path.parent)

    df.to_csv(output_path, index=False, encoding='utf-8')

    logger.info(f"Saved {len(df)} classified reviews to: {output_path}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Classify Groww app reviews into themes using Gemini API'
    )
    parser.add_argument(
        '--input',
        type=str,
        help='Path to input CSV file (default: latest from data/raw/)'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Theme Classification")
    logger.info("=" * 60)

    with Timer() as total_timer:
        try:
            # Step 1: Load input file
            log_pipeline_step(logger, "Load Reviews", "START")
            with Timer() as t:
                if args.input:
                    input_path = Path(args.input)
                else:
                    input_path = get_latest_raw_file()

                df = load_reviews(input_path)

            log_pipeline_step(
                logger, "Load Reviews", "SUCCESS",
                duration=t.duration,
                metadata={"count": len(df), "file": input_path.name}
            )

            # Step 2: Setup Gemini
            log_pipeline_step(logger, "Setup Gemini API", "START")
            with Timer() as t:
                model = setup_gemini()
                base_prompt = load_classification_prompt()

            log_pipeline_step(
                logger, "Setup Gemini API", "SUCCESS",
                duration=t.duration
            )

            # Step 3: Classify themes
            log_pipeline_step(logger, "Classify Themes", "START")
            with Timer() as t:
                df = classify_reviews(df, model, base_prompt)

            log_pipeline_step(
                logger, "Classify Themes", "SUCCESS",
                duration=t.duration,
                metadata={"reviews": len(df), "batches": (len(df) + BATCH_SIZE - 1) // BATCH_SIZE}
            )

            # Step 3.5: Classify review types (new feature)
            log_pipeline_step(logger, "Classify Review Types", "START")
            with Timer() as t:
                from src.models.review_type_classifier import ReviewTypeClassifier

                # Initialize review type classifier
                review_type_classifier = ReviewTypeClassifier(
                    api_key=GEMINI_API_KEY,
                    model_name="gemini-2.0-flash",
                    temperature=0.1
                )

                # Prepare reviews for classification
                reviews_list = [{"content": text} for text in df['content'].tolist()]

                # Classify review types
                review_types = review_type_classifier.classify_batch(
                    reviews_list,
                    batch_size=10
                )

                # Add to dataframe
                df['review_type'] = review_types

            log_pipeline_step(
                logger, "Classify Review Types", "SUCCESS",
                duration=t.duration,
                metadata={"reviews": len(df)}
            )

            # Step 4: Save results
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            output_path = PROCESSED_DATA_DIR / f"reviews_classified_{today_str}.csv"

            log_pipeline_step(logger, "Save Results", "START")
            with Timer() as t:
                save_classified_reviews(df, output_path)

            log_pipeline_step(
                logger, "Save Results", "SUCCESS",
                duration=t.duration,
                metadata={"path": str(output_path)}
            )

            # Print summary
            print_theme_distribution(df)
            print_review_type_distribution(df)

        except Exception as e:
            logger.error(f"Classification failed: {str(e)}", exc_info=True)
            log_pipeline_step(logger, "Theme Classification", "FAILED")
            raise

    logger.info(f"Total execution time: {total_timer.duration:.2f}s")
    logger.info("Theme classification completed successfully!")


if __name__ == "__main__":
    main()
