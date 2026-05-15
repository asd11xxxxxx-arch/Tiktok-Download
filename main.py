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
from flask import Flask, request
import json
import random

# ========== FLASK APP FOR RENDER ==========
app = Flask(__name__)

@app.route('/')
def health_check():
    return "✅ Bot is running!", 200

# ========== BOT CONFIGURATION ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "youtube-mp4-mp3-m4a-cdn.p.rapidapi.com"
COOLDOWN_TIME = 3
TEMP_DIR = "downloads"

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)
user_last_request = {}
user_data = {}

# Create temp directory
os.makedirs(TEMP_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== MYANMAR LANGUAGE TEXT ==========
TEXTS = {
    'welcome': """
🎵 **မင်္ဂလာပါ ဂီတချစ်သူရေ** 🎵

ကျွန်တော်က **Music & Video Downloader Bot** ပါ။
YouTube ကနေ သီချင်းနဲ့ Video တွေ အခမဲ့ ဒေါင်းလုဒ်လုပ်ပေးပါတယ်။

📌 **အသုံးပြုနည်း**
• သီချင်းနာမည် ရိုက်ထည့်ပါ
• ဥပမာ - `Believer Imagine Dragons`
• ငါ့ကို ရှာခိုင်းလိုက်ရုံပါပဲ

✨ **အင်္ဂါရပ်များ**
🎧 MP3 အသံဖိုင်
🎬 MP4 ဗီဒီယိုဖိုင်
⚡ မြန်ဆန်တိကျ
🛡 ကြော်ငြာကင်းစင်

📝 **Command များ**
/start - စတင်ရန်
/help - အကူအညီ
/about - ဘော့အကြောင်း

**စတင်လိုက်ပါ...** 🚀
""",
    'help': """
📚 **အသုံးပြုနည်း အဆင့်ဆင့်**

1️⃣ သီချင်းနာမည် ရိုက်ထည့်ပါ
2️⃣ ဘော့က ရှာပေးပါမယ်
3️⃣ ရလဒ်ကို ပြသပါမယ်
4️⃣ MP3 သို့မဟုတ် MP4 ရွေးပါ
5️⃣ ဒေါင်းလုဒ်လုပ်ပြီး လက်ခံယူပါ

🎯 **ဥပမာများ**
• မင်းကိုယ်တော် - ရေစက်လက်လက်
• Justin Bieber - Baby
• Despacito lyrics

❓ **အကူအညီလိုရင်**
@k_raw_official

⚡ **အကြံပြုချက်**
မြန်မာလို ရေးလည်း ရှာပေးပါတယ်။
""",
    'about': """
🤖 **ဘော့အကြောင်းအသေးစိတ်**

📌 **ဗားရှင်း:** 2.0 (Myanmar Edition)
👨‍💻 **ကိုယ်တိုင်ရေး:** ကိုရဲ
🔧 **အသုံးပြုထားသော API:**
• YouTube Data API
• RapidAPI CDN

💎 **အင်္ဂါရပ်အပြည့်အစုံ**
• အမြန်ရှာဖွေခြင်း
• အရည်အသွေးမြင့် MP3/MP4
• Anti-spam ကာကွယ်ရေး
• Auto-clean စနစ်
• 24/7 အလုပ်လုပ်ခြင်း

🎁 **အခမဲ့အသုံးပြုနိုင်ပါသည်**
အားလုံးအတွက် ကန့်သတ်ချက်မရှိ ဝန်ဆောင်မှုပေးပါတယ်။

📢 **ချန်နယ်:** @k_raw_official
"""
}

# ========== HELPER FUNCTIONS ==========
def search_youtube(query):
    """Search YouTube and return best matching video info"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        logger.info(f"Downloaded: {percent:.1f}%")
        return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

def format_duration(seconds):
    """Format duration in mm:ss or hh:mm:ss"""
    if not seconds:
        return "အချိန်မသိရသေး"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}နာရီ {minutes}မိနစ် {seconds}စက္ကန့်"
    return f"{minutes}မိနစ် {seconds}စက္ကန့်"

def clean_filename(title):
    """Clean filename for safe saving"""
    # Remove emojis and special chars
    title = re.sub(r'[^\w\s\u1000-\u109F-]', '', title)
    return title[:80]

def delete_temp_file(file_path):
    """Delete temp file after delay"""
    time.sleep(10)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted: {file_path}")
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

def show_loading_animation(chat_id, message_id, step=0):
    """Show loading animation"""
    animations = ["🎵", "🎶", "🎼", "🎧", "📀", "💿"]
    text = f"{animations[step % len(animations)]} **လုပ်ဆောင်နေပါသည်...** \n\nကျေးဇူးပြု၍ စောင့်မျှော်ပေးပါ။"
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown")
        return step + 1
    except:
        return step

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Welcome message handler"""
    user_name = message.from_user.first_name
    welcome_text = TEXTS['welcome'].replace("ဂီတချစ်သူရေ", f"{user_name}") if user_name else TEXTS['welcome']
    
    # Create inline buttons
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_help = InlineKeyboardButton("📚 အကူအညီ", callback_data="help_menu")
    btn_about = InlineKeyboardButton("ℹ️ ဘော့အကြောင်း", callback_data="about_menu")
    btn_channel = InlineKeyboardButton("📢 ချန်နယ်", url="https://t.me/k_raw_official")
    btn_owner = InlineKeyboardButton("👤 ပိုင်ရှင်", url="https://t.me/k_raw_official")
    keyboard.add(btn_help, btn_about)
    keyboard.add(btn_channel, btn_owner)
    
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=keyboard)

