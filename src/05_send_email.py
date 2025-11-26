"""Step 5: Send email draft via Gmail SMTP with delivery logging."""

import argparse
import smtplib
import ssl
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from src.config import (
    EMAILS_DIR,
    LOGS_DIR,
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
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465  # SSL port
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_email_credentials() -> Dict[str, str]:
    """
    Load email credentials from environment variables.

    Returns:
        Dictionary with email_from, email_password, email_to

    Raises:
        ValueError: If required environment variables are not set
    """
    import os
    from dotenv import load_dotenv

    # Load .env file
    load_dotenv()

    email_from = os.getenv('EMAIL_FROM')
    email_password = os.getenv('EMAIL_PASSWORD')
    email_to = os.getenv('EMAIL_TO')

    # Validate credentials
    missing = []
    if not email_from:
        missing.append('EMAIL_FROM')
    if not email_password:
        missing.append('EMAIL_PASSWORD')
    if not email_to:
        missing.append('EMAIL_TO')

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please set them in .env file or environment.\n\n"
            f"For EMAIL_PASSWORD, use a Gmail App Password:\n"
            f"1. Go to Google Account settings\n"
            f"2. Security → 2-Step Verification (enable if not already)\n"
            f"3. Security → App Passwords\n"
            f"4. Generate new app password for 'Mail'\n"
            f"5. Use the 16-character password in .env file"
        )

    logger.info(f"Loaded credentials: FROM={email_from}, TO={email_to}")

    return {
        'email_from': email_from,
        'email_password': email_password,
        'email_to': email_to,
    }


# ============================================================================
# INPUT HANDLING
# ============================================================================

def get_latest_email_file() -> Path:
    """
    Get the most recent email draft file from outputs/emails directory.

    Returns:
        Path to latest email file

    Raises:
        FileNotFoundError: If no email files found
    """
    email_files = sorted(EMAILS_DIR.glob("email_draft_*.txt"))

    if not email_files:
        raise FileNotFoundError(f"No email files found in {EMAILS_DIR}")

    latest_file = email_files[-1]
    logger.info(f"Found latest email file: {latest_file}")

    return latest_file


def parse_email_file(file_path: Path) -> Tuple[str, str]:
    """
    Parse email file to extract subject and body.

    Expected format:
        Subject: [subject line]

        [email body]

    Args:
        file_path: Path to email draft file

    Returns:
        Tuple of (subject, body)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Email file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse subject line
    if not content.startswith('Subject: '):
        raise ValueError(f"Email file missing 'Subject:' line: {file_path}")

    lines = content.split('\n', 1)
    if len(lines) != 2:
        raise ValueError(f"Email file format invalid: {file_path}")

    subject_line = lines[0]
    body = lines[1].strip()

    # Extract subject
    subject = subject_line.replace('Subject: ', '', 1).strip()

    if not subject:
        raise ValueError(f"Email subject is empty: {file_path}")

    if not body:
        raise ValueError(f"Email body is empty: {file_path}")

    logger.info(f"Parsed email: subject='{subject[:50]}...', body_length={len(body)}")

    return subject, body


# ============================================================================
# EMAIL CREATION
# ============================================================================

def create_email_message(
    subject: str,
    body: str,
    from_addr: str,
    to_addr: str
) -> MIMEText:
    """
    Create MIME email message.

    Args:
        subject: Email subject line
        body: Email body text
        from_addr: Sender email address
        to_addr: Recipient email address

    Returns:
        MIMEText message object
    """
    # Create message
    msg = MIMEText(body, 'plain', 'utf-8')

    # Set headers
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Date'] = formatdate(localtime=True)

    logger.debug(f"Created email message: {len(body)} bytes")

    return msg


# ============================================================================
# SMTP OPERATIONS
# ============================================================================

def validate_smtp_credentials(
    email_from: str,
    email_password: str
) -> bool:
    """
    Validate SMTP credentials without sending email.

    Args:
        email_from: Sender email address
        email_password: Sender email password (app password)

    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=10) as server:
            server.login(email_from, email_password)
            logger.info("SMTP credentials validated successfully")
            return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {str(e)}")
        logger.error(
            "Gmail App Password required. See README for instructions:\n"
            "1. Enable 2-Step Verification in Google Account\n"
            "2. Generate App Password for Mail\n"
            "3. Use 16-character password in EMAIL_PASSWORD"
        )
        return False

    except Exception as e:
        logger.error(f"SMTP validation error: {str(e)}")
        return False


