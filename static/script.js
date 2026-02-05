// Dashboard JavaScript

let viewsChart = null;
let watchTimeChart = null;

// Helper to create skeleton row for table
const getSkeletonRow = () => `
    <tr>
        <td><div class="skeleton skeleton-text" style="width: 80%"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 60%"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 50%"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 40%"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 70%"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 60%; border-radius: 12px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 30%"></div></td>
    </tr>
`;

// Refresh stats and uploads data
async function refreshData() {
    // We don't show skeletons on every auto-refresh to avoid flicker
    // but we do on manual refresh or first load
    const isInitial = document.querySelectorAll('.skeleton').length > 0;

    await Promise.all([
        loadStats(),
        loadUploads(isInitial),
        loadAnalytics(isInitial)
    ]);
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        // Update stats
        document.getElementById('total-clips').textContent = data.total_clips || 0;
        document.getElementById('uploaded-clips').textContent = data.uploaded || 0;
        document.getElementById('pending-clips').textContent = data.pending || 0;
        document.getElementById('failed-clips').textContent = data.failed || 0;

        // Update YouTube connection status
        updateYouTubeStatus(data.youtube_connected);

        // Toggle visibility of cleanup buttons based on stats
        document.getElementById('cleanup-pending-btn').style.display = data.pending > 0 ? 'inline-flex' : 'none';
        document.getElementById('cleanup-failed-btn').style.display = data.failed > 0 ? 'inline-flex' : 'none';

    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Update YouTube connection status
function updateYouTubeStatus(connected) {
    const statusHero = document.getElementById('youtube-status');
    const statusIcon = document.getElementById('status-icon');
    const statusTitle = document.getElementById('status-title');
    const statusDescription = document.getElementById('status-description');
    const actionBtn = document.getElementById('youtube-action-btn');
    const analyticsSection = document.getElementById('analytics-section');

    if (connected) {
        statusHero.classList.add('connected');
        statusIcon.textContent = '✅';
        statusTitle.textContent = 'YouTube Connected';
        statusDescription.textContent = 'Automatic uploads are active. Your Twitch clips will be posted to YouTube.';
        actionBtn.textContent = 'Disconnect';
        actionBtn.className = 'btn btn-danger btn-sm';
        actionBtn.onclick = disconnectYouTube;
        analyticsSection.style.display = 'block';
    } else {
        statusHero.classList.remove('connected');
        statusIcon.textContent = '❌';
        statusTitle.textContent = 'YouTube Not Connected';
        statusDescription.textContent = 'Enable automatic uploads by linking your YouTube account.';
        actionBtn.textContent = 'Connect YouTube';
        actionBtn.className = 'btn btn-primary btn-sm';
        actionBtn.onclick = connectYouTube;
        analyticsSection.style.display = 'none';
    }
}

// Connect to YouTube
function connectYouTube() {
    window.location.href = '/auth/youtube';
}

// Disconnect from YouTube
async function disconnectYouTube() {
    if (!confirm('Are you sure you want to disconnect YouTube?')) {
        return;
    }

    try {
        const response = await fetch('/api/disconnect', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            await refreshData();
        } else {
            alert('Failed to disconnect: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error disconnecting:', error);
        alert('Failed to disconnect from YouTube');
    }
}

// Load YouTube Analytics
async function loadAnalytics(showSkeleton = false) {
    const statusHero = document.getElementById('youtube-status');
    if (!statusHero.classList.contains('connected')) {
        return;
    }

    if (showSkeleton) {
        // Reset to skeletons
        const elements = ['analytics-views', 'analytics-watchtime', 'analytics-avgduration', 'analytics-subscribers'];
        elements.forEach(id => {
            document.getElementById(id).innerHTML = '<div class="skeleton skeleton-value" style="margin-inline:auto"></div>';
        });
        document.getElementById('views-chart-container').querySelector('.skeleton').style.display = 'block';
        document.getElementById('watchtime-chart-container').querySelector('.skeleton').style.display = 'block';
    }

    const days = document.getElementById('analytics-days').value;
    try {
        const response = await fetch(`/api/analytics?days=${days}`);
        const data = await response.json();

        if (data.error) {
            console.warn('Analytics error:', data.error);
            const summaryDiv = document.getElementById('analytics-summary');
            summaryDiv.innerHTML = `<div style="grid-column: 1 / -1; padding: 20px; text-align: center; color: var(--error); background: #fef2f2; border-radius: 6px; font-size: 14px; border: 1px solid #fee2e2;">
                ⚠️ ${data.error}
            </div>`;
            return;
        }

        renderAnalytics(data);
    } catch (error) {
        console.error('Error loading analytics:', error);
    } finally {
        // Hide chart skeletons
        document.getElementById('views-chart-container').querySelector('.skeleton').style.display = 'none';
        document.getElementById('watchtime-chart-container').querySelector('.skeleton').style.display = 'none';
    }
}

function renderAnalytics(data) {
    const { summary, timeSeries } = data;

    // Update summary values
    if (summary) {
        document.getElementById('analytics-views').textContent = (summary.totalViews || 0).toLocaleString();
        document.getElementById('analytics-watchtime').textContent = (summary.totalWatchTime || 0).toLocaleString();
        document.getElementById('analytics-avgduration').textContent = Math.round(summary.avgViewDuration || 0);
        document.getElementById('analytics-subscribers').textContent = (summary.subscribersGained || 0).toLocaleString();
    }

    // Render Charts
    renderTimeSeriesChart('views-chart', 'Views', timeSeries.labels, timeSeries.views, '#f38020', viewsChart, (c) => viewsChart = c);
    renderTimeSeriesChart('watchtime-chart', 'Watch Time (mins)', timeSeries.labels, timeSeries.watchTime, '#0051c3', watchTimeChart, (c) => watchTimeChart = c);
}

function renderTimeSeriesChart(canvasId, label, labels, data, color, chartInstance, setInstance) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    if (chartInstance) {
        chartInstance.destroy();
    }

    const newChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(l => {
                const d = new Date(l);
                return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
            }),
            datasets: [{
                label: label,
                data: data,
                borderColor: color,
                backgroundColor: color + '20',
                fill: true,
                tension: 0.3,
                pointRadius: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: '#e3e6eb' } },
                x: { grid: { display: false } }
            }
        }
    });

    setInstance(newChart);
}