@bot.message_handler(commands=['help'])
def send_help(message):
    """Help command handler"""
    bot.reply_to(message, TEXTS['help'], parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def send_about(message):
    """About command handler"""
    bot.reply_to(message, TEXTS['about'], parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ['help_menu', 'about_menu'])
def handle_menus(call):
    """Handle menu callbacks"""
    if call.data == 'help_menu':
        bot.edit_message_text(TEXTS['help'], call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    elif call.data == 'about_menu':
        bot.edit_message_text(TEXTS['about'], call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Main message handler for music search"""
    user_id = message.chat.id
    song_name = message.text.strip()
    
    # Check empty message
    if not song_name:
        bot.reply_to(message, "❌ **ကျေးဇူးပြု၍ သီချင်းနာမည် ထည့်သွင်းပါ။**", parse_mode="Markdown")
        return
    
    # Anti-spam check
    if not can_send(user_id):
        bot.reply_to(message, "⏳ **ခေတ္တစောင့်ဆိုင်းပေးပါ...** \n\nကျေးဇူးပြု၍ ခဏအကြာ ထပ်မံကြိုးစားပါ။", parse_mode="Markdown")
        return
    
    # Send searching message with animation
    status_msg = bot.reply_to(message, "🔍 **ရှာဖွေနေပါသည်...** \n⏳ ကျေးဇူးပြု၍ စောင့်မျှော်ပေးပါ။", parse_mode="Markdown")
    
    # Search YouTube
    video_info = search_youtube(song_name)
    
    if not video_info:
        bot.edit_message_text(
            "❌ **ရလဒ်မတွေ့ပါ!** \n\nကျေးဇူးပြု၍ အခြားသီချင်းနာမည်ဖြင့် ထပ်မံရှာဖွေပါ။\n\n💡 **အကြံပြုချက်:** အင်္ဂလိပ်လို ရှာဖွေကြည့်ပါ။",
            chat_id=user_id,
            message_id=status_msg.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Format duration
    duration = format_duration(video_info['duration'])
    title = video_info['title'][:100]
    
    # Store video info for later use
    user_data[user_id] = video_info
    
    # Create modern inline keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_mp3 = InlineKeyboardButton(
        "🎵 MP3 ဒေါင်းလုဒ်", 
        callback_data=f"mp3|{video_info['id']}|{title[:50]}"
    )
    btn_mp4 = InlineKeyboardButton(
        "🎬 MP4 ဒေါင်းလုဒ်", 
        callback_data=f"mp4|{video_info['id']}|{title[:50]}"
    )
    btn_cancel = InlineKeyboardButton("❌ မလုပ်တော့ပါ", callback_data="cancel")
    keyboard.add(btn_mp3, btn_mp4)
    keyboard.add(btn_cancel)
    
    # Preview message with thumbnail
    preview_text = f"""
✅ **တွေ့ရှိပါပြီ!**
━━━━━━━━━━━━━━━━━━━━
🎵 **ခေါင်းစဉ်:** `{title}`
⏱ **ကြာချိန်:** {duration}
🌐 **ရင်းမြစ်:** YouTube
━━━━━━━━━━━━━━━━━━━━

📥 **ဒေါင်းလုဒ်ပုံစံ ရွေးချယ်ပါ:**

• 🎵 MP3 - အသံဖိုင် (ဖိုင်အရွယ်အစားသေး)
• 🎬 MP4 - ဗီဒီယိုဖိုင် (အရည်အသွေးမြင့်)
"""
    
    # Edit message with preview
    bot.edit_message_text(
        preview_text,
        chat_id=user_id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    # Send thumbnail if available
    if video_info['thumbnail']:
        try:
            bot.send_photo(
                user_id, 
                video_info['thumbnail'], 
                caption=f"🎬 **Video Preview**\n\n{title}",
                parse_mode="Markdown"
            )
        except:
            pass

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Handle all callback queries"""
    user_id = call.message.chat.id
    
    # Handle cancel
    if call.data == "cancel":
        bot.edit_message_text(
            "❌ **လုပ်ဆောင်ချက် ဖျက်သိမ်းပြီးပါပြီ။** \n\n/start နှိပ်၍ ပြန်လည်စတင်နိုင်ပါသည်။",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "ဖျက်သိမ်းပြီးပါပြီ ✅")
        return
    
    # Parse callback data
    if '|' not in call.data:
        bot.answer_callback_query(call.id, "အမှားဖြစ်နေပါသည်!")
        return
    
    data = call.data.split('|')
    if len(data) < 3:
        bot.answer_callback_query(call.id, "အချက်အလက် မပြည့်စုံပါ!")
        return
    
    file_type = data[0]  # mp3 or mp4
    video_id = data[1]
    title = data[2]
    
    # Acknowledge callback
    bot.answer_callback_query(call.id, f"{file_type.upper()} ဒေါင်းလုဒ် စတင်နေပါပြီ... ⏳")
    
    # Update message to show processing
    processing_text = f"""
⏳ **{file_type.upper()} ဒေါင်းလုဒ် လုပ်ဆောင်နေပါသည်...**

🎵 **{title}**
━━━━━━━━━━━━━━━
📥 ဖိုင်အရွယ်အစား တွက်ချက်နေပါသည်...
⚡ ကျေးဇူးပြု၍ စောင့်မျှော်ပေးပါ။
"""
    
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
            "❌ **ဒေါင်းလုဒ် မအောင်မြင်ပါ!** \n\nအကြောင်းအမျိုးမျိုးကြောင့် ဒေါင်းလုဒ်မရနိုင်ပါ။\nကျေးဇူးပြု၍ နောက်မှထပ်ကြိုးစားပါ။\n\n📢 အကူအညီအတွက် @k_raw_official",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        return
    
    # Prepare filename
    safe_title = clean_filename(title)
    extension = "mp3" if file_type == "mp3" else "mp4"
    timestamp = int(time.time())
    file_path = os.path.join(TEMP_DIR, f"{safe_title}_{timestamp}.{extension}")
    
    # Send downloading status
    downloading_msg = bot.send_message(
        user_id, 
        f"📥 **ဒေါင်းလုဒ်လုပ်နေပါသည်...** \n\n🎵 {title}\n📁 {extension.upper()} ဖိုင်\n\n⏳ စောင့်မျှော်ပေးပါ...",
        parse_mode="Markdown"
    )
    
    # Download file
    success = download_file(download_url, file_path)
    
    if not success:
        bot.edit_message_text(
            "❌ **ဒေါင်းလုဒ် မအောင်မြင်ပါ!** \n\nကွန်ရက်အဆက်အသွယ် အားနည်းနေပါသည်။\nကျေးဇူးပြု၍ ထပ်မံကြိုးစားပါ။",
            chat_id=user_id,
            message_id=downloading_msg.message_id,
            parse_mode="Markdown"
        )
        if os.path.exists(file_path):
            os.remove(file_path)
        return
    
    # Delete downloading message
    bot.delete_message(user_id, downloading_msg.message_id)
    
    # Get file size
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
    
    # Send file to user with nice caption
    try:
        with open(file_path, 'rb') as f:
            if file_type == "mp3":
                bot.send_audio(
                    user_id,
                    f,
                    title=title[:50],
                    performer="Music Bot Myanmar",
                    caption=f"""
🎵 **ဒေါင်းလုဒ် အောင်မြင်ပါပြီ!**
━━━━━━━━━━━━━━━━━━━━
📌 **ခေါင်းစဉ်:** {title[:60]}
📁 **ဖိုင်အမျိုးအစား:** MP3 Audio
💾 **အရွယ်အစား:** {file_size:.1f} MB
✅ **အခြေအနေ:** အောင်မြင်ပါပြီ

📢 **ချန်နယ်:** @k_raw_official
🎵 **ပျော်ရွှင်စွာ နားဆင်ပါ!**
"""
                )
            else:
                bot.send_video(
                    user_id,
                    f,
                    caption=f"""
🎬 **ဒေါင်းလုဒ် အောင်မြင်ပါပြီ!**
━━━━━━━━━━━━━━━━━━━━
📌 **ခေါင်းစဉ်:** {title[:60]}
📁 **ဖိုင်အမျိုးအစား:** MP4 Video
💾 **အရွယ်အစား:** {file_size:.1f} MB
✅ **အခြေအနေ:** အောင်မြင်ပါပြီ

📢 **ချန်နယ်:** @k_raw_official
🎬 **ပျော်ရွှင်စွာ ကြည့်ရှုပါ!**
""",
                    supports_streaming=True
                )
        
        # Update original message to success
        success_text = f"""
✅ **ဒေါင်းလုဒ် ပြီးစီးပါပြီ!**
━━━━━━━━━━━━━━━━━━━━
🎵 **{title[:60]}**
📁 **ဖိုင်:** {extension.upper()}
💾 **အရွယ်အစား:** {file_size:.1f} MB
━━━━━━━━━━━━━━━━━━━━

🎉 **သင့် {extension.upper()} ဖိုင်ကို အပေါ်တွင် ပေးပို့ထားပါသည်။**

📢 **နောက်ထပ် သီချင်းများ ရှာရန်:** /start
"""
        bot.edit_message_text(
            success_text,
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Send file error: {e}")
        bot.edit_message_text(
            f"❌ **ဖိုင်ပေးပို့ရန် မအောင်မြင်ပါ!** \n\nအမှား: {str(e)[:100]}\n\nဖိုင်အရွယ်အစား ကြီးလွန်းနေနိုင်ပါသည်။",
            chat_id=user_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    
    # Cleanup temp file in background
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
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    logger.info("🎵 Myanmar Music Bot Started!")
    print("=" * 50)
    print("🤖 MUSIC BOT IS RUNNING...")
    print("📢 Support: @k_raw_official")
    print("=" * 50)
    
    # Start bot polling in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Run Flask app on port 8080 (required for Render)
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port)
