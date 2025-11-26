"""Step 3: Generate weekly pulse note from classified reviews."""

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

import pandas as pd
import google.generativeai as genai
from tqdm import tqdm

from src.config import (
    GEMINI_API_KEY,
    GEMINI_PRO_MODEL,
    THEME_TAXONOMY,
    TOP_THEMES_FOR_REPORT,
    WEEKLY_NOTE_MAX_WORDS,
    PROCESSED_DATA_DIR,
    NOTES_DIR,
    PROMPTS_DIR,
    setup_logging,
)
from src.utils import (
    scrub_all_pii,
    count_words,
    format_week_label,
    ensure_dir_exists,
    save_json,
    save_markdown,
    log_pipeline_step,
    Timer,
)

# Setup logging
logger = setup_logging(name=__name__)

# Constants
MAX_COMPRESSION_ATTEMPTS = 3


# ============================================================================
# GEMINI API SETUP
# ============================================================================

def setup_gemini() -> genai.GenerativeModel:
    """
    Configure Gemini Pro API and return model instance.

    Returns:
        Configured GenerativeModel instance
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_PRO_MODEL,
        generation_config={
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
    )

    logger.info(f"Initialized Gemini model: {GEMINI_PRO_MODEL}")
    return model


def load_prompt(prompt_name: str) -> str:
    """
    Load prompt template from file.

    Args:
        prompt_name: Name of prompt file (without .txt extension)

    Returns:
        Prompt template string
    """
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read()

    logger.info(f"Loaded prompt: {prompt_name}")
    return prompt


# ============================================================================
# INPUT HANDLING
# ============================================================================

def get_latest_themed_file() -> Path:
    """
    Get the most recent themed CSV file from data/processed directory.

    Returns:
        Path to latest CSV file
    """
    csv_files = sorted(PROCESSED_DATA_DIR.glob("reviews_themed_*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No themed CSV files found in {PROCESSED_DATA_DIR}")

    latest_file = csv_files[-1]
    logger.info(f"Found latest themed file: {latest_file}")

    return latest_file


def get_last_complete_week() -> Tuple[datetime, datetime]:
    """
    Get start and end dates of last complete week (Monday-Sunday).

    Returns:
        Tuple of (week_start, week_end) datetime objects
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get last Monday
    days_since_monday = today.weekday()
    last_monday = today - timedelta(days=days_since_monday + 7)

    # Get last Sunday (6 days after last Monday)
    last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return last_monday, last_sunday


def load_and_filter_reviews(
    file_path: Path,
    week_start: datetime,
    week_end: datetime
) -> pd.DataFrame:
    """
    Load reviews and filter by week range.

    Args:
        file_path: Path to themed CSV file
        week_start: Week start date
        week_end: Week end date

    Returns:
        Filtered DataFrame
    """
    df = pd.read_csv(file_path)

    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])

    # Filter by date range
    df = df[(df['date'] >= week_start) & (df['date'] <= week_end)]

    logger.info(f"Loaded {len(df)} reviews for week {week_start.date()} to {week_end.date()}")

    return df


# ============================================================================
# THEME SELECTION
# ============================================================================

def select_top_themes(df: pd.DataFrame, top_n: int = TOP_THEMES_FOR_REPORT) -> List[Tuple[str, int]]:
    """
    Select top N themes by review count.

    Args:
        df: DataFrame with theme column
        top_n: Number of top themes to select

    Returns:
        List of (theme_name, count) tuples
    """
    theme_counts = df['theme'].value_counts()

    top_themes = [(theme, int(count)) for theme, count in theme_counts.head(top_n).items()]

    logger.info(f"Selected top {top_n} themes:")
    for theme, count in top_themes:
        logger.info(f"  - {theme}: {count} reviews")

    return top_themes


# ============================================================================
# THEME SUMMARIZATION (MAP)
# ============================================================================

