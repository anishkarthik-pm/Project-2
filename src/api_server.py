"""
Flask API Server for Play Store Review Analyzer.

Provides REST API endpoints for the frontend dashboard.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
OUTPUTS_DIR = BASE_DIR / 'outputs'
LOGS_DIR = BASE_DIR / 'logs'


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_latest_file(directory: Path, pattern: str) -> Optional[Path]:
    """Get the most recent file matching pattern."""
    try:
        files = sorted(directory.glob(pattern))
        return files[-1] if files else None
    except Exception as e:
        logger.error(f"Error finding latest file: {e}")
        return None


def load_reviews_data() -> Dict[str, Any]:
    """Load latest classified reviews data."""
    try:
        processed_dir = DATA_DIR / 'processed'
        latest_file = get_latest_file(processed_dir, 'reviews_classified_*.csv')

        if not latest_file:
            return {
                'total': 0,
                'reviews': [],
                'date_range': 'N/A'
            }

        df = pd.read_csv(latest_file)

        # Calculate date range
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            date_range = f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}"
        else:
            date_range = 'N/A'

        # Convert to dict format
        reviews_list = []
        for _, row in df.head(100).iterrows():  # Limit to 100 most recent
            reviews_list.append({
                'text': row.get('content', ''),
                'rating': int(row.get('score', 0)),
                'date': row.get('date', '').strftime('%Y-%m-%d') if pd.notna(row.get('date')) else 'N/A',
                'theme': row.get('theme', 'Unknown'),
                'review_type': row.get('review_type', 'Unknown')
            })

        return {
            'total': len(df),
            'reviews': reviews_list,
            'date_range': date_range,
            'filename': latest_file.name
        }

    except Exception as e:
        logger.error(f"Error loading reviews: {e}")
        return {
            'total': 0,
            'reviews': [],
            'date_range': 'Error'
        }


def load_summary_data() -> Dict[str, Any]:
    """Load latest weekly summary/note data."""
    try:
        notes_dir = OUTPUTS_DIR / 'notes'
        latest_file = get_latest_file(notes_dir, 'weekly_note_*.json')

        if not latest_file:
            return {
                'available': False,
                'message': 'No summary available'
            }

        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return {
            'available': True,
            'data': data,
            'filename': latest_file.name
        }

    except Exception as e:
        logger.error(f"Error loading summary: {e}")
        return {
            'available': False,
            'message': f'Error: {str(e)}'
        }


def get_theme_distribution() -> Dict[str, int]:
    """Get theme distribution from latest classified reviews."""
    try:
        processed_dir = DATA_DIR / 'processed'
        latest_file = get_latest_file(processed_dir, 'reviews_classified_*.csv')

        if not latest_file:
            return {}

        df = pd.read_csv(latest_file)

        if 'theme' not in df.columns:
            return {}

        return df['theme'].value_counts().to_dict()

    except Exception as e:
        logger.error(f"Error getting theme distribution: {e}")
        return {}


def get_review_type_distribution() -> Dict[str, int]:
    """Get review type distribution from latest classified reviews."""
    try:
        processed_dir = DATA_DIR / 'processed'
        latest_file = get_latest_file(processed_dir, 'reviews_classified_*.csv')

        if not latest_file:
            return {}

        df = pd.read_csv(latest_file)

        if 'review_type' not in df.columns:
            return {}

        return df['review_type'].value_counts().to_dict()

    except Exception as e:
        logger.error(f"Error getting review type distribution: {e}")
        return {}


def get_statistics() -> Dict[str, Any]:
    """Get overall statistics."""
    try:
        processed_dir = DATA_DIR / 'processed'
        latest_file = get_latest_file(processed_dir, 'reviews_classified_*.csv')

        if not latest_file:
            return {
                'total_reviews': 0,
                'avg_rating': 0.0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0
            }

        df = pd.read_csv(latest_file)

        stats = {
            'total_reviews': len(df),
            'avg_rating': float(df['score'].mean()) if 'score' in df.columns else 0.0,
        }

        # Count by rating
        if 'score' in df.columns:
            stats['positive_count'] = int(len(df[df['score'] >= 4]))
            stats['negative_count'] = int(len(df[df['score'] <= 2]))
            stats['neutral_count'] = int(len(df[df['score'] == 3]))
        else:
            stats['positive_count'] = 0
            stats['negative_count'] = 0
            stats['neutral_count'] = 0

        return stats

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {
            'total_reviews': 0,
            'avg_rating': 0.0,
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0
        }


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/')
def serve_frontend():
    """Serve the frontend index.html."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    """
    GET /api/reviews

    Returns latest reviews with classifications.

    Query params:
        limit: Number of reviews to return (default: 100)
    """
    try:
        limit = int(request.args.get('limit', 100))
        data = load_reviews_data()

        # Limit reviews
        data['reviews'] = data['reviews'][:limit]

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        logger.error(f"Error in /api/reviews: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """
    GET /api/summary

    Returns latest weekly summary/pulse note.
    """
    try:
        data = load_summary_data()

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        logger.error(f"Error in /api/summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/themes', methods=['GET'])
def get_themes():
    """
    GET /api/themes

    Returns theme distribution.
    """
    try:
        distribution = get_theme_distribution()

        return jsonify({
            'success': True,
            'data': distribution
        })

    except Exception as e:
        logger.error(f"Error in /api/themes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/review-types', methods=['GET'])
def get_review_types():
    """
    GET /api/review-types

    Returns review type distribution.
    """
    try:
        distribution = get_review_type_distribution()

        return jsonify({
            'success': True,
            'data': distribution
        })

    except Exception as e:
        logger.error(f"Error in /api/review-types: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/statistics', methods=['GET'])
def api_statistics():
    """
    GET /api/statistics

    Returns overall statistics.
    """
    try:
        stats = get_statistics()

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"Error in /api/statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """
    POST /api/refresh

    Triggers the pipeline to fetch and process new data.
    """
    try:
        logger.info("Manual refresh triggered via API")

        # Run main.py in background
        cmd = [sys.executable, str(BASE_DIR / 'main.py')]

        result = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return jsonify({
            'success': True,
            'message': 'Pipeline started in background',
            'pid': result.pid
        })

    except Exception as e:
        logger.error(f"Error in /api/refresh: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the API server."""
    logger.info("=" * 60)
    logger.info("PLAY STORE REVIEW ANALYZER API SERVER")
    logger.info("=" * 60)

    # Create necessary directories
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUTS_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    # Run Flask app
    logger.info("Starting API server on http://localhost:5001")
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )


if __name__ == '__main__':
    main()
