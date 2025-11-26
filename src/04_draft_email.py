"""Step 4: Draft email body from weekly pulse note using Gemini API."""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import google.generativeai as genai

from src.config import (
    GEMINI_API_KEY,
    GEMINI_PRO_MODEL,
    EMAIL_DRAFT_MAX_WORDS,
    NOTES_DIR,
    EMAILS_DIR,
    PROMPTS_DIR,
    setup_logging,
)
from src.utils import (
    ensure_dir_exists,
    log_pipeline_step,
    Timer,
    count_words,
    scrub_all_pii,
    format_week_label,
)

# Setup logging
logger = setup_logging(name=__name__)

# Constants
TEMPERATURE = 0.3
MAX_RETRIES = 3
MAX_COMPRESSION_ATTEMPTS = 3
REQUIRED_SECTIONS = ['intro', 'themes', 'quotes', 'actions', 'closing']


# ============================================================================
# GEMINI API SETUP
# ============================================================================

def setup_gemini() -> genai.GenerativeModel:
    """
    Configure Gemini API and return Pro model instance.

    Returns:
        Configured GenerativeModel instance for email drafting

    Raises:
        ValueError: If API key is not set
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_PRO_MODEL,
        generation_config={
            "temperature": TEMPERATURE,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
    )

    logger.info(f"Initialized Gemini model: {GEMINI_PRO_MODEL}")
    logger.info(f"Temperature: {TEMPERATURE}")

    return model


def load_email_prompt() -> str:
    """
    Load email draft prompt template from file.

    Returns:
        Prompt template string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / "draft_email.txt"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read()

    logger.info(f"Loaded email prompt from: {prompt_path}")
    return prompt


# ============================================================================
# INPUT HANDLING
# ============================================================================

def get_latest_note_file() -> Path:
    """
    Get the most recent JSON note file from outputs/notes directory.

    Returns:
        Path to latest note file

    Raises:
        FileNotFoundError: If no note files found
    """
    json_files = sorted(NOTES_DIR.glob("weekly_pulse_*.json"))

    if not json_files:
        raise FileNotFoundError(f"No note files found in {NOTES_DIR}")

    latest_file = json_files[-1]
    logger.info(f"Found latest note file: {latest_file}")

    return latest_file


def load_note_data(file_path: Path) -> Dict[str, Any]:
    """
    Load weekly pulse note from JSON file.

    Args:
        file_path: Path to JSON note file

    Returns:
        Dictionary with note data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Note file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        note_data = json.load(f)

    logger.info(f"Loaded note data from: {file_path}")
    logger.info(f"Note metadata: {note_data.get('metadata', {})}")

    return note_data


# ============================================================================
# EMAIL GENERATION
# ============================================================================

def build_email_prompt(
    prompt_template: str,
    note_data: Dict[str, Any],
    max_words: int = EMAIL_DRAFT_MAX_WORDS
) -> str:
    """
    Build email generation prompt from template and note data.

    Args:
        prompt_template: Email prompt template
        note_data: Weekly pulse note data
        max_words: Maximum word count for email

    Returns:
        Complete prompt for Gemini
    """
    # Extract note content and metadata
    note_content = note_data.get('note', {})
    metadata = note_data.get('metadata', {})

    # Format note content as readable text
    note_text = f"""
Title: {note_content.get('title', 'N/A')}

Overview:
{note_content.get('overview', 'N/A')}