def summarize_theme(
    model: genai.GenerativeModel,
    theme_name: str,
    reviews: List[str],
    prompt_template: str
) -> Dict[str, Any]:
    """
    Summarize reviews for a specific theme using Gemini Pro.

    Args:
        model: Gemini model instance
        theme_name: Name of the theme
        reviews: List of review texts
        prompt_template: Prompt template for summarization

    Returns:
        Dictionary with theme summary data
    """
    # Build review text
    reviews_text = "\n\n".join([f"- {review}" for review in reviews[:50]])  # Limit to 50 reviews

    # Build prompt
    prompt = prompt_template.replace("{theme_name}", theme_name)
    prompt = prompt.replace("{reviews_text}", reviews_text)

    # Call API
    try:
        response = model.generate_content(prompt)
        response_text = response.text

        # Try to parse JSON
        response_text = response_text.strip()

        # Extract JSON if wrapped in markdown
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        summary_data = json.loads(response_text)

        logger.info(f"Summarized theme: {theme_name}")

        return summary_data

    except Exception as e:
        logger.error(f"Failed to summarize theme {theme_name}: {str(e)}")

        # Return fallback summary
        return {
            "theme": theme_name,
            "key_points": [f"{len(reviews)} reviews about {theme_name}"],
            "candidate_quotes": []
        }


def summarize_all_themes(
    model: genai.GenerativeModel,
    df: pd.DataFrame,
    top_themes: List[Tuple[str, int]],
    prompt_template: str
) -> Dict[str, Any]:
    """
    Summarize all top themes (Map step).

    Args:
        model: Gemini model instance
        df: DataFrame with reviews
        top_themes: List of (theme_name, count) tuples
        prompt_template: Prompt template for summarization

    Returns:
        Dictionary mapping theme names to summaries
    """
    theme_summaries = {}

    for theme_name, count in tqdm(top_themes, desc="Summarizing themes"):
        # Get reviews for this theme
        theme_reviews = df[df['theme'] == theme_name]['text'].tolist()

        # Summarize
        with Timer() as t:
            summary = summarize_theme(model, theme_name, theme_reviews, prompt_template)

        logger.info(f"Theme '{theme_name}' summarized in {t.duration:.2f}s")

        theme_summaries[theme_name] = {
            **summary,
            "count": count
        }

    return theme_summaries


# ============================================================================
# WEEKLY SYNTHESIS (REDUCE)
# ============================================================================

def synthesize_weekly_note(
    model: genai.GenerativeModel,
    theme_summaries: Dict[str, Any],
    week_start: datetime,
    week_end: datetime,
    prompt_template: str
) -> Dict[str, Any]:
    """
    Synthesize weekly pulse note from theme summaries (Reduce step).

    Args:
        model: Gemini model instance
        theme_summaries: Dictionary of theme summaries
        week_start: Week start date
        week_end: Week end date
        prompt_template: Prompt template for synthesis

    Returns:
        Dictionary with weekly note data
    """
    # Format week label
    week_label = format_week_label(week_start, week_end)

    # Build theme summaries text
    summaries_text = ""
    for theme_name, summary in theme_summaries.items():
        summaries_text += f"\n### {theme_name} ({summary['count']} reviews)\n"
        summaries_text += f"Key Points:\n"
        for point in summary.get('key_points', []):
            summaries_text += f"- {point}\n"
        if summary.get('candidate_quotes'):
            summaries_text += f"Sample Quotes:\n"
            for quote in summary.get('candidate_quotes', [])[:3]:
                summaries_text += f'- "{quote}"\n'
        summaries_text += "\n"

    # Build prompt
    prompt = prompt_template.replace("{theme_summaries}", summaries_text)
    prompt = prompt.replace("{week_label}", week_label)
    prompt = prompt.replace("{max_words}", str(WEEKLY_NOTE_MAX_WORDS))
    prompt = prompt.replace("{top_themes}", str(len(theme_summaries)))

    # Call API
    try:
        response = model.generate_content(prompt)
        response_text = response.text

        # Extract JSON
        response_text = response_text.strip()
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        note_data = json.loads(response_text)

        logger.info("Synthesized weekly note")

        return note_data

    except Exception as e:
        logger.error(f"Failed to synthesize weekly note: {str(e)}")
        raise


# ============================================================================
# WORD COUNT ENFORCEMENT
# ============================================================================

def count_markdown_words(markdown_text: str) -> int:
    """
    Count words in markdown text, excluding markdown syntax.

    Args:
        markdown_text: Markdown text

    Returns:
        Word count
    """
    # Remove markdown syntax
    text = re.sub(r'#+\s', '', markdown_text)  # Headers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # Italic
    text = re.sub(r'^\s*[-*]\s', '', text, flags=re.MULTILINE)  # Bullets

    return count_words(text)


