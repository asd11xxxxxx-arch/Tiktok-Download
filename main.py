import os
import threading
import logging
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)
from yt_dlp import YoutubeDL

# --- LOGGING (Error တွေကို သိနိုင်အောင်) ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- RENDER KEEP ALIVE SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURATION ---
# Render ရဲ့ Env Vars ထဲမှာ TOKEN ထည့်ထားရင် ပိုကောင်းပါတယ်။ 
TOKEN = os.environ.get("TOKEN", "8512086853:AAHK2NEV83KsG34QqTbwGHIULZEgXVo3tW4")

CHOOSING, DOWNLOADING = range(2)

# Emoji Codes
U_WAVE, U_VIDEO, U_MUSIC, U_PHOTO, U_LINK, U_WAIT, U_CHECK, U_ERROR, U_ROCKET = (
    "\U0001F44B", "\U0001F3AC", "\U0001F3B5", "\U0001F4F8", "\U0001F517", "\U000023F3", "\U00002705", "\U0000274C", "\U0001F680"
)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"{U_VIDEO} Video (No Logo)", callback_data='video')],
        [InlineKeyboardButton(f"{U_MUSIC} Music (MP3)", callback_data='music')],
        [InlineKeyboardButton(f"{U_PHOTO} Photos (Album)", callback_data='photo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"{U_WAVE} *TikTok Downloader*\n\nဘာကို ဒေါင်းလုဒ်ဆွဲချင်ပါသလဲ?\nအောက်က Button တစ်ခုရွေးပါ။"

    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return CHOOSING

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['choice'] = query.data
    await query.edit_message_text(f"{U_ROCKET} Selected: {query.data.upper()}\n\n{U_LINK} TikTok Link ကို ပို့ပေးပါ။")
    return DOWNLOADING

# --- DOWNLOAD PROCESS ---
async def download_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    choice = context.user_data.get("choice")

    if "tiktok.com" not in url:
        await update.message.reply_text(f"{U_ERROR} Link မှားနေပါတယ် (TikTok Link သာပို့ပါ)")
        return DOWNLOADING

    status_msg = await update.message.reply_text(f"{U_WAIT} လုပ်ဆောင်နေပါပြီ...")

    # yt-dlp Options
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    if choice == "music":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if choice == "photo":
                # Photo Album တွေကို extract လုပ်ခြင်း
                image_urls = []
                if 'entries' in info:
                    image_urls = [e['url'] for e in info['entries'] if 'url' in e]
                elif info.get('thumbnails'):
                    image_urls = [info['thumbnails'][-1]['url']]
                
                if image_urls:
                    media = [InputMediaPhoto(img) for img in image_urls[:10]]
                    await update.message.reply_media_group(media)
                else:
                    await update.message.reply_text("ပုံများ ရှာမတွေ့ပါ။")
            
            else:
                file_path = ydl.prepare_filename(info)
                if choice == "music":
                    file_path = file_path.rsplit(".", 1)[0] + ".mp3"
                
                with open(file_path, "rb") as f:
                    if choice == "video":
                        await update.message.reply_video(video=f, caption=f"{U_CHECK} Done!")
                    else:
                        await update.message.reply_audio(audio=f, caption=f"{U_MUSIC} Done!")
                
                # ပို့ပြီးရင် File ပြန်ဖျက်မယ်
                if os.path.exists(file_path):
                    os.remove(file_path)

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Download Error: {e}")
        await status_msg.edit_text(f"{U_ERROR} အဆင်မပြေပါ (Private Video ဖြစ်နိုင်သလို Link သေနေတာလည်း ဖြစ်နိုင်ပါတယ်)")

    return await start(update, context)

def main():
    threading.Thread(target=run_web, daemon=True).start()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(button_click)],
            DOWNLOADING: [MessageHandler(filters.TEXT & ~filters.COMMAND, download_process)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()

