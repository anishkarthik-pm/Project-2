"""Main orchestrator for the Groww app review analyzer pipeline."""

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from src.config import (
    LOGS_DIR,
    PROCESSED_DATA_DIR,
    NOTES_DIR,
    EMAILS_DIR,
    setup_logging,
)
from src.utils import (
    ensure_dir_exists,
    Timer,
)

# Setup logging
logger = setup_logging(name=__name__)

# Pipeline state file
PIPELINE_STATE_FILE = LOGS_DIR / "pipeline_state.json"


# ============================================================================
# PIPELINE STATE MANAGEMENT
# ============================================================================

class PipelineError(Exception):
    """Custom exception for pipeline errors."""
    pass


def save_pipeline_state(state: Dict[str, Any]) -> None:
    """
    Save pipeline state to JSON file.

    Args:
        state: Pipeline state dictionary
    """
    ensure_dir_exists(PIPELINE_STATE_FILE.parent)

    with open(PIPELINE_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, default=str)

    logger.debug(f"Pipeline state saved to: {PIPELINE_STATE_FILE}")


def load_pipeline_state() -> Dict[str, Any]:
    """
    Load pipeline state from JSON file.

    Returns:
        Pipeline state dictionary, or empty dict if file doesn't exist
    """
    if not PIPELINE_STATE_FILE.exists():
        return {}

    with open(PIPELINE_STATE_FILE, 'r', encoding='utf-8') as f:
        state = json.load(f)

    logger.debug(f"Pipeline state loaded from: {PIPELINE_STATE_FILE}")
    return state


# ============================================================================
# PIPELINE STEP EXECUTION
# ============================================================================

