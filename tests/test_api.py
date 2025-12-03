"""
Unit tests for Flask API server.
"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api_server import app


@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200

    data = response.get_json()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data


def test_get_reviews_endpoint(client):
    """Test GET /api/reviews endpoint."""
    response = client.get('/api/reviews')
    assert response.status_code == 200

    data = response.get_json()
    assert 'success' in data
    assert 'data' in data


def test_get_summary_endpoint(client):
    """Test GET /api/summary endpoint."""
    response = client.get('/api/summary')
    assert response.status_code == 200

    data = response.get_json()
    assert 'success' in data
    assert 'data' in data


def test_get_themes_endpoint(client):
    """Test GET /api/themes endpoint."""
    response = client.get('/api/themes')
    assert response.status_code == 200

    data = response.get_json()
    assert 'success' in data
    assert 'data' in data


def test_get_review_types_endpoint(client):
    """Test GET /api/review-types endpoint."""
    response = client.get('/api/review-types')
    assert response.status_code == 200

    data = response.get_json()
    assert 'success' in data
    assert 'data' in data


def test_get_statistics_endpoint(client):
    """Test GET /api/statistics endpoint."""
    response = client.get('/api/statistics')
    assert response.status_code == 200

    data = response.get_json()
    assert 'success' in data
    assert 'data' in data

    stats = data['data']
    assert 'total_reviews' in stats
    assert 'avg_rating' in stats
    assert 'positive_count' in stats
    assert 'negative_count' in stats


def test_post_refresh_endpoint(client):
    """Test POST /api/refresh endpoint."""
    response = client.post('/api/refresh')
    assert response.status_code == 200

    data = response.get_json()
    assert 'success' in data
    assert 'message' in data