// Clip Management
async function deleteClip(clipId) {
    if (!confirm('Are you sure you want to delete this clip and its file?')) {
        return;
    }

    try {
        const response = await fetch(`/api/clips/${clipId}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            await refreshData();
        } else {
            alert('Failed to delete clip: ' + data.error);
        }
    } catch (error) {
        console.error('Error deleting clip:', error);
    }
}

async function cleanupPending() {
    if (!confirm('Delete all pending clip files?')) return;
    cleanup('pending');
}

async function cleanupFailed() {
    if (!confirm('Delete all failed clip data and files?')) return;
    cleanup('failed');
}

async function cleanup(status) {
    try {
        const response = await fetch(`/api/clips/cleanup?status=${status}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            alert(data.message);
            await refreshData();
        } else {
            alert('Failed to cleanup: ' + data.error);
        }
    } catch (error) {
        console.error('Error cleaning up:', error);
    }
}

// Load recent uploads
async function loadUploads(showSkeleton = false) {
    const tbody = document.getElementById('uploads-tbody');

    if (showSkeleton) {
        tbody.innerHTML = getSkeletonRow().repeat(5);
    }

    try {
        const response = await fetch('/api/uploads?limit=50');
        const clips = await response.json();

        if (clips.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">No records found. Start your first download to see activity.</td></tr>';
            return;
        }

        renderClips(clips);

        // Setup Search
        const searchInput = document.getElementById('clip-search');
        searchInput.oninput = (e) => {
            const query = e.target.value.toLowerCase();
            const filtered = clips.filter(c =>
                c.title.toLowerCase().includes(query) ||
                (c.game_name && c.game_name.toLowerCase().includes(query)) ||
                (c.broadcaster_name && c.broadcaster_name.toLowerCase().includes(query))
            );
            renderClips(filtered);
        };

    } catch (error) {
        console.error('Error loading uploads:', error);
        tbody.innerHTML =
            '<tr><td colspan="7" class="loading">Error syncing records. Please try again.</td></tr>';
    }
}

function renderClips(clips) {
    const tbody = document.getElementById('uploads-tbody');
    if (clips.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No clips match your search.</td></tr>';
        return;
    }

    tbody.innerHTML = clips.map(clip => {
        const date = new Date(clip.downloaded_at).toLocaleDateString(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        const statusClass = `status-${clip.upload_status}`;
        const statusText = clip.upload_status.charAt(0).toUpperCase() + clip.upload_status.slice(1);

        let actionBtn = '';
        if (clip.upload_status === 'uploaded' && clip.youtube_url) {
            actionBtn = `<a href="${clip.youtube_url}" target="_blank" class="btn btn-secondary btn-sm">View on YT</a>`;
        } else if (clip.url) {
            actionBtn = `<a href="${clip.url}" target="_blank" class="btn btn-secondary btn-sm">Original</a>`;
        }

        // Add Delete Button for non-uploaded clips
        if (clip.upload_status !== 'uploaded') {
            actionBtn += ` <button onclick="deleteClip('${clip.clip_id}')" class="btn btn-danger btn-sm" title="Delete file & record">🗑️</button>`;
        }

        return `
            <tr>
                <td><div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500;">${escapeHtml(clip.title)}</div></td>
                <td><span style="color: var(--cf-blue); font-size: 13px;">${escapeHtml(clip.game_name || 'N/A')}</span></td>
                <td>${escapeHtml(clip.broadcaster_name || 'N/A')}</td>
                <td>${(clip.view_count || 0).toLocaleString()}</td>
                <td style="color: var(--text-secondary); font-size: 13px;">${date}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td style="white-space: nowrap;">${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Check for URL parameters (success/error messages)
function checkUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has('success')) {
        const message = urlParams.get('success');
        if (message === 'youtube_connected') {
            // Success notification in a clean way
            console.log('Successfully connected to YouTube!');
        }
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    if (urlParams.has('error')) {
        const error = urlParams.get('error');
        alert('Authentication Error: ' + error.replace(/_/g, ' '));
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    checkUrlParams();
    refreshData();
    setInterval(refreshData, 30000);

    // Analytics days listener
    document.getElementById('analytics-days').addEventListener('change', () => loadAnalytics(true));
});