def send_email_smtp(
    message: MIMEText,
    email_from: str,
    email_password: str,
    email_to: str,
    max_retries: int = MAX_RETRIES
) -> Tuple[bool, Optional[str]]:
    """
    Send email via Gmail SMTP with retry logic.

    Args:
        message: MIMEText message to send
        email_from: Sender email address
        email_password: Sender email password (app password)
        email_to: Recipient email address
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Sending email (attempt {attempt}/{max_retries})")

            # Create SSL context
            context = ssl.create_default_context()

            with Timer() as t:
                # Connect to SMTP server
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=30) as server:
                    # Enable debug logging if needed
                    # server.set_debuglevel(1)

                    # Login
                    server.login(email_from, email_password)
                    logger.debug("SMTP login successful")

                    # Send email
                    server.send_message(message)
                    logger.debug("Email sent via SMTP")

            logger.info(f"Email sent successfully in {t.duration:.2f}s")
            return True, None

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {str(e)}"
            logger.error(error_msg)
            logger.error(
                "Use Gmail App Password (not regular password):\n"
                "1. Google Account → Security → 2-Step Verification\n"
                "2. Security → App Passwords → Generate for Mail"
            )
            return False, error_msg

        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"Recipient refused: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except smtplib.SMTPSenderRefused as e:
            error_msg = f"Sender refused: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except smtplib.SMTPDataError as e:
            error_msg = f"SMTP data error: {str(e)}"
            logger.error(error_msg)

            # Check for rate limiting
            if '421' in str(e) or 'rate limit' in str(e).lower():
                logger.warning("Rate limiting detected, will retry with longer delay")
                if attempt < max_retries:
                    wait_time = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

            return False, error_msg

        except (smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError) as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(f"Attempt {attempt}: {error_msg}")

            if attempt < max_retries:
                wait_time = RETRY_BASE_DELAY ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Attempt {attempt}: {error_msg}", exc_info=True)

            if attempt < max_retries:
                wait_time = RETRY_BASE_DELAY ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                return False, error_msg

    return False, f"All {max_retries} attempts failed"


# ============================================================================
# DELIVERY LOGGING
# ============================================================================

def log_email_delivery(
    recipient: str,
    subject: str,
    status: str,
    error: Optional[str] = None
) -> None:
    """
    Log email delivery to logs/email_sent.log.

    Format: timestamp | recipient | subject | status | error_if_any

    Args:
        recipient: Email recipient
        subject: Email subject
        status: Delivery status (SUCCESS or FAILED)
        error: Error message if delivery failed
    """
    log_path = LOGS_DIR / "email_sent.log"
    ensure_dir_exists(log_path.parent)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Truncate subject if too long
    subject_truncated = subject[:100] + "..." if len(subject) > 100 else subject

    # Format log entry
    error_str = error if error else "N/A"
    log_entry = f"{timestamp} | {recipient} | {subject_truncated} | {status} | {error_str}\n"

    # Append to log file
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(log_entry)

    logger.info(f"Delivery logged to: {log_path}")


# ============================================================================
# DRY RUN MODE
# ============================================================================

def preview_email(message: MIMEText, credentials: Dict[str, str]) -> None:
    """
    Preview email in console without sending.

    Args:
        message: MIMEText message
        credentials: Email credentials dictionary
    """
    print("\n" + "=" * 70)
    print("EMAIL PREVIEW (DRY RUN MODE)")
    print("=" * 70)
    print(f"From: {credentials['email_from']}")
    print(f"To: {credentials['email_to']}")
    print(f"Subject: {message['Subject']}")
    print(f"Date: {message['Date']}")
    print("-" * 70)
    print(message.get_payload())
    print("=" * 70 + "\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Send email draft via Gmail SMTP with delivery logging'
    )
    parser.add_argument(
        '--email-file',
        type=str,
        help='Path to specific email file (default: latest from outputs/emails/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview email and validate credentials without sending'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Email Sender")
    logger.info("=" * 60)

    with Timer() as total_timer:
        try:
            # Step 1: Load credentials
            log_pipeline_step(logger, "Load Credentials", "START")
            with Timer() as t:
                credentials = load_email_credentials()

            log_pipeline_step(
                logger, "Load Credentials", "SUCCESS",
                duration=t.duration
            )

            # Step 2: Load email file
            log_pipeline_step(logger, "Load Email File", "START")
            with Timer() as t:
                if args.email_file:
                    email_path = Path(args.email_file)
                else:
                    email_path = get_latest_email_file()

                subject, body = parse_email_file(email_path)

            log_pipeline_step(
                logger, "Load Email File", "SUCCESS",
                duration=t.duration,
                metadata={"file": email_path.name}
            )

            # Step 3: Create email message
            log_pipeline_step(logger, "Create Email Message", "START")
            with Timer() as t:
                message = create_email_message(
                    subject=subject,
                    body=body,
                    from_addr=credentials['email_from'],
                    to_addr=credentials['email_to']
                )

            log_pipeline_step(
                logger, "Create Email Message", "SUCCESS",
                duration=t.duration,
                metadata={"size": len(body)}
            )

            if args.dry_run:
                # Dry run mode
                log_pipeline_step(logger, "Validate SMTP Credentials", "START")
                with Timer() as t:
                    is_valid = validate_smtp_credentials(
                        credentials['email_from'],
                        credentials['email_password']
                    )

                if is_valid:
                    log_pipeline_step(
                        logger, "Validate SMTP Credentials", "SUCCESS",
                        duration=t.duration
                    )

                    # Preview email
                    preview_email(message, credentials)
                    print("✓ SMTP credentials validated")
                    print("✓ Email would be sent successfully")

                else:
                    log_pipeline_step(
                        logger, "Validate SMTP Credentials", "FAILED",
                        duration=t.duration
                    )
                    print("✗ SMTP credentials validation failed")
                    print("  Check logs for details")

            else:
                # Send email
                log_pipeline_step(logger, "Send Email", "START")
                with Timer() as t:
                    success, error = send_email_smtp(
                        message=message,
                        email_from=credentials['email_from'],
                        email_password=credentials['email_password'],
                        email_to=credentials['email_to']
                    )

                if success:
                    log_pipeline_step(
                        logger, "Send Email", "SUCCESS",
                        duration=t.duration
                    )

                    # Log delivery
                    log_email_delivery(
                        recipient=credentials['email_to'],
                        subject=subject,
                        status="SUCCESS"
                    )

                    print(f"\n✓ Email sent successfully to {credentials['email_to']}")
                    print(f"  Subject: {subject}")

                else:
                    log_pipeline_step(
                        logger, "Send Email", "FAILED",
                        duration=t.duration
                    )

                    # Log delivery failure
                    log_email_delivery(
                        recipient=credentials['email_to'],
                        subject=subject,
                        status="FAILED",
                        error=error
                    )

                    print(f"\n✗ Email sending failed: {error}")
                    raise Exception(f"Email delivery failed: {error}")

        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}", exc_info=True)
            log_pipeline_step(logger, "Email Sender", "FAILED")
            raise

    logger.info(f"Total execution time: {total_timer.duration:.2f}s")
    logger.info("Email sender completed successfully!")


if __name__ == "__main__":
    main()
