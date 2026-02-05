# Twitch Clip Auto-Uploader with YouTube Integration

Automatically download top Twitch clips hourly and upload them to YouTube with a beautiful web dashboard.

## ✨ Features

- 🔄 **Auto-updates top games**: Fetches top 5 trending games daily at 3 AM UTC
- ⏰ **Hourly clip downloads**: Downloads top clips every hour from rotating games
- 📤 **YouTube auto-upload**: Automatically uploads clips to your YouTube channel
- 🎯 **Smart rotation**: Cycles through the top 5 games for variety
- 📊 **Web dashboard**: Beautiful UI to monitor stats and uploads
- 🐳 **Docker-ready**: Run as a containerized service
- 💾 **Upload tracking**: SQLite database tracks all clips and uploads

## 🌐 Web Dashboard

Access the dashboard at **http://localhost:8000** to:
- Connect your YouTube account
- View upload statistics
- Monitor recent clips and their status
- See failed uploads and errors

![Dashboard Preview](https://via.placeholder.com/800x400/0a0e27/6366f1?text=Dashboard+Preview)

## 🚀 Quick Start

### Prerequisites

1. **Twitch API Credentials**
   - Create an app at [Twitch Developer Console](https://dev.twitch.tv/console/apps)
   - Get Client ID and Client Secret

2. **YouTube API Credentials** (for auto-upload)
   - Create a project at [Google Cloud Console](https://console.cloud.google.com/)
   - Enable YouTube Data API v3
   - Create OAuth 2.0 credentials (Web application)
   - Add redirect URI: `http://localhost:8000/auth/youtube/callback`

### Setup with Docker (Recommended)

1. **Clone and configure**:
   ```bash
   git clone <your-repo>
   cd tcif
   cp .env.example .env
   ```

2. **Edit `.env`** with your credentials:
   ```env
   TWITCH_CLIENT_ID=your_twitch_client_id
   TWITCH_CLIENT_SECRET=your_twitch_client_secret
   
   YOUTUBE_CLIENT_ID=your_google_client_id
   YOUTUBE_CLIENT_SECRET=your_google_client_secret
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Connect YouTube**:
   - Open **http://localhost:8000** in your browser
   - Click "Connect YouTube" and authorize the app
   - Done! Clips will now auto-upload

5. **Monitor logs**:
   ```bash
   docker-compose logs -f
   ```

### Local Setup (Without Docker)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Run the application**:
   ```bash
   python3 -m app.main
   ```

4. **Access dashboard**: http://localhost:8000

## 📋 How It Works

### Automated Flow

1. **Daily at 3 AM UTC**: Fetches top 5 trending games from Twitch API
2. **Every hour**: 
   - Selects next game in rotation
   - Fetches top clips from last hour
   - Downloads the best clip
   - Saves to database
   - **If YouTube connected**: Automatically uploads to your channel
3. **Dashboard**: Updates in real-time with stats and upload history

### File Organization

```
tcif/
├── app/
│   ├── main.py              # Main runner (web + scheduler)
│   ├── scheduler.py         # APScheduler jobs
│   ├── clips.py             # Twitch API interactions
│   ├── downloader.py        # yt-dlp wrapper
│   ├── game_manager.py      # Game rotation logic
│   ├── youtube_auth.py      # YouTube OAuth flow
│   ├── youtube_uploader.py  # YouTube upload logic
│   ├── database.py          # SQLite tracking
│   └── web.py               # FastAPI dashboard
├── static/
│   ├── index.html           # Dashboard UI
│   ├── style.css            # Premium styling
│   └── script.js            # Dashboard logic
├── downloads/               # Downloaded clips
├── data/                    # Game state & database
│   ├── top_games.json       # Current top games
│   ├── rotation_state.json  # Rotation tracker
│   ├── clips.db             # Upload database
│   └── youtube_token.json   # YouTube credentials
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 📊 Dashboard Features

### Stats Cards
- **Total Clips**: Number of clips downloaded
- **Uploaded**: Successfully uploaded to YouTube
- **Pending**: Downloaded but not yet uploaded
- **Failed**: Upload failures with error details

### Upload History Table
- Clip title, game, broadcaster
- View counts and timestamps
- Upload status badges
- Direct links to YouTube videos

### YouTube Connection
- One-click OAuth integration
- Auto-refresh tokens
- Disconnect anytime

## ⚙️ Configuration

### YouTube Upload Settings

Customize video metadata in `.env`:

```env
# Title template
YOUTUBE_TITLE_TEMPLATE={clip_title} - Twitch Highlights

# Description
YOUTUBE_DESCRIPTION=Amazing clip from {broadcaster}!\n\nOriginal: {clip_url}

# Tags (comma-separated)
YOUTUBE_TAGS=twitch,gaming,highlights,{game}

# Category (20 = Gaming)
YOUTUBE_CATEGORY=20

# Privacy: public, unlisted, or private
YOUTUBE_PRIVACY=public
```

**Available variables**:
- `{clip_title}` - Original clip title
- `{creator}` - Clip creator name
- `{broadcaster}` - Channel name
- `{game}` - Game name
- `{clip_url}` - Original Twitch URL
- `{views}` - View count
- `{duration}` - Clip duration

## 🔧 Manual Downloads

To download a specific clip manually:

```bash
# Set broadcaster or game ID in .env
TWITCH_BROADCASTER_ID=123456789

# Run manual download
python3 -m app.download_clip
```

## 📅 Schedule

| Job | Frequency | Description |
|-----|-----------|-------------|
| **Update Top Games** | Daily at 3:00 AM UTC | Fetches top 5 trending games |
| **Download & Upload Clips** | Every hour (on the hour) | Downloads and uploads clips |

## 🔍 Monitoring

### Docker Logs
```bash
# Follow all logs
docker-compose logs -f

# View recent logs
docker-compose logs --tail=100
```

### Dashboard
- Real-time stats
- Upload history
- Error tracking

## 🛠️ Troubleshooting

**YouTube upload fails**:
- Check OAuth credentials in `.env`
- Ensure redirect URI matches exactly
- Re-connect YouTube in dashboard

**No clips found**:
- Check Twitch API credentials
- Verify games have recent clips
- Check scheduler logs

**Dashboard not loading**:
- Ensure port 8000 is not in use
- Check Docker container is running
- Verify static files are copied

## 📝 Notes

- Clips are downloaded to `./downloads` directory
- Database and state files saved in `./data`
- YouTube tokens automatically refresh
- Scheduler runs continuously in Docker
- Dashboard auto-refreshes every 30 seconds

## 🎯 What's Changed

From the previous version, this update adds:
- ✅ Full YouTube integration with OAuth
- ✅ Beautiful web dashboard
- ✅ Upload tracking database
- ✅ Automatic upload after download
- ✅ Top 5 games (increased from 3)
- ✅ Enhanced logging
- ✅ Real-time stats monitoring

## 📜 License

MIT License - feel free to use and modify!
