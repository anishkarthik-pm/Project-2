#!/usr/bin/env python3
"""
CLI Utility for Play Store Review Analyzer.

Provides command-line interface for running individual pipeline steps.
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent


def run_command(script_name: str, args: list = None) -> int:
    """
    Run a Python script as a subprocess.

    Args:
        script_name: Name of the script (e.g., '01_import_reviews.py')
        args: Additional command-line arguments

    Returns:
        Exit code
    """
    cmd = [sys.executable, '-m', f'src.{script_name.replace(".py", "")}']

    if args:
        cmd.extend(args)

    logger.info(f"Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            check=True,
            capture_output=False
        )
        return result.returncode

    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        return e.returncode

    except Exception as e:
        logger.error(f"Error running command: {e}")
        return 1


def cmd_fetch(args):
    """Fetch reviews from Google Play Store."""
    logger.info("=" * 60)
    logger.info("FETCH REVIEWS")
    logger.info("=" * 60)

    cmd_args = []
    if args.weeks:
        cmd_args.extend(['--weeks-back', str(args.weeks)])

    return run_command('01_import_reviews.py', cmd_args)


def cmd_classify(args):
    """Classify reviews into themes and types."""
    logger.info("=" * 60)
    logger.info("CLASSIFY REVIEWS")
    logger.info("=" * 60)

    return run_command('02_classify_themes.py')


def cmd_summary(args):
    """Generate weekly summary note."""
    logger.info("=" * 60)
    logger.info("GENERATE SUMMARY")
    logger.info("=" * 60)

    cmd_args = []
    if args.no_date_filter:
        cmd_args.append('--no-date-filter')

    return run_command('03_generate_note.py', cmd_args)


def cmd_email(args):
    """Draft and optionally send email."""
    logger.info("=" * 60)
    logger.info("EMAIL OPERATIONS")
    logger.info("=" * 60)

    # Draft email
    exit_code = run_command('04_draft_email.py')

    if exit_code != 0:
        logger.error("Email draft failed")
        return exit_code

    # Send email if requested
    if args.send:
        cmd_args = []
        if args.dry_run:
            cmd_args.append('--dry-run')

        return run_command('05_send_email.py', cmd_args)

    return 0


def cmd_full_run(args):
    """Run the complete pipeline."""
    logger.info("=" * 60)
    logger.info("FULL PIPELINE RUN")
    logger.info("=" * 60)

    cmd_args = []
    if args.dry_run:
        cmd_args.append('--dry-run')
    if args.weeks:
        cmd_args.extend(['--weeks-back', str(args.weeks)])

    return run_command('main.py', cmd_args)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Play Store Review Analyzer CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch reviews from last 2 weeks
  python src/cli.py fetch --weeks 2

  # Classify reviews
  python src/cli.py classify

  # Generate summary without date filter
  python src/cli.py summary --no-date-filter

  # Draft and send email
  python src/cli.py email --send

  # Run full pipeline
  python src/cli.py full-run

  # Run full pipeline (dry run, no email sent)
  python src/cli.py full-run --dry-run
        """
    )

    subparsers = parser.add_subparsers(title='commands', dest='command', required=True)

    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch reviews from Play Store')
    fetch_parser.add_argument(
        '--weeks',
        type=int,
        default=1,
        help='Number of weeks to look back (default: 1)'
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # Classify command
    classify_parser = subparsers.add_parser('classify', help='Classify reviews into themes and types')
    classify_parser.set_defaults(func=cmd_classify)

    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Generate weekly summary note')
    summary_parser.add_argument(
        '--no-date-filter',
        action='store_true',
        help='Disable date filtering (use all reviews)'
    )
    summary_parser.set_defaults(func=cmd_summary)

    # Email command
    email_parser = subparsers.add_parser('email', help='Draft and optionally send email')
    email_parser.add_argument(
        '--send',
        action='store_true',
        help='Send the email after drafting'
    )
    email_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate credentials without sending'
    )
    email_parser.set_defaults(func=cmd_email)

    # Full run command
    full_parser = subparsers.add_parser('full-run', help='Run the complete pipeline')
    full_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run pipeline without sending email'
    )
    full_parser.add_argument(
        '--weeks',
        type=int,
        default=1,
        help='Number of weeks to look back (default: 1)'
    )
    full_parser.set_defaults(func=cmd_full_run)

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    try:
        exit_code = args.func(args)
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
