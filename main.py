import re
import requests
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- AUTH & CONFIG ---
OWM_API_KEY = "a2f23d47fb176514df23ae74a6cf13aa"
TG_TOKEN = "8206102049:AAGIK_k6sNh9DgZsNtMotluiUEoo5NAZb4U"
PREFIX = "!"

# --- FLASK SERVER (Keep-Alive for Render) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is active and watching the skies!", 200

def run_web_server():
    # Render assigns a port dynamically via the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- LOCALIZATION MAP ---
TRIGGER_MAP = {
    'weather': ('en', 'full'), 'time': ('en', 'time'), 'temp': ('en', 'temp'), 'cmd': ('en', 'help'),
    'погода': ('ru', 'full'), 'время': ('ru', 'time'), 'температура': ('ru', 'temp'), 'команды': ('ru', 'help'),
    'clima': ('es', 'full'), 'hora': ('es', 'time'), 'temperatura': ('es', 'temp'), 'comandos': ('es', 'help'),
    '天气': ('zh', 'full'), '时间': ('zh', 'time'), '温度': ('zh', 'temp'), '指令': ('zh', 'help')
}

HELP_STRINGS = {
    'en': "📋 **Commands:**\n!weather [city]\n!time [city]\n!temp [city]",
    'ru': "📋 **Команды:**\n!погода [город]\n!время [город]\n!температура [город]",
    'es': "📋 **Comandos:**\n!clima [ciudad]\n!hora [ciudad]\n!temperatura [ciudad]",
    'zh': "📋 **指令:**\n!天气 [城市]\n!时间 [城市]\n!温度 [城市]"
}

STRINGS = {
    'en': {'t': 'Temperature', 'lt': 'Local Time', 'st': 'Status', 'err': 'City not found'},
    'ru': {'t': 'Температура', 'lt': 'Время', 'st': 'Статус', 'err': 'Город не найден'},
    'es': {'t': 'Temperatura', 'lt': 'Hora local', 'st': 'Estado', 'err': 'Ciudad no encontrada'},
    'zh': {'t': '温度', 'lt': '当地时间', 'st': '天气状况', 'err': '找不到城市'}
}

ALL_KEYWORDS = "|".join(TRIGGER_MAP.keys())

async def bot_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.lower()
    if not text.startswith(PREFIX): return

    # Regex: Detect Prefix + Keyword + Optional City
    pattern = rf"^{PREFIX}({ALL_KEYWORDS})(?:\s+(.*))?$"
    match = re.search(pattern, text)
    if not match: return

    keyword = match.group(1)
    city_query = match.group(2).strip() if match.group(2) else None
    lang_code, mode = TRIGGER_MAP[keyword]

    # Handle Help Command
    if mode == 'help':
        await update.message.reply_text(HELP_STRINGS[lang_code], parse_mode="Markdown")
        return

    # Error if city is missing for data commands
    if not city_query:
        err_msg = "Please provide a city." if lang_code == 'en' else "Укажите город."
        await update.message.reply_text(f"📍 {err_msg}")
        return

    # API Call
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_query}&appid={OWM_API_KEY}&units=metric&lang={lang_code}"
    res = requests.get(url).json()

    if res.get("cod") != 200:
        await update.message.reply_text(STRINGS[lang_code]['err'])
        return

    # Data Extraction
    city = res['name']
    temp = f"{res['main']['temp']}°C"
    desc = res['weather'][0]['description'].capitalize()
    
    # Timezone Math
    offset = res['timezone']
    local_time = (datetime.utcnow() + timedelta(seconds=offset)).strftime("%H:%M")

    # Response Building
    if mode == 'time':
        response = f"🕒 {city}: {local_time}"
    elif mode == 'temp':
        response = f"🌡 {city}: {temp}"
    else:
        s = STRINGS[lang_code]
        response = f"📍 **{city}, {res['sys']['country']}**\n🌡 {s['t']}: {temp}\n🕒 {s['lt']}: {local_time}\n☁️ {s['st']}: {desc}"

    await update.message.reply_text(response, parse_mode="Markdown")

if __name__ == "__main__":
    # Start the Flask web server in a background thread
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # Start the Telegram bot polling
    application = Application.builder().token(TG_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic))
    print("🚀 Bot and Health-Check Server starting...")
    application.run_polling()
