"""
Flask web dashboard for Groww Review Analyzer.

Provides a clean Bento-style UI with:
- Real-time pipeline status
- Chart visualizations of review themes
- Manual pipeline trigger
- Historical execution logs
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from flask import Flask, render_template, jsonify, request
from scheduler import PipelineScheduler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'groww-review-analyzer-2024'

# Initialize scheduler
scheduler = PipelineScheduler()

# Paths
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / 'logs'
DATA_DIR = BASE_DIR / 'data'
OUTPUTS_DIR = BASE_DIR / 'outputs'
STATE_FILE = LOGS_DIR / 'pipeline_state.json'


# ============================================================================
# DATA RETRIEVAL FUNCTIONS
# ============================================================================

def get_latest_note() -> Optional[Dict[str, Any]]:
    """
    Get the latest weekly note JSON.

    Returns:
        Dictionary with note data or None if not found
    """
    try:
        notes_dir = OUTPUTS_DIR / 'notes'
        json_files = sorted(notes_dir.glob('weekly_note_*.json'))

        if not json_files:
            return None

        latest_file = json_files[-1]
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Add filename for reference
        data['filename'] = latest_file.name
        return data

    except Exception as e:
        logger.error(f"Error loading latest note: {e}")
        return None


def get_pipeline_state() -> Dict[str, Any]:
    """
    Get current pipeline state.

    Returns:
        Dictionary with pipeline state or default values
    """
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                'status': 'never_run',
                'last_run': None,
                'steps': []
            }
    except Exception as e:
        logger.error(f"Error loading pipeline state: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


def get_scheduler_status() -> Dict[str, Any]:
    """
    Get scheduler status.

    Returns:
        Dictionary with scheduler info
    """
    return scheduler.get_status()


def get_review_statistics() -> Dict[str, Any]:
    """
    Get review statistics from processed data.

    Returns:
        Dictionary with review stats
    """
    try:
        # Get latest classified reviews
        processed_dir = DATA_DIR / 'processed'
        classified_files = sorted(processed_dir.glob('reviews_classified_*.csv'))

        if not classified_files:
            return {
                'total_reviews': 0,
                'date_range': 'N/A',
                'avg_rating': 0.0,
                'themes': {}
            }

        latest_file = classified_files[-1]

        # Read CSV
        import pandas as pd
        df = pd.read_csv(latest_file)

        # Calculate statistics
        stats = {
            'total_reviews': len(df),
            'date_range': f"{df['date'].min()} to {df['date'].max()}",
            'avg_rating': float(df['score'].mean()) if 'score' in df.columns else 0.0,
            'themes': {}
        }

        # Count themes
        if 'theme' in df.columns:
            theme_counts = df['theme'].value_counts().to_dict()
            stats['themes'] = theme_counts

        return stats

    except Exception as e:
        logger.error(f"Error calculating review statistics: {e}")
        return {
            'total_reviews': 0,
            'date_range': 'Error',
            'avg_rating': 0.0,
            'themes': {}
        }


def get_recent_logs(max_lines: int = 100) -> List[str]:
    """
    Get recent pipeline logs.

    Args:
        max_lines: Maximum number of log lines to return

    Returns:
        List of log lines
    """
    try:
        log_file = LOGS_DIR / 'pipeline.log'

        if not log_file.exists():
            return []

        # Try UTF-8 first, fall back to cp1252 for Windows, with error handling
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception:
            # Fall back to cp1252 (Windows encoding)
            with open(log_file, 'r', encoding='cp1252', errors='replace') as f:
                lines = f.readlines()

        # Return last N lines
        return lines[-max_lines:]

    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return [f"Error reading logs: {str(e)}"]


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Render main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """
    Get overall system status.

    Returns:
        JSON with pipeline state, scheduler status, and latest note
    """
    try:
        pipeline_state = get_pipeline_state()
        scheduler_status = get_scheduler_status()
        latest_note = get_latest_note()

        return jsonify({
            'success': True,
            'pipeline': pipeline_state,
            'scheduler': scheduler_status,
            'latest_note': latest_note
        })

    except Exception as e:
        logger.error(f"Error in /api/status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/statistics')
def api_statistics():
    """
    Get review statistics and theme distribution.

    Returns:
        JSON with review statistics
    """
    try:
        stats = get_review_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })

    except Exception as e:
        logger.error(f"Error in /api/statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logs')
def api_logs():
    """
    Get recent pipeline logs.

    Query params:
        lines: Number of lines to return (default 100)

    Returns:
        JSON with log lines
    """
    try:
        max_lines = int(request.args.get('lines', 100))
        logs = get_recent_logs(max_lines)

        return jsonify({
            'success': True,
            'logs': logs
        })

    except Exception as e:
        logger.error(f"Error in /api/logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/trigger', methods=['POST'])
def api_trigger():
    """
    Manually trigger pipeline execution.

    Request body:
        dry_run: boolean (optional, default False)

    Returns:
        JSON with trigger status
    """
    try:
        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)

        logger.info(f"Manual trigger requested (dry_run={dry_run})")

        # Check if pipeline is already running
        if scheduler.is_pipeline_running():
            return jsonify({
                'success': False,
                'error': 'Pipeline is already running'
            }), 409

        # Run pipeline in background thread (non-blocking)
        success = scheduler.run_pipeline_async(dry_run=dry_run)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to start pipeline'
            }), 500

        return jsonify({
            'success': True,
            'message': 'Pipeline started in background',
            'dry_run': dry_run
        })

    except Exception as e:
        logger.error(f"Error in /api/trigger: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scheduler/start', methods=['POST'])
def api_scheduler_start():
    """
    Start the scheduler.

    Returns:
        JSON with start status
    """
    try:
        if not scheduler.is_running:
            scheduler.schedule_weekly_run()
            scheduler.start()
            message = 'Scheduler started successfully'
        else:
            message = 'Scheduler is already running'

        return jsonify({
            'success': True,
            'message': message,
            'status': scheduler.get_status()
        })

    except Exception as e:
        logger.error(f"Error in /api/scheduler/start: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scheduler/stop', methods=['POST'])
def api_scheduler_stop():
    """
    Stop the scheduler.

    Returns:
        JSON with stop status
    """
    try:
        if scheduler.is_running:
            scheduler.stop()
            message = 'Scheduler stopped successfully'
        else:
            message = 'Scheduler is not running'

        return jsonify({
            'success': True,
            'message': message,
            'status': scheduler.get_status()
        })

    except Exception as e:
        logger.error(f"Error in /api/scheduler/stop: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Run Flask development server."""
    logger.info("=" * 60)
    logger.info("GROWW REVIEW ANALYZER DASHBOARD")
    logger.info("=" * 60)

    # Create necessary directories
    LOGS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUTS_DIR.mkdir(exist_ok=True)

    # Start scheduler
    try:
        scheduler.schedule_weekly_run()
        scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.warning(f"Could not start scheduler: {e}")

    # Run Flask app
    logger.info("Starting web dashboard on http://localhost:5000")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )


if __name__ == '__main__':
    main()