def run_step(
    step_num: int,
    step_name: str,
    script_path: str,
    args: list = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run a single pipeline step using subprocess.

    Args:
        step_num: Step number (1-5)
        step_name: Human-readable step name
        script_path: Path to Python script
        args: Additional command-line arguments
        dry_run: Whether to skip email sending

    Returns:
        Step result dictionary with status, duration, etc.

    Raises:
        PipelineError: If step execution fails
    """
    logger.info("=" * 60)
    logger.info(f"Step {step_num}/5: {step_name}")
    logger.info("=" * 60)

    # Skip email sending in dry run mode
    if dry_run and step_num == 5:
        logger.info("DRY RUN MODE: Skipping email sending")
        return {
            "step": step_num,
            "name": step_name,
            "status": "skipped",
            "duration": 0,
            "message": "Skipped due to dry-run mode"
        }

    # Build command
    cmd = [sys.executable, "-m", script_path.replace("/", ".").replace(".py", "")]
    if args:
        cmd.extend(args)

    # Add --dry-run flag for email sender
    if dry_run and step_num == 4:
        cmd.append("--preview")

    logger.info(f"Executing: {' '.join(cmd)}")

    with Timer() as t:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10 minute timeout
            )

            # Log output
            if result.stdout:
                logger.info("STDOUT:")
                for line in result.stdout.strip().split('\n'):
                    logger.info(f"  {line}")

            logger.info(f"✓ Step {step_num} completed successfully in {t.duration:.2f}s")

            return {
                "step": step_num,
                "name": step_name,
                "status": "success",
                "duration": t.duration,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Step {step_num} failed with exit code {e.returncode}")
            logger.error("STDOUT:")
            logger.error(e.stdout)
            logger.error("STDERR:")
            logger.error(e.stderr)

            raise PipelineError(
                f"Step {step_num} ({step_name}) failed with exit code {e.returncode}\n"
                f"Error: {e.stderr}"
            )

        except subprocess.TimeoutExpired:
            logger.error(f"✗ Step {step_num} timed out after 10 minutes")
            raise PipelineError(f"Step {step_num} ({step_name}) timed out")

        except Exception as e:
            logger.error(f"✗ Step {step_num} failed with unexpected error: {str(e)}")
            raise PipelineError(f"Step {step_num} ({step_name}) failed: {str(e)}")


# ============================================================================
# SUMMARY REPORT
# ============================================================================

def generate_summary_report(state: Dict[str, Any]) -> str:
    """
    Generate summary report of pipeline execution.

    Args:
        state: Pipeline state dictionary

    Returns:
        Formatted summary report string
    """
    summary = []
    summary.append("\n" + "=" * 70)
    summary.append("PIPELINE EXECUTION SUMMARY")
    summary.append("=" * 70)

    # Overall status
    if state.get("status") == "success":
        summary.append("Status: ✓ SUCCESS")
    else:
        summary.append(f"Status: ✗ FAILED ({state.get('failed_step', 'unknown')})")

    summary.append(f"Total Duration: {state.get('total_duration', 0):.2f}s")
    summary.append(f"Started: {state.get('start_time', 'N/A')}")
    summary.append(f"Completed: {state.get('end_time', 'N/A')}")
    summary.append("")

    # Step-by-step results
    summary.append("Step Results:")
    for step in state.get("steps", []):
        status_symbol = "✓" if step["status"] == "success" else "✗" if step["status"] == "failed" else "○"
        summary.append(
            f"  {status_symbol} Step {step['step']}: {step['name']} "
            f"({step.get('duration', 0):.2f}s) - {step['status'].upper()}"
        )

    summary.append("")

    # Statistics
    stats = state.get("statistics", {})
    if stats:
        summary.append("Statistics:")
        summary.append(f"  Total Reviews Processed: {stats.get('total_reviews', 'N/A')}")
        summary.append(f"  Reviews Analyzed: {stats.get('reviews_analyzed', 'N/A')}")

        theme_dist = stats.get('theme_distribution', {})
        if theme_dist:
            summary.append("  Theme Distribution:")
            for theme, count in sorted(theme_dist.items(), key=lambda x: x[1], reverse=True):
                summary.append(f"    - {theme}: {count}")

        summary.append(f"  Note Word Count: {stats.get('note_word_count', 'N/A')}")
        summary.append(f"  Email Word Count: {stats.get('email_word_count', 'N/A')}")
        summary.append(f"  Email Sent: {'Yes' if stats.get('email_sent') else 'No' if 'email_sent' in stats else 'N/A'}")

    summary.append("")

    # Output files
    outputs = state.get("outputs", {})
    if outputs:
        summary.append("Output Files:")
        for key, path in outputs.items():
            summary.append(f"  - {key}: {path}")

    summary.append("=" * 70)

    return "\n".join(summary)


def collect_statistics(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect statistics from pipeline outputs.

    Args:
        state: Pipeline state dictionary

    Returns:
        Statistics dictionary
    """
    stats = {}

    try:
        # Get latest CSV files
        csv_files = sorted(PROCESSED_DATA_DIR.glob("reviews_themed_*.csv"))
        if csv_files:
            import pandas as pd
            df = pd.read_csv(csv_files[-1])
            stats['reviews_analyzed'] = len(df)
            stats['theme_distribution'] = df['theme'].value_counts().to_dict()

        # Get note word count
        note_files = sorted(NOTES_DIR.glob("weekly_pulse_*.json"))
        if note_files:
            with open(note_files[-1], 'r') as f:
                note_data = json.load(f)
                metadata = note_data.get('metadata', {})
                stats['note_word_count'] = metadata.get('word_count', 'N/A')
                stats['total_reviews'] = metadata.get('total_reviews', 'N/A')

        # Check if email was sent
        email_files = sorted(EMAILS_DIR.glob("email_draft_*.txt"))
        if email_files:
            with open(email_files[-1], 'r') as f:
                content = f.read()
                # Count words in email body (skip subject line)
                body = content.split('\n\n', 1)[1] if '\n\n' in content else content
                stats['email_word_count'] = len(body.split())

        # Check email sent log
        email_log = LOGS_DIR / "email_sent.log"
        if email_log.exists():
            with open(email_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1]
                    stats['email_sent'] = 'SUCCESS' in last_line

    except Exception as e:
        logger.warning(f"Could not collect all statistics: {str(e)}")

    return stats


# ============================================================================
# ERROR NOTIFICATION
# ============================================================================

def send_error_notification(
    failed_step: str,
    error_message: str,
    logs_excerpt: str
) -> None:
    """
    Send error notification email.

    Args:
        failed_step: Name of failed step
        error_message: Error message
        logs_excerpt: Excerpt from logs
    """
    try:
        import smtplib
        import ssl
        import os
        from email.mime.text import MIMEText
        from email.utils import formatdate
        from dotenv import load_dotenv

        load_dotenv()

        email_from = os.getenv('EMAIL_FROM')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_to = os.getenv('EMAIL_TO')

        if not all([email_from, email_password, email_to]):
            logger.warning("Email credentials not configured, skipping error notification")
            return

        # Create email body
        body = f"""
Pipeline Execution Failed

Failed Step: {failed_step}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Error Message:
{error_message}

Recent Logs:
{logs_excerpt}

Please check the full logs at: {LOGS_DIR}/pipeline.log

---
Groww App Review Analyzer
"""

        # Create message
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = f"❌ Pipeline Failed - {failed_step}"
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Date'] = formatdate(localtime=True)

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=10) as server:
            server.login(email_from, email_password)
            server.send_message(msg)

        logger.info(f"Error notification sent to {email_to}")

    except Exception as e:
        logger.error(f"Failed to send error notification: {str(e)}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(
    weeks_back: int = 1,
    week_start: Optional[str] = None,
    week_end: Optional[str] = None,
    dry_run: bool = False,
    step: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run the complete pipeline end-to-end.

    Args:
        weeks_back: Number of weeks to look back (default: 1)
        week_start: Override week start date (YYYY-MM-DD)
        week_end: Override week end date (YYYY-MM-DD)
        dry_run: Skip email sending
        step: Run only specific step (1-5)

    Returns:
        Pipeline state dictionary

    Raises:
        PipelineError: If any step fails
    """
    state = {
        "start_time": datetime.now().isoformat(),
        "status": "running",
        "steps": [],
        "outputs": {},
        "statistics": {}
    }

    try:
        # Define pipeline steps
        steps = [
            (1, "Import Reviews", "src/01_import_reviews", ["--weeks-back", str(weeks_back)]),
            (2, "Classify Themes", "src/02_classify_themes", []),
            (3, "Generate Weekly Note", "src/03_generate_note", []),
            (4, "Draft Email", "src/04_draft_email", []),
            (5, "Send Email", "src/05_send_email", []),
        ]

        # Filter to specific step if requested
        if step is not None:
            if step < 1 or step > 5:
                raise ValueError(f"Invalid step number: {step}. Must be 1-5.")
            logger.info(f"Running only step {step}")
            steps = [s for s in steps if s[0] == step]

        # Add date overrides if provided
        if week_start and week_end:
            logger.info(f"Using custom date range: {week_start} to {week_end}")
            # Note: Date override logic would need to be implemented in individual scripts

        # Execute steps
        for step_num, step_name, script_path, args in steps:
            step_result = run_step(
                step_num=step_num,
                step_name=step_name,
                script_path=script_path,
                args=args,
                dry_run=dry_run
            )
            state["steps"].append(step_result)

            # Save state after each step
            save_pipeline_state(state)

        # Collect statistics
        logger.info("Collecting pipeline statistics...")
        state["statistics"] = collect_statistics(state)

        # Mark as successful
        state["status"] = "success"
        state["end_time"] = datetime.now().isoformat()

        return state

    except PipelineError as e:
        state["status"] = "failed"
        state["failed_step"] = str(e).split('(')[1].split(')')[0] if '(' in str(e) else "unknown"
        state["error"] = str(e)
        state["end_time"] = datetime.now().isoformat()

        # Get logs excerpt
        log_file = LOGS_DIR / "pipeline.log"
        logs_excerpt = ""
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                logs_excerpt = "".join(lines[-50:])  # Last 50 lines

        # Send error notification
        send_error_notification(
            failed_step=state["failed_step"],
            error_message=str(e),
            logs_excerpt=logs_excerpt
        )

        raise

    finally:
        # Calculate total duration
        if "start_time" in state and "end_time" in state:
            start = datetime.fromisoformat(state["start_time"])
            end = datetime.fromisoformat(state["end_time"])
            state["total_duration"] = (end - start).total_seconds()

        # Save final state
        save_pipeline_state(state)


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run the complete Groww app review analyzer pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Full pipeline
  python main.py --weeks-back 8           # Shorter lookback
  python main.py --dry-run                # Test without sending email
  python main.py --step 3                 # Run only note generation
  python main.py --step 5 --dry-run       # Test email sending

Steps:
  1. Import reviews from Google Play Store
  2. Classify reviews into themes using Gemini Flash
  3. Generate weekly pulse note using Gemini Pro
  4. Draft stakeholder email
  5. Send email via Gmail SMTP
        """
    )
    parser.add_argument(
        '--weeks-back',
        type=int,
        default=1,
        help='Number of weeks to look back for reviews (default: 1)'
    )
    parser.add_argument(
        '--week-start',
        type=str,
        help='Override week start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--week-end',
        type=str,
        help='Override week end date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Skip email sending (preview mode)'
    )
    parser.add_argument(
        '--step',
        type=int,
        choices=[1, 2, 3, 4, 5],
        help='Run only specific step (1-5)'
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("GROWW APP REVIEW ANALYZER PIPELINE")
    logger.info("=" * 70)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    if args.step:
        logger.info(f"Running: Step {args.step} only")
    else:
        logger.info("Running: Full pipeline (Steps 1-5)")
    logger.info("=" * 70)

    with Timer() as total_timer:
        try:
            # Run pipeline
            state = run_pipeline(
                weeks_back=args.weeks_back,
                week_start=args.week_start,
                week_end=args.week_end,
                dry_run=args.dry_run,
                step=args.step
            )

            # Print summary report
            summary = generate_summary_report(state)
            print(summary)
            logger.info(summary)

            logger.info(f"\n✓ Pipeline completed successfully in {total_timer.duration:.2f}s")
            sys.exit(0)

        except PipelineError as e:
            logger.error(f"\n✗ Pipeline failed: {str(e)}")
            logger.error(f"Total execution time: {total_timer.duration:.2f}s")

            # Load and print summary even on failure
            state = load_pipeline_state()
            if state:
                summary = generate_summary_report(state)
                print(summary)
                logger.info(summary)

            logger.error("\nTroubleshooting:")
            logger.error("1. Check logs/pipeline.log for detailed error messages")
            logger.error("2. Verify all environment variables are set in .env file")
            logger.error("3. Ensure Gemini API key has sufficient quota")
            logger.error("4. Check Gmail App Password is configured correctly")
            logger.error("5. Try running individual steps with --step flag")

            sys.exit(1)

        except Exception as e:
            logger.error(f"\n✗ Unexpected error: {str(e)}")
            logger.error(traceback.format_exc())
            sys.exit(1)


if __name__ == "__main__":
    main()
