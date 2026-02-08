// Dashboard JavaScript

let viewsChart = null;
let watchTimeChart = null;
let currentTab = 'clips';
let clipsData = [];
let youtubeVideos = [];

// Helper to create skeleton row for table
const getSkeletonRow = () => `
    <tr>
        <td class="video-thumbnail-cell"><div class="skeleton" style="width: 100px; height: 56px; border-radius: 4px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 80%; height: 20px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 50%; height: 20px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 40%; height: 20px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 40%; height: 20px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 70%; height: 20px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 60%; height: 24px; border-radius: 12px;"></div></td>
        <td><div class="skeleton skeleton-text" style="width: 30%; height: 32px; border-radius: 6px;"></div></td>
    </tr>
`;

const getGameSkeleton = () => `
    <div class="skeleton-leaderboard skeleton"></div>
`;

// Refresh stats and uploads data
async function refreshData(showSkeleton = false) {
    await Promise.all([
        loadStats(),
        loadUploads(showSkeleton),
        loadAnalytics(showSkeleton),
        loadTrending(showSkeleton),
        loadTopGames(showSkeleton)
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
    if (!confirm('Are you sure you want to disconnect YouTube?')) return;

    try {
        await fetch('/auth/youtube/disconnect');
        window.location.reload();
    } catch (error) {
        console.error('Error disconnecting YouTube:', error);
    }
}

// Switch between Clips and YouTube tabs
function switchTab(tab) {
    currentTab = tab;

    // Update tabs UI
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Render the active dataset
    if (tab === 'clips') {
        renderClips(clipsData);
    } else {
        renderYouTubeVideos(youtubeVideos);
    }

    // Re-trigger search after switching tabs
    const searchQuery = document.getElementById('clip-search').value;
    if (searchQuery) {
        triggerSearch(searchQuery);
    }
}

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
    const formattedLabels = labels.map(l => {
        const d = new Date(l);
        return d.toLocaleDateString('en-IN', {
            timeZone: 'Asia/Kolkata',
            month: 'short',
            day: 'numeric'
        });
    });

    if (chartInstance) {
        chartInstance.data.labels = formattedLabels;
        chartInstance.data.datasets[0].data = data;
        chartInstance.update('none'); // silent update
        return;
    }

    const newChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: formattedLabels,
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

// Helper to format date in IST
function formatIST(dateString) {
    return new Date(dateString).toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

// Render a reusable leaderboard item
function createLeaderboardItem(game, rank, options = {}) {
    let artUrl = game.box_art_url || '';

    if (!artUrl && (game.id || game.game_id)) {
        const id = game.id || game.game_id;
        artUrl = `https://static-cdn.jtvnw.net/ttv-boxart/${id}-{width}x{height}.jpg`;
    }

    if (!artUrl) {
        artUrl = 'https://static-cdn.jtvnw.net/ttv-static/404_boxart-{width}x{height}.jpg';
    }

    artUrl = artUrl
        .replace('{width}', '120')
        .replace('{height}', '160');

    const meta = options.meta || '';

    return `
        <div class="leaderboard-item">
            <div class="leaderboard-rank">#${rank}</div>
            <div class="leaderboard-art-container">
                <img src="${artUrl}" alt="${escapeHtml(game.name || game.game_name)}" class="leaderboard-art" loading="lazy">
            </div>
            <div class="leaderboard-info">
                <div class="leaderboard-name">${escapeHtml(game.name || game.game_name)}</div>
                <div class="leaderboard-meta">
                    <span>${meta}</span>
                </div>
            </div>
        </div>
    `;
}

// Render a reusable game grid card
function createGameCard(game, options = {}) {
    let artUrl = game.box_art_url || '';

    // Generate art URL if missing but ID exists
    if (!artUrl && (game.id || game.game_id)) {
        const id = game.id || game.game_id;
        artUrl = `https://static-cdn.jtvnw.net/ttv-boxart/${id}-{width}x{height}.jpg`;
    }

    // Fallback image
    if (!artUrl) {
        artUrl = 'https://static-cdn.jtvnw.net/ttv-static/404_boxart-{width}x{height}.jpg';
    }

    // Replace width/height
    artUrl = artUrl
        .replace('{width}', '285')
        .replace('{height}', '380');

    const meta = options.meta || '';
    const flag = options.isTrending ? '<div class="trending-flag">TRENDING</div>' : '';

    return `
        <div class="game-card">
            ${flag}
            <div class="game-art-container">
                <img src="${artUrl}" alt="${escapeHtml(game.name || game.game_name)}" class="game-art" loading="lazy">
            </div>
            <div class="game-info">
                <div class="game-name">${escapeHtml(game.name || game.game_name)}</div>
                <div class="game-meta">
                    <span>${meta}</span>
                </div>
            </div>
        </div>
    `;
}

// Load top games
async function loadTopGames(showSkeleton = false) {
    const grid = document.getElementById('top-games-grid');
    if (showSkeleton || !grid.innerHTML || grid.querySelector('.loading-container')) {
        grid.innerHTML = getGameSkeleton().repeat(8);
    }

    try {
        const response = await fetch('/api/top-games');
        const data = await response.json();

        // Defensive check for the games list
        let games = [];
        if (Array.isArray(data)) {
            games = data;
        } else if (data && Array.isArray(data.games)) {
            games = data.games;
        } else if (data && Array.isArray(data.data)) {
            games = data.data;
        }

        if (games.length === 0) {
            grid.innerHTML = '<div class="loading-container">No top games found.</div>';
            return;
        }

        grid.innerHTML = games.map((game, index) => createLeaderboardItem(game, index + 1)).join('');
    } catch (error) {
        console.error('Error loading top games:', error);
        grid.innerHTML = '<div class="loading-container">Error loading top games. See console for details.</div>';
    }
}

// Load trending games
async function loadTrending(showSkeleton = false) {
    const grid = document.getElementById('trending-grid');

    if (showSkeleton || !grid.innerHTML || grid.querySelector('.loading-container')) {
        grid.innerHTML = getGameSkeleton().repeat(4);
    }

    try {
        const response = await fetch('/api/trending');
        const data = await response.json();

        const trending = Array.isArray(data) ? data : (data.data || []);

        if (trending.length === 0) {
            grid.innerHTML = '<div class="loading-container">No games currently trending. Checking every hour.</div>';
            return;
        }

        grid.innerHTML = trending.map((game, index) => {
            const viewers = (game.current_viewers || 0).toLocaleString();
            return createLeaderboardItem(game, index + 1, {
                meta: `🔥 ${viewers} viewers`
            });
        }).join('');
    } catch (error) {
        console.error('Error loading trending:', error);
        grid.innerHTML = '<div class="loading-container">Error loading trends.</div>';
    }
}

// Load both local clips and YouTube videos
async function loadUploads(showSkeleton = false) {
    const tbody = document.getElementById('uploads-tbody');

    if (showSkeleton) {
        tbody.innerHTML = getSkeletonRow().repeat(5);
    }

    try {
        // Fetch both datasets in parallel
        const [clipsRes, youtubeRes] = await Promise.all([
            fetch('/api/uploads?limit=50'),
            fetch('/api/youtube-videos?limit=50')
        ]);

        clipsData = await clipsRes.json();
        const youtubePayload = await youtubeRes.json();
        youtubeVideos = Array.isArray(youtubePayload) ? youtubePayload : (youtubePayload.items || []);

        // Initial render based on active tab
        if (currentTab === 'clips') {
            renderClips(clipsData);
        } else {
            renderYouTubeVideos(youtubeVideos);
        }

        // Setup Search
        const searchInput = document.getElementById('clip-search');
        searchInput.oninput = (e) => triggerSearch(e.target.value);

    } catch (error) {
        console.error('Error loading uploads:', error);
        tbody.innerHTML =
            '<tr><td colspan="8" class="loading">Error syncing records. Please try again.</td></tr>';
    }
}

function triggerSearch(query) {
    const q = query.toLowerCase();
    if (currentTab === 'clips') {
        const filtered = clipsData.filter(c =>
            c.title.toLowerCase().includes(q) ||
            (c.game_name && c.game_name.toLowerCase().includes(q))
        );
        renderClips(filtered);
    } else {
        const filtered = youtubeVideos.filter(v =>
            v.title.toLowerCase().includes(q)
        );
        renderYouTubeVideos(filtered);
    }
}

function renderClips(clips) {
    const thead = document.querySelector('#uploads-table thead');
    const tbody = document.getElementById('uploads-tbody');

    // Only update headers if needed to prevent flicker
    if (thead.dataset.activeTab !== 'clips') {
        thead.innerHTML = `
            <tr>
                <th>Video Title</th>
                <th>Category</th>
                <th>Creator</th>
                <th>Views</th>
                <th>Date Added</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        `;
        thead.dataset.activeTab = 'clips';
    }

    if (clips.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No local clips found.</td></tr>';
        return;
    }

    tbody.innerHTML = clips.map(clip => {
        const date = formatIST(clip.downloaded_at);
        const statusClass = `status-${clip.upload_status}`;
        const statusText = clip.upload_status.charAt(0).toUpperCase() + clip.upload_status.slice(1);

        let actionBtn = '';
        if (clip.upload_status === 'uploaded' && clip.youtube_url) {
            actionBtn = `<a href="${clip.youtube_url}" target="_blank" class="btn btn-secondary btn-sm">View on YT</a>`;
        } else if (clip.url) {
            actionBtn = `<a href="${clip.url}" target="_blank" class="btn btn-secondary btn-sm">Original</a>`;
        }

        if (clip.upload_status !== 'uploaded') {
            actionBtn += ` <button onclick="deleteClip('${clip.clip_id}')" class="btn btn-danger btn-sm" title="Delete record">🗑️</button>`;
        }

        return `
            <tr>
                <td><div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500;">${escapeHtml(clip.title)}</div></td>
                <td><span style="color: var(--cf-blue); font-size: 13px;">${escapeHtml(clip.game_name || 'N/A')}</span></td>
                <td>${escapeHtml(clip.broadcaster_name || 'N/A')}</td>
                <td>${(clip.view_count || 0).toLocaleString()}</td>
                <td style="color: var(--text-secondary); font-size: 13px; white-space: nowrap;">${date}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td style="white-space: nowrap;">${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

function renderYouTubeVideos(videos) {
    const thead = document.querySelector('#uploads-table thead');
    const tbody = document.getElementById('uploads-tbody');

    // Only update headers if needed to prevent flicker
    if (thead.dataset.activeTab !== 'youtube') {
        thead.innerHTML = `
            <tr>
                <th>Preview</th>
                <th>Video Title</th>
                <th>Views</th>
                <th>Likes</th>
                <th>Comments</th>
                <th>Published</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        `;
        thead.dataset.activeTab = 'youtube';
    }

    if (videos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading">No videos found on YouTube.</td></tr>';
        return;
    }

    tbody.innerHTML = videos.map(video => {
        const date = formatIST(video.published_at);
        const statusClass = `status-${video.status}`;
        const statusText = video.status.charAt(0).toUpperCase() + video.status.slice(1);

        const actionBtn = `<a href="${video.url}" target="_blank" class="btn btn-secondary btn-sm">Watch</a>`;

        return `
            <tr>
                <td class="video-thumbnail-cell">
                    <img src="${video.thumbnail}" alt="thumbnail" class="video-thumbnail">
                </td>
                <td><div style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500;">${escapeHtml(video.title)}</div></td>
                <td style="font-weight: 600;">${(video.view_count || 0).toLocaleString()}</td>
                <td style="font-weight: 600; color: var(--cf-blue);">${(video.like_count || 0).toLocaleString()}</td>
                <td style="font-weight: 600; color: var(--text-secondary);">${(video.comment_count || 0).toLocaleString()}</td>
                <td style="color: var(--text-secondary); font-size: 13px; white-space: nowrap;">${date}</td>
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
    refreshData(true); // First load with skeletons
    setInterval(() => refreshData(false), 30000); // Background refresh silent

    // Analytics days listener
    document.getElementById('analytics-days').addEventListener('change', () => loadAnalytics(true));
});
