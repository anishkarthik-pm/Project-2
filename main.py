"""Main orchestrator for the Groww app review analyzer pipeline."""

import sys
from src.config import setup_logging, validate_config

logger = setup_logging(name=__name__)


def main():
    """Execute the complete review analysis pipeline."""
    logger.info("=" * 60)
    logger.info("Starting Groww App Review Analyzer Pipeline")
    logger.info("=" * 60)

    # Validate configuration
    is_valid, missing_vars = validate_config()
    if not is_valid:
        logger.error(f"Configuration validation failed. Missing: {', '.join(missing_vars)}")
        logger.error("Please check your .env file.")
        sys.exit(1)

    try:
        # Step 1: Import reviews
        logger.info("\n[Step 1/5] Importing reviews from Google Play Store...")
        # TODO: Import 01_import_reviews module and execute

        # Step 2: Classify themes
        logger.info("\n[Step 2/5] Classifying reviews into themes...")
        # TODO: Import 02_classify_themes module and execute

        # Step 3: Generate weekly note
        logger.info("\n[Step 3/5] Generating weekly pulse note...")
        # TODO: Import 03_generate_note module and execute

        # Step 4: Draft email
        logger.info("\n[Step 4/5] Drafting stakeholder email...")
        # TODO: Import 04_draft_email module and execute

        # Step 5: Send email
        logger.info("\n[Step 5/5] Sending email to stakeholders...")
        # TODO: Import 05_send_email module and execute

        logger.info("\n" + "=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline failed with error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
