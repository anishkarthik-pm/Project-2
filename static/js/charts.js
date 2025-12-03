// ============================================================================
// GROWW REVIEW ANALYZER - DASHBOARD JAVASCRIPT
// ============================================================================

// Global state
let themeChartInstance = null;
const REFRESH_INTERVAL = 30000; // 30 seconds

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initialized');

    // Load initial data
    loadDashboardData();

    // Setup event listeners
    setupEventListeners();

    // Setup auto-refresh
    setInterval(loadDashboardData, REFRESH_INTERVAL);
});

// ============================================================================
// EVENT LISTENERS
// ============================================================================

function setupEventListeners() {
    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', () => {
        loadDashboardData();
        showToast('Dashboard refreshed');
    });

    // Trigger pipeline button
    document.getElementById('triggerBtn').addEventListener('click', () => {
        triggerPipeline(false);
    });

    // Scheduler control buttons
    document.getElementById('startSchedulerBtn').addEventListener('click', startScheduler);
    document.getElementById('stopSchedulerBtn').addEventListener('click', stopScheduler);

    // Refresh logs button
    document.getElementById('refreshLogsBtn').addEventListener('click', loadLogs);
}

// ============================================================================
// DATA LOADING
// ============================================================================

async function loadDashboardData() {
    try {
        // Load all data in parallel
        await Promise.all([
            loadStatus(),
            loadStatistics(),
            loadLogs()
        ]);

        // Update last updated time
        document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showToast('Error loading data', 'error');
    }
}

async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load status');
        }

        // Update pipeline status
        updatePipelineStatus(data.pipeline);

        // Update scheduler status
        updateSchedulerStatus(data.scheduler);

        // Update latest note
        updateLatestNote(data.latest_note);

    } catch (error) {
        console.error('Error loading status:', error);
        throw error;
    }
}

async function loadStatistics() {
    try {
        const response = await fetch('/api/statistics');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load statistics');
        }

        const stats = data.statistics;

        // Update statistics cards
        document.getElementById('totalReviews').textContent = stats.total_reviews.toLocaleString();
        document.getElementById('dateRange').textContent = stats.date_range;
        document.getElementById('avgRating').textContent = stats.avg_rating.toFixed(1);

        // Update top theme
        if (stats.themes && Object.keys(stats.themes).length > 0) {
            const themes = Object.entries(stats.themes);
            themes.sort((a, b) => b[1] - a[1]);
            const [topThemeName, topThemeCount] = themes[0];

            document.getElementById('topTheme').textContent = topThemeName;
            document.getElementById('topThemeCount').textContent = `${topThemeCount} reviews`;
        } else {
            document.getElementById('topTheme').textContent = 'N/A';
            document.getElementById('topThemeCount').textContent = '0 reviews';
        }

        // Update theme chart
        updateThemeChart(stats.themes);

    } catch (error) {
        console.error('Error loading statistics:', error);
        throw error;
    }
}

async function loadLogs() {
    try {
        const response = await fetch('/api/logs?lines=50');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load logs');
        }

        const logsContainer = document.getElementById('logsContainer');

        if (data.logs.length === 0) {
            logsContainer.innerHTML = '<p class="loading-text">No logs available</p>';
        } else {
            // Display last 50 lines
            logsContainer.innerHTML = data.logs
                .map(line => `<div class="log-line">${escapeHtml(line.trim())}</div>`)
                .join('');

            // Scroll to bottom
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }

    } catch (error) {
        console.error('Error loading logs:', error);
        const logsContainer = document.getElementById('logsContainer');
        logsContainer.innerHTML = '<p class="loading-text">Error loading logs</p>';
    }
}

// ============================================================================
// UI UPDATES
// ============================================================================

function updatePipelineStatus(pipeline) {
    const statusBadge = document.getElementById('statusBadge');
    const lastRun = document.getElementById('lastRun');
    const duration = document.getElementById('duration');
    const stepsContainer = document.getElementById('stepsContainer');

    // Update status badge
    statusBadge.textContent = pipeline.status || 'Unknown';
    statusBadge.className = 'status-badge';

    switch (pipeline.status) {
        case 'success':
            statusBadge.classList.add('success');
            break;
        case 'running':
            statusBadge.classList.add('running');
            break;
        case 'failed':
        case 'error':
            statusBadge.classList.add('failed');
            break;
        default:
            statusBadge.classList.add('idle');
    }

    // Update last run
    if (pipeline.start_time) {
        const date = new Date(pipeline.start_time);
        lastRun.textContent = date.toLocaleString();
    } else {
        lastRun.textContent = 'Never';
    }

    // Update duration
    if (pipeline.total_duration) {
        duration.textContent = `${pipeline.total_duration.toFixed(2)}s`;
    } else {
        duration.textContent = 'N/A';
    }

    // Update steps
    if (pipeline.steps && pipeline.steps.length > 0) {
        stepsContainer.innerHTML = pipeline.steps
            .map(step => createStepElement(step))
            .join('');
    } else {
        stepsContainer.innerHTML = '<p class="loading-text">No pipeline runs yet</p>';
    }
}