Themes:
"""
    for i, theme in enumerate(note_content.get('themes', []), 1):
        note_text += f"{i}. {theme.get('name', 'N/A')}: {theme.get('summary', 'N/A')}\n"

    note_text += "\nUser Quotes:\n"
    for i, quote in enumerate(note_content.get('quotes', []), 1):
        note_text += f"{i}. \"{quote}\"\n"

    note_text += "\nRecommended Actions:\n"
    for i, action in enumerate(note_content.get('actions', []), 1):
        note_text += f"{i}. {action}\n"

    # Get week label
    week_start = metadata.get('week_start', '')
    week_end = metadata.get('week_end', '')

    if week_start and week_end:
        try:
            start_date = datetime.fromisoformat(week_start)
            end_date = datetime.fromisoformat(week_end)
            week_label = format_week_label(start_date, end_date)
        except ValueError:
            week_label = metadata.get('week_label', 'N/A')
    else:
        week_label = metadata.get('week_label', 'N/A')

    # Get total reviews
    total_reviews = metadata.get('total_reviews', 'N/A')

    # Fill in prompt template
    prompt = prompt_template.replace("{note_content}", note_text)
    prompt = prompt.replace("{week_label}", week_label)
    prompt = prompt.replace("{total_reviews}", str(total_reviews))
    prompt = prompt.replace("{max_words}", str(max_words))

    return prompt


def generate_email_draft(
    model: genai.GenerativeModel,
    prompt: str,
    max_retries: int = MAX_RETRIES
) -> str:
    """
    Generate email draft using Gemini API with retry logic.

    Args:
        model: Gemini model instance
        prompt: Complete prompt for email generation
        max_retries: Maximum number of retry attempts

    Returns:
        Generated email body text

    Raises:
        Exception: If all retries fail
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Generating email draft (attempt {attempt}/{max_retries})")

            with Timer() as t:
                response = model.generate_content(prompt)
                email_text = response.text.strip()

            logger.debug(f"Email generation completed in {t.duration:.2f}s")

            # Clean up any markdown code blocks
            if "```" in email_text:
                # Extract content between code blocks
                match = re.search(r'```(?:text|email)?\s*\n(.*?)\n```', email_text, re.DOTALL)
                if match:
                    email_text = match.group(1).strip()
                else:
                    # Remove any remaining code block markers
                    email_text = re.sub(r'```(?:text|email)?\s*\n?', '', email_text)
                    email_text = email_text.strip()

            return email_text

        except Exception as e:
            logger.error(f"Attempt {attempt}: Email generation error: {str(e)}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    raise Exception(f"Email generation failed after {max_retries} attempts")


# ============================================================================
# EMAIL VALIDATION
# ============================================================================

def validate_email_structure(email_text: str) -> Dict[str, bool]:
    """
    Validate that email contains required sections.

    Args:
        email_text: Email body text

    Returns:
        Dictionary mapping section names to presence booleans
    """
    email_lower = email_text.lower()

    # Heuristic checks for sections
    validation = {
        'intro': False,
        'themes': False,
        'quotes': False,
        'actions': False,
        'closing': False,
    }

    # Check for intro (first 100 chars should mention week/reviews)
    intro_text = email_lower[:100]
    if any(keyword in intro_text for keyword in ['week', 'review', 'pulse', 'analyzed']):
        validation['intro'] = True

    # Check for themes (mentions theme-related keywords)
    if any(keyword in email_lower for keyword in ['theme', 'focus', 'area', 'insight']):
        validation['themes'] = True

    # Check for quotes (bullet points or quote marks)
    if ('- "' in email_text or '• "' in email_text or
        email_text.count('"') >= 6):  # At least 3 quoted phrases
        validation['quotes'] = True

    # Check for actions (numbered list)
    if re.search(r'\n\s*\d+\.', email_text):
        validation['actions'] = True

    # Check for closing (last 100 chars should have closing phrase)
    closing_text = email_lower[-100:]
    if any(keyword in closing_text for keyword in ['let me know', 'reach out', 'questions', 'dive deeper']):
        validation['closing'] = True

    return validation


def enforce_word_limit(
    model: genai.GenerativeModel,
    email_text: str,
    max_words: int = EMAIL_DRAFT_MAX_WORDS
) -> str:
    """
    Ensure email body does not exceed word limit.
    If it does, compress using Gemini.

    Args:
        model: Gemini model instance
        email_text: Current email body text
        max_words: Maximum allowed words

    Returns:
        Email text within word limit
    """
    current_word_count = count_words(email_text)

    if current_word_count <= max_words:
        logger.info(f"Email word count OK: {current_word_count}/{max_words} words")
        return email_text

    logger.warning(f"Email exceeds word limit: {current_word_count}/{max_words} words")

    # Attempt compression
    for attempt in range(1, MAX_COMPRESSION_ATTEMPTS + 1):
        logger.info(f"Compression attempt {attempt}/{MAX_COMPRESSION_ATTEMPTS}")

        compression_prompt = f"""
You are editing an email to reduce its word count.

Current email body ({current_word_count} words):
\"\"\"
{email_text}
\"\"\"

Your task:
- Reduce the email to {max_words} words maximum
- Maintain all key sections: intro, themes, quotes, actions, closing
- Keep the same structure and tone
- Do NOT remove any quotes or action items
- Make the intro and theme descriptions more concise

Return ONLY the compressed email body, no additional text.
"""

        try:
            with Timer() as t:
                response = model.generate_content(compression_prompt)
                compressed_text = response.text.strip()

            # Clean up code blocks if present
            if "```" in compressed_text:
                match = re.search(r'```(?:text|email)?\s*\n(.*?)\n```', compressed_text, re.DOTALL)
                if match:
                    compressed_text = match.group(1).strip()

            new_word_count = count_words(compressed_text)
            logger.info(f"Compressed to {new_word_count} words in {t.duration:.2f}s")

            if new_word_count <= max_words:
                return compressed_text

            # Update for next iteration
            email_text = compressed_text
            current_word_count = new_word_count

        except Exception as e:
            logger.error(f"Compression attempt {attempt} failed: {str(e)}")
            break

    # Return best effort
    logger.warning(f"Could not compress to {max_words} words, returning closest: {current_word_count} words")
    return email_text


# ============================================================================
# SUBJECT LINE GENERATION
# ============================================================================

def generate_subject_line(note_data: Dict[str, Any]) -> str:
    """
    Generate subject line for email.

    Format: "Groww Weekly Pulse – Google Play Reviews (Nov 18-24, 2024)"

    Args:
        note_data: Weekly pulse note data

    Returns:
        Subject line string
    """
    metadata = note_data.get('metadata', {})
    week_label = metadata.get('week_label', 'N/A')

    subject = f"Groww Weekly Pulse – Google Play Reviews ({week_label})"

    logger.info(f"Generated subject line: {subject}")

    return subject


# ============================================================================
# PII SCRUBBING
# ============================================================================

def check_for_pii(text: str) -> bool:
    """
    Check if text contains PII patterns.

    Args:
        text: Text to check

    Returns:
        True if PII found, False otherwise
    """
    # Check for email pattern
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        return True

    # Check for phone pattern
    if re.search(r'\b\d{10}\b|\+\d{1,3}[-.\s]?[\d\-.\s]{6,20}', text):
        return True

    # Check for @mentions
    if re.search(r'@\w+', text):
        return True

    return False


def scrub_pii_from_email(
    model: genai.GenerativeModel,
    email_text: str,
    max_retries: int = MAX_RETRIES
) -> str:
    """
    Remove PII from email by re-prompting Gemini if PII detected.

    Args:
        model: Gemini model instance
        email_text: Email body text
        max_retries: Maximum retry attempts

    Returns:
        Email text with PII removed
    """
    # First pass: automated scrubbing
    scrubbed_text = scrub_all_pii(email_text)

    # Check if PII still exists
    if not check_for_pii(scrubbed_text):
        logger.info("No PII detected in email")
        return scrubbed_text

    # PII detected - re-prompt Gemini
    logger.warning("PII detected in email, re-prompting Gemini for removal")

    for attempt in range(1, max_retries + 1):
        try:
            pii_removal_prompt = f"""
Remove any personally identifiable information (PII) from this email:

Email:
\"\"\"
{scrubbed_text}
\"\"\"

PII includes:
- Email addresses
- Phone numbers
- @mentions or usernames
- Any other identifying information

Replace PII with generic placeholders like [EMAIL], [PHONE], [USER].
Maintain the same structure and tone.

Return ONLY the cleaned email body, no additional text.
"""

            with Timer() as t:
                response = model.generate_content(pii_removal_prompt)
                cleaned_text = response.text.strip()

            # Clean up code blocks
            if "```" in cleaned_text:
                match = re.search(r'```(?:text|email)?\s*\n(.*?)\n```', cleaned_text, re.DOTALL)
                if match:
                    cleaned_text = match.group(1).strip()

            logger.info(f"PII removal completed in {t.duration:.2f}s")

            # Apply automated scrubbing again
            cleaned_text = scrub_all_pii(cleaned_text)

            # Check if PII still exists
            if not check_for_pii(cleaned_text):
                return cleaned_text

            logger.warning(f"Attempt {attempt}: PII still detected, retrying...")

        except Exception as e:
            logger.error(f"PII removal attempt {attempt} failed: {str(e)}")
            if attempt < max_retries:
                time.sleep(2)

    # Return best effort
    logger.warning("Could not fully remove PII, returning best effort")
    return scrub_all_pii(scrubbed_text)


# ============================================================================
# OUTPUT
# ============================================================================

def format_email_output(subject: str, body: str) -> str:
    """
    Format complete email output with subject and body.

    Args:
        subject: Email subject line
        body: Email body text

    Returns:
        Formatted email string
    """
    return f"Subject: {subject}\n\n{body}"


def save_email_draft(email_text: str, output_path: Path) -> None:
    """
    Save email draft to file.

    Args:
        email_text: Complete email text (subject + body)
        output_path: Path to output file
    """
    ensure_dir_exists(output_path.parent)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(email_text)

    logger.info(f"Saved email draft to: {output_path}")


def preview_email(email_text: str) -> None:
    """
    Print email to console for preview.

    Args:
        email_text: Complete email text
    """
    print("\n" + "=" * 70)
    print("EMAIL DRAFT PREVIEW")
    print("=" * 70)
    print(email_text)
    print("=" * 70 + "\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Generate email draft from weekly pulse note using Gemini API'
    )
    parser.add_argument(
        '--note-file',
        type=str,
        help='Path to specific note JSON file (default: latest from outputs/notes/)'
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Preview email in console instead of saving to file'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Email Draft Generation")
    logger.info("=" * 60)

    with Timer() as total_timer:
        try:
            # Step 1: Load input file
            log_pipeline_step(logger, "Load Note Data", "START")
            with Timer() as t:
                if args.note_file:
                    note_path = Path(args.note_file)
                else:
                    note_path = get_latest_note_file()

                note_data = load_note_data(note_path)

            log_pipeline_step(
                logger, "Load Note Data", "SUCCESS",
                duration=t.duration,
                metadata={"file": note_path.name}
            )

            # Step 2: Setup Gemini
            log_pipeline_step(logger, "Setup Gemini API", "START")
            with Timer() as t:
                model = setup_gemini()
                email_prompt = load_email_prompt()

            log_pipeline_step(
                logger, "Setup Gemini API", "SUCCESS",
                duration=t.duration
            )

            # Step 3: Generate email draft
            log_pipeline_step(logger, "Generate Email Draft", "START")
            with Timer() as t:
                prompt = build_email_prompt(email_prompt, note_data)
                email_body = generate_email_draft(model, prompt)

            log_pipeline_step(
                logger, "Generate Email Draft", "SUCCESS",
                duration=t.duration,
                metadata={"word_count": count_words(email_body)}
            )

            # Step 4: Validate structure
            log_pipeline_step(logger, "Validate Email Structure", "START")
            with Timer() as t:
                validation = validate_email_structure(email_body)
                missing_sections = [k for k, v in validation.items() if not v]

                if missing_sections:
                    logger.warning(f"Email may be missing sections: {missing_sections}")

            log_pipeline_step(
                logger, "Validate Email Structure", "SUCCESS",
                duration=t.duration,
                metadata={"valid_sections": sum(validation.values()), "total_sections": len(validation)}
            )

            # Step 5: Enforce word limit
            log_pipeline_step(logger, "Enforce Word Limit", "START")
            with Timer() as t:
                email_body = enforce_word_limit(model, email_body, EMAIL_DRAFT_MAX_WORDS)
                final_word_count = count_words(email_body)

            log_pipeline_step(
                logger, "Enforce Word Limit", "SUCCESS",
                duration=t.duration,
                metadata={"final_word_count": final_word_count, "limit": EMAIL_DRAFT_MAX_WORDS}
            )

            # Step 6: Generate subject line
            log_pipeline_step(logger, "Generate Subject Line", "START")
            with Timer() as t:
                subject = generate_subject_line(note_data)

            log_pipeline_step(
                logger, "Generate Subject Line", "SUCCESS",
                duration=t.duration
            )

            # Step 7: Final PII scrub
            log_pipeline_step(logger, "PII Scrubbing", "START")
            with Timer() as t:
                email_body = scrub_pii_from_email(model, email_body)

            log_pipeline_step(
                logger, "PII Scrubbing", "SUCCESS",
                duration=t.duration
            )

            # Step 8: Format and output
            complete_email = format_email_output(subject, email_body)

            if args.preview:
                # Preview mode
                log_pipeline_step(logger, "Preview Email", "START")
                preview_email(complete_email)
                log_pipeline_step(logger, "Preview Email", "SUCCESS")

            else:
                # Save mode
                today_str = datetime.now().strftime("%Y-%m-%d")
                output_path = EMAILS_DIR / f"email_draft_{today_str}.txt"

                log_pipeline_step(logger, "Save Email Draft", "START")
                with Timer() as t:
                    save_email_draft(complete_email, output_path)

                log_pipeline_step(
                    logger, "Save Email Draft", "SUCCESS",
                    duration=t.duration,
                    metadata={"path": str(output_path)}
                )

                print(f"\nEmail draft saved to: {output_path}")
                print(f"Word count: {final_word_count}/{EMAIL_DRAFT_MAX_WORDS} words")

        except Exception as e:
            logger.error(f"Email draft generation failed: {str(e)}", exc_info=True)
            log_pipeline_step(logger, "Email Draft Generation", "FAILED")
            raise

    logger.info(f"Total execution time: {total_timer.duration:.2f}s")
    logger.info("Email draft generation completed successfully!")


if __name__ == "__main__":
    main()
