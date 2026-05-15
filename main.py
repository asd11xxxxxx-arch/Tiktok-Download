import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import yt_dlp
import os
import re
import time
import logging
import threading
from datetime import datetime
from flask import Flask, request
import sys

# ========== FLASK APP FOR RENDER ==========
app = Flask(__name__)

@app.route('/')
def health_check():
    return "✅ Bot is running!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ========== BOT CONFIGURATION ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "youtube-mp4-mp3-m4a-cdn.p.rapidapi.com"
COOLDOWN_TIME = 5
TEMP_DIR = "downloads"

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)
user_last_request = {}

# Create temp directory
os.makedirs(TEMP_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== HELPER FUNCTIONS ==========
def search_youtube(query):
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
    try:
        response = requests.get(url, stream=True, timeout=60)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

def clean_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)[:100]

def delete_temp_file(file_path):
    time.sleep(5)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.error(f"Delete error: {e}")

def can_send(user_id):
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

**Commands:**
/start - Restart bot
/help - Show this menu
"""
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    song_name = message.text.strip()
    
    if not can_send(user_id):
        bot.reply_to(message, "⏳ Please wait before sending another request!")
        return
    
    searching_msg = bot.reply_to(message, "🔍 **Searching...**\n⏳ Please wait...", parse_mode="Markdown")
    
    video_info = search_youtube(song_name)
    
    if not video_info:
        bot.edit_message_text(
            "❌ **No results found!**\nPlease try a different song name.",
            chat_id=user_id,
            message_id=searching_msg.message_id,
            parse_mode="Markdown"
        )
        return
    
    duration = format_duration(video_info['duration'])
    title = video_info['title'][:100]
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_mp3 = InlineKeyboardButton("🎵 Download MP3", callback_data=f"mp3|{video_info['id']}|{title}")
    btn_mp4 = InlineKeyboardButton("🎬 Download MP4", callback_data=f"mp4|{video_info['id']}|{title}")
    keyboard.add(btn_mp3, btn_mp4)
    
    preview_text = f"""
✅ **Song Found**
━━━━━━━━━━━━━━━
🎧 **Title:** {title}
⏱ **Duration:** {duration}
━━━━━━━━━━━━━━━

Choose your format below:
"""
    
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
    
    file_type = data[0]
    video_id = data[1]
    title = data[2]
    
    bot.answer_callback_query(call.id, f"Processing {file_type.upper()}...")
    
    processing_text = f"⏳ **Processing {file_type.upper()} download...**\n\n🎵 {title}\nPlease wait..."
    bot.edit_message_text(
        processing_text,
        chat_id=user_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    
    download_url = get_download_url(video_id, file_type)
    
    if not download_url:
        bot.edit_message_text(
            "❌ **Download failed!**\nCould not fetch download URL. Please try again later.",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
    safe_title = clean_filename(title)
    extension = "mp3" if file_type == "mp3" else "mp4"
    file_path = os.path.join(TEMP_DIR, f"{safe_title}_{int(time.time())}.{extension}")
    
    success = download_file(download_url, file_path)
    
    if not success:
        bot.edit_message_text(
            "❌ **Download failed!**\nNetwork error or invalid URL.",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
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
        
        success_text = f"✅ **Download complete!**\n\n🎵 {title}\n📁 Format: {file_type.upper()}"
        bot.edit_message_text(
            success_text,
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Send file error: {e}")
        bot.edit_message_text(
            "❌ **Failed to send file!**",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    
    threading.Thread(target=delete_temp_file, args=(file_path,), daemon=True).start()

# ========== RUN BOT WITH FLASK ==========
def run_bot():
    """Remove webhook and start polling in background"""
    try:
        bot.remove_webhook()
        logger.info("Starting bot polling...")
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except Exception as e:
        logger.error(f"Polling error: {e}")

if __name__ == "__main__":
    logger.info("Bot started!")
    
    # Start bot polling in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Run Flask app on port 8080 (required for Render)
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port)