function createStepElement(step) {
    let icon = '';
    switch (step.status) {
        case 'success':
            icon = '<span style="color: var(--color-success);">[SUCCESS]</span>';
            break;
        case 'failed':
        case 'error':
            icon = '<span style="color: var(--color-danger);">[FAILED]</span>';
            break;
        case 'running':
            icon = '<span style="color: var(--color-info);">[RUNNING]</span>';
            break;
        default:
            icon = '<span style="color: var(--color-text-secondary);">[SKIP]</span>';
    }

    const durationText = step.duration ? `${step.duration.toFixed(2)}s` : 'N/A';

    return `
        <div class="step">
            <div class="step-icon">${icon}</div>
            <div class="step-name">Step ${step.step}: ${step.name}</div>
            <div class="step-duration">${durationText}</div>
        </div>
    `;
}

function updateSchedulerStatus(scheduler) {
    const schedulerStatus = document.getElementById('schedulerStatus');
    const nextRun = document.getElementById('nextRun');

    // Update status
    if (scheduler.is_running) {
        schedulerStatus.textContent = 'Running';
        schedulerStatus.style.color = 'var(--color-success)';
    } else {
        schedulerStatus.textContent = 'Stopped';
        schedulerStatus.style.color = 'var(--color-text-secondary)';
    }

    // Update next run
    if (scheduler.next_run) {
        const date = new Date(scheduler.next_run);
        nextRun.textContent = date.toLocaleString();
    } else {
        nextRun.textContent = 'Not scheduled';
    }
}

function updateLatestNote(note) {
    const noteDate = document.getElementById('noteDate');
    const noteContent = document.getElementById('noteContent');

    if (!note) {
        noteContent.innerHTML = '<p class="loading-text">No weekly note available</p>';
        noteDate.textContent = 'N/A';
        return;
    }

    // Update date
    noteDate.textContent = note.date_range || 'Unknown date';

    // Build note HTML
    let html = `<h3>Weekly Review Pulse</h3>`;
    html += `<p><strong>Total Reviews:</strong> ${note.total_reviews || 0}</p>`;

    if (note.themes) {
        html += `<h3 style="margin-top: 1rem;">Top Themes:</h3>`;

        // Sort themes by count
        const themes = Object.entries(note.themes);
        themes.sort((a, b) => b[1].count - a[1].count);

        themes.forEach(([themeName, themeData]) => {
            html += `
                <div class="theme-section">
                    <div class="theme-header">
                        <span class="theme-name">${escapeHtml(themeName)}</span>
                        <span class="theme-count">${themeData.count} reviews</span>
                    </div>
                    <div class="theme-summary">${escapeHtml(themeData.summary || 'No summary')}</div>
                </div>
            `;
        });
    }

    noteContent.innerHTML = html;
}

function updateThemeChart(themes) {
    const canvas = document.getElementById('themeChart');

    if (!themes || Object.keys(themes).length === 0) {
        // No data - show message
        canvas.style.display = 'none';
        canvas.parentElement.innerHTML += '<p class="loading-text">No theme data available</p>';
        return;
    }

    canvas.style.display = 'block';

    // Prepare data
    const themeEntries = Object.entries(themes);
    themeEntries.sort((a, b) => b[1] - a[1]);

    const labels = themeEntries.map(([name]) => name);
    const data = themeEntries.map(([, count]) => count);

    // Color palette
    const colors = [
        '#00D09C',
        '#5F5AF6',
        '#F59E0B',
        '#EF4444',
        '#10B981',
        '#3B82F6',
        '#8B5CF6',
        '#EC4899'
    ];

    const backgroundColors = colors.slice(0, data.length).map(color => color + '40');
    const borderColors = colors.slice(0, data.length);

    // Destroy existing chart
    if (themeChartInstance) {
        themeChartInstance.destroy();
    }

    // Create new chart
    themeChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Review Count',
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
                    titleFont: {
                        size: 14,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 13
                    },
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
                        }
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

// ============================================================================
// ACTIONS
// ============================================================================

async function triggerPipeline(dryRun = false) {
    try {
        // Show loading overlay
        document.getElementById('loadingOverlay').classList.add('active');

        const response = await fetch('/api/trigger', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ dry_run: dryRun })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to trigger pipeline');
        }

        showToast('Pipeline started successfully');

        // Refresh data after 2 seconds
        setTimeout(() => {
            loadDashboardData();
            document.getElementById('loadingOverlay').classList.remove('active');
        }, 2000);

    } catch (error) {
        console.error('Error triggering pipeline:', error);
        showToast('Error: ' + error.message, 'error');
        document.getElementById('loadingOverlay').classList.remove('active');
    }
}

async function startScheduler() {
    try {
        const response = await fetch('/api/scheduler/start', {
            method: 'POST'
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to start scheduler');
        }

        showToast(data.message);
        loadStatus();

    } catch (error) {
        console.error('Error starting scheduler:', error);
        showToast('Error: ' + error.message, 'error');
    }
}

async function stopScheduler() {
    try {
        const response = await fetch('/api/scheduler/stop', {
            method: 'POST'
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to stop scheduler');
        }

        showToast(data.message);
        loadStatus();

    } catch (error) {
        console.error('Error stopping scheduler:', error);
        showToast('Error: ' + error.message, 'error');
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
