"""
Scheduler for automated weekly pipeline execution.

Runs the Groww Review Analyzer pipeline every Monday at 9:00 AM IST.
Can also be triggered manually via the web dashboard or CLI.
"""

import logging
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PipelineScheduler:
    """
    Manages scheduled execution of the review analysis pipeline.
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.last_run = None
        self.last_status = None
        self.current_thread = None

    def run_pipeline_async(self, dry_run=False):
        """
        Trigger pipeline execution in a background thread (non-blocking).

        Args:
            dry_run: If True, run without sending email

        Returns:
            True if started successfully, False if already running
        """
        if self.current_thread and self.current_thread.is_alive():
            logger.warning("Pipeline is already running, cannot start another instance")
            return False

        # Start pipeline in background thread
        self.current_thread = threading.Thread(
            target=self._run_pipeline_sync,
            args=(dry_run,),
            daemon=True
        )
        self.current_thread.start()
        logger.info("Pipeline started in background thread")
        return True

    def _run_pipeline_sync(self, dry_run=False):
        """
        Execute the pipeline.

        Args:
            dry_run: If True, run without sending email
        """
        logger.info("=" * 60)
        logger.info("SCHEDULED PIPELINE EXECUTION")
        logger.info("=" * 60)
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")

        try:
            # Run the pipeline
            cmd = [sys.executable, 'main.py']
            if dry_run:
                cmd.append('--dry-run')

            logger.info(f"Executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            self.last_run = datetime.now()

            if result.returncode == 0:
                self.last_status = "SUCCESS"
                logger.info("[SUCCESS] Pipeline completed successfully!")
                logger.info("Output:")
                logger.info(result.stdout)
            else:
                self.last_status = "FAILED"
                logger.error("[FAILED] Pipeline failed!")
                logger.error("STDOUT:")
                logger.error(result.stdout)
                logger.error("STDERR:")
                logger.error(result.stderr)

        except subprocess.TimeoutExpired:
            self.last_status = "TIMEOUT"
            logger.error("[TIMEOUT] Pipeline exceeded 1 hour timeout")

        except Exception as e:
            self.last_status = "ERROR"
            logger.error(f"[ERROR] Unexpected error: {str(e)}", exc_info=True)

    def schedule_weekly_run(self):
        """
        Schedule pipeline to run every Monday at 9:00 AM IST.
        """
        # Monday = 0, at 9:00 AM IST (UTC+5:30)
        trigger = CronTrigger(
            day_of_week='mon',
            hour=9,
            minute=0,
            timezone='Asia/Kolkata'
        )

        self.scheduler.add_job(
            self._run_pipeline_sync,
            trigger=trigger,
            id='weekly_pipeline',
            name='Weekly Review Analysis',
            replace_existing=True
        )

        logger.info("Scheduled: Every Monday at 9:00 AM IST")

    def start(self):
        """Start the scheduler."""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Scheduler started successfully")
            logger.info("Press Ctrl+C to stop")
        else:
            logger.warning("Scheduler is already running")

    def stop(self):
        """Stop the scheduler."""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")
        else:
            logger.warning("Scheduler is not running")

    def get_next_run_time(self):
        """Get the next scheduled run time."""
        job = self.scheduler.get_job('weekly_pipeline')
        if job:
            return job.next_run_time
        return None

    def is_pipeline_running(self):
        """Check if pipeline is currently executing."""
        return self.current_thread and self.current_thread.is_alive()

    def get_status(self):
        """Get scheduler status."""
        return {
            'is_running': self.is_running,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'last_status': self.last_status,
            'next_run': self.get_next_run_time().isoformat() if self.get_next_run_time() else None,
            'pipeline_running': self.is_pipeline_running()
        }


def main():
    """Main entry point for standalone scheduler."""
    logger.info("=" * 60)
    logger.info("GROWW REVIEW ANALYZER SCHEDULER")
    logger.info("=" * 60)

    # Create scheduler
    scheduler = PipelineScheduler()

    # Schedule weekly runs
    scheduler.schedule_weekly_run()

    # Start scheduler
    scheduler.start()

    # Display status
    next_run = scheduler.get_next_run_time()
    if next_run:
        logger.info(f"Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    try:
        # Keep running
        while True:
            import time
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("\nShutting down scheduler...")
        scheduler.stop()
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
