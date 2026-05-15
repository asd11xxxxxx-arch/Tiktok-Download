import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import yt_dlp
import os
import re
import time
import logging
import threading
from datetime import datetime
from config import BOT_TOKEN, RAPIDAPI_KEY, RAPIDAPI_HOST, COOLDOWN_TIME, TEMP_DIR

# ========== CONFIGURATION ==========
bot = telebot.TeleBot(BOT_TOKEN)
user_last_request = {}

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== HELPER FUNCTIONS ==========
def search_youtube(query):
    """Search YouTube and return best matching video info"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch1:{query}"
            info = ydl.extract_info(search_query, download=False)
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
                return {
                    'id': video['id'],
                    'title': video['title'],
                    'duration': video.get('duration', 0),
                    'thumbnail': video.get('thumbnail', ''),
                    'url': video.get('url', '')
                }
    except Exception as e:
        logger.error(f"Search error: {e}")
    return None

def get_download_url(video_id, file_type):
    """Get direct download URL from RapidAPI"""
    url = f"https://{RAPIDAPI_HOST}/cdn"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    payload = {"id": video_id}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
        
        if response.status_code == 200 and 'data' in data:
            if file_type == 'mp3' and 'mp3' in data['data']:
                return data['data']['mp3']['url']
            elif file_type == 'mp4' and 'mp4' in data['data']:
                return data['data']['mp4']['url']
    except Exception as e:
        logger.error(f"RapidAPI error: {e}")
    return None

def download_file(url, file_path):
    """Download file with progress"""
    try:
        response = requests.get(url, stream=True, timeout=60)
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        logger.info(f"Download progress: {percent:.2f}%")
        return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

def format_duration(seconds):
    """Format duration in mm:ss or hh:mm:ss"""
    if not seconds:
        return "Unknown"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def clean_filename(title):
    """Clean filename for safe saving"""
    return re.sub(r'[\\/*?:"<>|]', "", title)[:100]

def delete_temp_file(file_path):
    """Delete temp file after delay"""
    time.sleep(5)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.error(f"Delete error: {e}")

def can_send(user_id):
    """Anti-spam cooldown"""
    now = time.time()
    if user_id in user_last_request:
        if now - user_last_request[user_id] < COOLDOWN_TIME:
            return False
    user_last_request[user_id] = now
    return True

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🎵 **Music & Video Downloader Bot** 🎬

Send me any **song name** or **video title** and I'll find it for you!

**How to use:**
• Simply type: `Believer Imagine Dragons`
• I'll search YouTube and give you download options

**Features:**
🎧 MP3 Audio download
🎬 MP4 Video download
⚡ Fast & Free
🛡 No ads

**Commands:**
/start - Restart bot
/help - Show this menu
/about - About bot

Enjoy! 🎶
"""
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def about_bot(message):
    about_text = """
🤖 **Bot Information**

📌 Version: 1.0
👨‍💻 Built with: pyTelegramBotAPI + yt-dlp
🔗 API: YouTube CDN via RapidAPI

**Features:**
• Automatic YouTube search
• MP3 & MP4 download
• Inline keyboard UI
• Anti-spam protection
• Auto-clean temp files

**Support:** https://t.me/k_raw_official
"""
    bot.reply_to(message, about_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    song_name = message.text.strip()
    
    # Anti-spam check
    if not can_send(user_id):
        bot.reply_to(message, "⏳ Please wait before sending another request!")
        return
    
    # Send searching message
    searching_msg = bot.reply_to(message, "🔍 **Searching music...**\n⏳ Please wait...", parse_mode="Markdown")
    
    # Search YouTube
    video_info = search_youtube(song_name)
    
    if not video_info:
        bot.edit_message_text(
            "❌ **No results found!**\nPlease try a different song name.",
            chat_id=user_id,
            message_id=searching_msg.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Format duration
    duration = format_duration(video_info['duration'])
    title = video_info['title'][:100]  # Limit title length
    
    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_mp3 = InlineKeyboardButton("🎵 Download MP3", callback_data=f"mp3|{video_info['id']}|{title}")
    btn_mp4 = InlineKeyboardButton("🎬 Download MP4", callback_data=f"mp4|{video_info['id']}|{title}")
    keyboard.add(btn_mp3, btn_mp4)
    
    # Edit message with preview
    preview_text = f"""
✅ **Song Found**
━━━━━━━━━━━━━━━
🎧 **Title:** {title}
⏱ **Duration:** {duration}
━━━━━━━━━━━━━━━

Choose your format below:
"""
    
    # Try to send thumbnail
    try:
        bot.edit_message_text(
            preview_text,
            chat_id=user_id,
            message_id=searching_msg.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        # Send thumbnail separately if possible
        if video_info['thumbnail']:
            bot.send_photo(user_id, video_info['thumbnail'], caption="🎵 Song Preview")
    except Exception as e:
        logger.error(f"Edit message error: {e}")
        bot.edit_message_text(
            preview_text,
            chat_id=user_id,
            message_id=searching_msg.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    data = call.data.split('|')
    
    if len(data) < 3:
        bot.answer_callback_query(call.id, "Invalid request!")
        return
    
    file_type = data[0]  # mp3 or mp4
    video_id = data[1]
    title = data[2]
    
    # Acknowledge callback
    bot.answer_callback_query(call.id, f"Processing {file_type.upper()}...")
    
    # Update message to show processing
    processing_text = f"⏳ **Processing {file_type.upper()} download...**\n\n🎵 {title}\nPlease wait, this may take a few moments."
    bot.edit_message_text(
        processing_text,
        chat_id=user_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    
    # Get download URL from API
    download_url = get_download_url(video_id, file_type)
    
    if not download_url:
        bot.edit_message_text(
            "❌ **Download failed!**\nCould not fetch download URL. Please try again later.",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Prepare filename
    safe_title = clean_filename(title)
    extension = "mp3" if file_type == "mp3" else "mp4"
    file_path = os.path.join(TEMP_DIR, f"{safe_title}_{int(time.time())}.{extension}")
    
    # Send "downloading" status
    status_msg = bot.send_message(user_id, "📥 **Downloading file...**", parse_mode="Markdown")
    
    # Download file
    success = download_file(download_url, file_path)
    
    if not success:
        bot.edit_message_text(
            "❌ **Download failed!**\nNetwork error or invalid URL.",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        bot.delete_message(user_id, status_msg.message_id)
        return
    
    # Delete status message
    bot.delete_message(user_id, status_msg.message_id)
    
    # Send file to user
    try:
        with open(file_path, 'rb') as f:
            if file_type == "mp3":
                bot.send_audio(
                    user_id,
                    f,
                    title=title,
                    performer="Music Bot",
                    caption=f"🎵 **{title}**\n✅ Downloaded successfully!"
                )
            else:
                bot.send_video(
                    user_id,
                    f,
                    caption=f"🎬 **{title}**\n✅ Downloaded successfully!",
                    supports_streaming=True
                )
        
        # Update original message to success
        success_text = f"✅ **Download complete!**\n\n🎵 {title}\n📁 Format: {file_type.upper()}\n\nFile sent successfully!"
        bot.edit_message_text(
            success_text,
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Send file error: {e}")
        bot.edit_message_text(
            "❌ **Failed to send file!**\nFile may be too large for Telegram.",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    
    # Cleanup temp file
    threading.Thread(target=delete_temp_file, args=(file_path,), daemon=True).start()

# ========== START BOT ==========
if __name__ == "__main__":
    logger.info("Bot started!")
    print("🤖 Music Downloader Bot is running...")
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
