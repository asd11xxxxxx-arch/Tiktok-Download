# 🎵 Telegram Music & Video Downloader Bot

A professional Telegram bot that downloads music and videos from YouTube directly to your Telegram chat.

## ✨ Features

- 🔍 Automatic YouTube search from song name
- 🎵 MP3 audio download (high quality)
- 🎬 MP4 video download (HD if available)
- 🖼 Thumbnail preview
- ⏱ Duration display
- 🎨 Modern UI with inline buttons
- 🛡 Anti-spam cooldown protection
- 📝 Logging system
- 🧹 Automatic temporary file cleanup
- ⚡ Fast async processing

## 🚀 Setup Instructions

### 1. Prerequisites

- Python 3.8 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- RapidAPI Key (from [RapidAPI](https://rapidapi.com))

### 2. Installation

```bash
# Clone or download the project
cd TelegramMusicBot

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "BOT_TOKEN=your_telegram_bot_token" > .env
echo "RAPIDAPI_KEY=your_rapidapi_key" >> .env