def compress_note(
    model: genai.GenerativeModel,
    note_data: Dict[str, Any],
    target_words: int
) -> Dict[str, Any]:
    """
    Compress note to meet word count limit.

    Args:
        model: Gemini model instance
        note_data: Original note data
        target_words: Target word count

    Returns:
        Compressed note data
    """
    compression_prompt = f"""
You are compressing a weekly review summary to meet a word limit.

Original summary (TOO LONG):
{json.dumps(note_data, indent=2)}

Requirements:
- Maximum {target_words} words in the final markdown output
- Keep title, overview, all {len(note_data.get('themes', []))} themes
- Keep {len(note_data.get('quotes', []))} quotes (shorten if needed)
- Keep {len(note_data.get('actions', []))} actions (make concise)
- Maintain key insights and actionable information
- Remove filler words and redundancy

Return compressed version as JSON with same structure:
{{
  "title": "...",
  "overview": "...",
  "themes": [{{"name": "...", "summary": "..."}}, ...],
  "quotes": ["...", "...", "..."],
  "actions": ["...", "...", "..."]
}}
"""

    try:
        response = model.generate_content(compression_prompt)
        response_text = response.text.strip()

        # Extract JSON
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        compressed_data = json.loads(response_text)

        logger.info("Compressed note successfully")

        return compressed_data

    except Exception as e:
        logger.error(f"Failed to compress note: {str(e)}")
        # Return original if compression fails
        return note_data


def enforce_word_limit(
    model: genai.GenerativeModel,
    note_data: Dict[str, Any],
    max_words: int = WEEKLY_NOTE_MAX_WORDS
) -> Dict[str, Any]:
    """
    Enforce word count limit on note, compressing if needed.

    Args:
        model: Gemini model instance
        note_data: Note data dictionary
        max_words: Maximum allowed words

    Returns:
        Note data that meets word count limit
    """
    # Convert to markdown to check word count
    markdown = format_note_as_markdown(note_data, datetime.now(), datetime.now())
    word_count = count_markdown_words(markdown)

    logger.info(f"Initial word count: {word_count}")

    if word_count <= max_words:
        logger.info("Word count within limit")
        return note_data

    # Compress iteratively
    compressed_data = note_data
    for attempt in range(1, MAX_COMPRESSION_ATTEMPTS + 1):
        logger.info(f"Compression attempt {attempt}/{MAX_COMPRESSION_ATTEMPTS}")

        compressed_data = compress_note(model, compressed_data, max_words)

        # Check new word count
        markdown = format_note_as_markdown(compressed_data, datetime.now(), datetime.now())
        word_count = count_markdown_words(markdown)

        logger.info(f"Word count after compression: {word_count}")

        if word_count <= max_words:
            logger.info("Compression successful")
            return compressed_data

    logger.warning(f"Could not compress to {max_words} words after {MAX_COMPRESSION_ATTEMPTS} attempts")
    logger.warning(f"Final word count: {word_count}")

    return compressed_data


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def format_note_as_markdown(
    note_data: Dict[str, Any],
    week_start: datetime,
    week_end: datetime
) -> str:
    """
    Format note data as markdown.

    Args:
        note_data: Note data dictionary
        week_start: Week start date
        week_end: Week end date

    Returns:
        Formatted markdown string
    """
    week_label = format_week_label(week_start, week_end)

    markdown = f"""# {note_data.get('title', 'Weekly Pulse')}

**Week:** {week_label}

## Overview

{note_data.get('overview', '')}

## Top Themes

"""

    # Add themes
    for theme_item in note_data.get('themes', []):
        theme_name = theme_item.get('name', '')
        theme_summary = theme_item.get('summary', '')
        markdown += f"- **{theme_name}:** {theme_summary}\n"

    # Add quotes
    markdown += "\n## User Quotes\n\n"
    for quote in note_data.get('quotes', []):
        markdown += f'- "{quote}"\n'

    # Add actions
    markdown += "\n## Action Ideas\n\n"
    for action in note_data.get('actions', []):
        markdown += f"- {action}\n"

    return markdown


