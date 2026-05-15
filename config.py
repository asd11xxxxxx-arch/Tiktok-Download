import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Get from @BotFather
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")  # Get from RapidAPI
RAPIDAPI_HOST = "youtube-mp4-mp3-m4a-cdn.p.rapidapi.com"

# Cooldown (seconds)
COOLDOWN_TIME = 5

# Temp files directory
TEMP_DIR = "downloads"
