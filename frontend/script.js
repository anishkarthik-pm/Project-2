// ============================================================================
// PLAY STORE REVIEW ANALYZER - FRONTEND JAVASCRIPT
// ============================================================================

// API Configuration
const API_BASE = 'http://localhost:5001/api';
const REFRESH_INTERVAL = 60000; // 60 seconds

// Chart instances
let reviewTypeChartInstance = null;
let themeChartInstance = null;

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initialized');

    // Load initial data
    loadAllData();

    // Setup event listeners
    setupEventListeners();

    // Setup auto-refresh
    setInterval(loadAllData, REFRESH_INTERVAL);
});

// ============================================================================
// EVENT LISTENERS
// ============================================================================

function setupEventListeners() {
    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', refreshData);
}

// ============================================================================
// DATA LOADING
// ============================================================================

async function loadAllData() {
    try {
        await Promise.all([
            loadStatistics(),
            loadReviews(),
            loadThemes(),
            loadReviewTypes(),
            loadSummary()
        ]);

        // Update last updated time
        document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();

    } catch (error) {
        console.error('Error loading data:', error);
        showToast('Error loading data', 'error');
    }
}

async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE}/statistics`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load statistics');
        }

        const stats = data.data;

        // Update UI
        document.getElementById('totalReviews').textContent = stats.total_reviews.toLocaleString();
        document.getElementById('avgRating').textContent = stats.avg_rating.toFixed(1);
        document.getElementById('positiveCount').textContent = stats.positive_count;
        document.getElementById('negativeCount').textContent = stats.negative_count;

    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

async function loadReviews() {
    try {
        const response = await fetch(`${API_BASE}/reviews?limit=20`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load reviews');
        }

        const reviewsData = data.data;

        // Update date range
        document.getElementById('dateRange').textContent = reviewsData.date_range;
        document.getElementById('reviewCount').textContent = reviewsData.reviews.length;

        // Render reviews
        renderReviews(reviewsData.reviews);

    } catch (error) {
        console.error('Error loading reviews:', error);
        document.getElementById('reviewsTable').innerHTML = '<p class="loading-text">Error loading reviews</p>';
    }
}

async function loadThemes() {
    try {
        const response = await fetch(`${API_BASE}/themes`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load themes');
        }

        updateThemeChart(data.data);

    } catch (error) {
        console.error('Error loading themes:', error);
    }
}

async function loadReviewTypes() {
    try {
        const response = await fetch(`${API_BASE}/review-types`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load review types');
        }

        updateReviewTypeChart(data.data);

    } catch (error) {
        console.error('Error loading review types:', error);
    }
}

async function loadSummary() {
    try {
        const response = await fetch(`${API_BASE}/summary`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load summary');
        }

        renderSummary(data.data);

    } catch (error) {
        console.error('Error loading summary:', error);
        document.getElementById('insightsContent').innerHTML = '<p class="loading-text">No insights available</p>';
    }
}

// ============================================================================
// UI UPDATES
// ============================================================================

function renderReviews(reviews) {
    const container = document.getElementById('reviewsTable');

    if (!reviews || reviews.length === 0) {
        container.innerHTML = '<p class="loading-text">No reviews available</p>';
        return;
    }

    let html = '';

    reviews.forEach(review => {
        const stars = '★'.repeat(review.rating) + '☆'.repeat(5 - review.rating);

        html += `
            <div class="review-item">
                <div class="review-header">
                    <div class="review-rating">
                        ${stars}
                    </div>
                    <span class="review-date">${review.date}</span>
                </div>
                <div class="review-text">${escapeHtml(review.text)}</div>
                <div class="review-meta">
                    <span class="review-tag">${review.review_type || 'Unknown'}</span>
                    <span class="review-tag theme">${review.theme || 'Unknown'}</span>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function renderSummary(summaryData) {
    const container = document.getElementById('insightsContent');

    if (!summaryData.available) {
        container.innerHTML = '<p class="loading-text">No insights available</p>';
        return;
    }

    const data = summaryData.data;
    let html = '<div class="insights-content">';

    // Add key themes if available
    if (data.themes) {
        const themes = Object.entries(data.themes);
        themes.sort((a, b) => b[1].count - a[1].count);

        themes.slice(0, 3).forEach(([themeName, themeData]) => {
            html += `
                <div class="insight-item">
                    <div class="insight-title">${themeName} (${themeData.count} reviews)</div>
                    <div class="insight-text">${escapeHtml(themeData.summary || 'No summary available')}</div>
                </div>
            `;
        });
    } else {
        html += '<p class="loading-text">No theme insights available</p>';
    }

    html += '</div>';
    container.innerHTML = html;
}

function updateReviewTypeChart(distribution) {
    const canvas = document.getElementById('reviewTypeChart');

    if (!distribution || Object.keys(distribution).length === 0) {
        canvas.parentElement.innerHTML += '<p class="loading-text">No review type data available</p>';
        canvas.style.display = 'none';
        return;
    }

    canvas.style.display = 'block';

    // Prepare data
    const entries = Object.entries(distribution);
    entries.sort((a, b) => b[1] - a[1]);

    const labels = entries.map(([name]) => name);
    const data = entries.map(([, count]) => count);

    // Color palette
    const colors = [
        '#4A6CF7', '#10B981', '#F59E0B', '#EF4444',
        '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
    ];

    const backgroundColors = colors.slice(0, data.length).map(color => color + '40');
    const borderColors = colors.slice(0, data.length);

    // Destroy existing chart
    if (reviewTypeChartInstance) {
        reviewTypeChartInstance.destroy();
    }

    // Create new chart
    reviewTypeChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Count',
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 2,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y} reviews`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            size: 11
                        },
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        font: {
                            size: 11
                        },
                        precision: 0
                    }
                }
            }
        }
    });
}

function updateThemeChart(distribution) {
    const canvas = document.getElementById('themeChart');

    if (!distribution || Object.keys(distribution).length === 0) {
        canvas.parentElement.innerHTML += '<p class="loading-text">No theme data available</p>';
        canvas.style.display = 'none';
        return;
    }

    canvas.style.display = 'block';

    // Prepare data
    const entries = Object.entries(distribution);
    entries.sort((a, b) => b[1] - a[1]);

    const labels = entries.map(([name]) => name);
    const data = entries.map(([, count]) => count);

    // Color palette
    const colors = [
        '#4A6CF7', '#10B981', '#F59E0B', '#EF4444',
        '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
    ];

    const backgroundColors = colors.slice(0, data.length);

    // Destroy existing chart
    if (themeChartInstance) {
        themeChartInstance.destroy();
    }

    // Create new chart
    themeChartInstance = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// ============================================================================
// ACTIONS
// ============================================================================

async function refreshData() {
    try {
        // Show loading overlay
        document.getElementById('loadingOverlay').classList.add('active');

        const response = await fetch(`${API_BASE}/refresh`, {
            method: 'POST'
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to refresh data');
        }

        showToast('Pipeline started! Data will be refreshed in a few minutes.');

        // Hide overlay after 3 seconds
        setTimeout(() => {
            document.getElementById('loadingOverlay').classList.remove('active');
            loadAllData();
        }, 3000);

    } catch (error) {
        console.error('Error refreshing data:', error);
        showToast('Error: ' + error.message, 'error');
        document.getElementById('loadingOverlay').classList.remove('active');
    }
}

// ============================================================================
// UTILITIES
// ============================================================================

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');

    toastMessage.textContent = message;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