def check_final_pii(markdown_text: str) -> str:
    """
    Final PII check on markdown output.

    Args:
        markdown_text: Markdown text

    Returns:
        Cleaned markdown text
    """
    cleaned = scrub_all_pii(markdown_text)

    if cleaned != markdown_text:
        logger.warning("PII patterns found in final output and scrubbed")
        logger.warning("This should be rare - please review source data")

    return cleaned


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Generate weekly pulse note from classified reviews'
    )
    parser.add_argument(
        '--week-start',
        type=str,
        help='Week start date (ISO format: YYYY-MM-DD)'
    )
    parser.add_argument(
        '--week-end',
        type=str,
        help='Week end date (ISO format: YYYY-MM-DD)'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Weekly Pulse Note Generation")
    logger.info("=" * 60)

    with Timer() as total_timer:
        try:
            # Step 1: Determine week range
            if args.week_start and args.week_end:
                week_start = datetime.fromisoformat(args.week_start)
                week_end = datetime.fromisoformat(args.week_end)
            else:
                week_start, week_end = get_last_complete_week()

            logger.info(f"Processing week: {week_start.date()} to {week_end.date()}")

            # Step 2: Load and filter reviews
            log_pipeline_step(logger, "Load Reviews", "START")
            with Timer() as t:
                input_path = get_latest_themed_file()
                df = load_and_filter_reviews(input_path, week_start, week_end)

            if df.empty:
                logger.warning("No reviews found for the specified week")
                return

            log_pipeline_step(
                logger, "Load Reviews", "SUCCESS",
                duration=t.duration,
                metadata={"count": len(df)}
            )

            # Step 3: Select top themes
            log_pipeline_step(logger, "Select Top Themes", "START")
            with Timer() as t:
                top_themes = select_top_themes(df)

            log_pipeline_step(
                logger, "Select Top Themes", "SUCCESS",
                duration=t.duration,
                metadata={"themes": len(top_themes)}
            )

            # Step 4: Setup Gemini
            model = setup_gemini()
            summarize_prompt = load_prompt("summarize_theme")
            synthesis_prompt = load_prompt("weekly_synthesis")

            # Step 5: Summarize themes (Map)
            log_pipeline_step(logger, "Summarize Themes", "START")
            with Timer() as t:
                theme_summaries = summarize_all_themes(
                    model, df, top_themes, summarize_prompt
                )

            log_pipeline_step(
                logger, "Summarize Themes", "SUCCESS",
                duration=t.duration,
                metadata={"themes": len(theme_summaries)}
            )

            # Step 6: Synthesize weekly note (Reduce)
            log_pipeline_step(logger, "Synthesize Weekly Note", "START")
            with Timer() as t:
                note_data = synthesize_weekly_note(
                    model, theme_summaries, week_start, week_end, synthesis_prompt
                )

            log_pipeline_step(
                logger, "Synthesize Weekly Note", "SUCCESS",
                duration=t.duration
            )

            # Step 7: Enforce word limit
            log_pipeline_step(logger, "Enforce Word Limit", "START")
            with Timer() as t:
                note_data = enforce_word_limit(model, note_data)

            log_pipeline_step(
                logger, "Enforce Word Limit", "SUCCESS",
                duration=t.duration
            )

            # Step 8: Format as markdown
            markdown = format_note_as_markdown(note_data, week_start, week_end)

            # Step 9: Final PII check
            markdown = check_final_pii(markdown)

            word_count = count_markdown_words(markdown)
            logger.info(f"Final word count: {word_count} words")

            # Step 10: Save outputs
            date_str = week_start.strftime("%Y-%m-%d")

            json_path = NOTES_DIR / f"weekly_pulse_{date_str}.json"
            md_path = NOTES_DIR / f"weekly_pulse_{date_str}.md"

            # Add metadata to JSON
            output_data = {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "week_label": format_week_label(week_start, week_end),
                "total_reviews": len(df),
                "word_count": word_count,
                **note_data
            }

            save_json(output_data, json_path)
            save_markdown(markdown, md_path)

            logger.info(f"Saved JSON to: {json_path}")
            logger.info(f"Saved Markdown to: {md_path}")

        except Exception as e:
            logger.error(f"Note generation failed: {str(e)}", exc_info=True)
            log_pipeline_step(logger, "Generate Note", "FAILED")
            raise

    logger.info(f"Total execution time: {total_timer.duration:.2f}s")
    logger.info("Weekly pulse note generated successfully!")


if __name__ == "__main__":
    main()
