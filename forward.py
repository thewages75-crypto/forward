import telebot
import sqlite3
from telebot.types import BotCommand

BOT_TOKEN = "8330293981:AAFTEqKOPNMQtonlVE-xnomlPzsAXVVd-Pg"
ADMIN_ID = 8352768379  # your telegram id

bot = telebot.TeleBot(BOT_TOKEN)

# ===== DATABASE SETUP =====

conn = sqlite3.connect("forward.db", check_same_thread=False)
cursor = conn.cursor()

# ----- USERS TABLE -----
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    approved INTEGER DEFAULT 0
)
""")

# ----- ROUTES TABLE -----
cursor.execute("""
CREATE TABLE IF NOT EXISTS routes (
    source_chat INTEGER,
    target_chat INTEGER,
    anon_mode INTEGER DEFAULT 0
)
""")

# ----- USER GROUP MODES TABLE -----
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_group_modes (
    user_id INTEGER,
    source_chat INTEGER,
    anon_mode INTEGER DEFAULT 0,
    forwarding_enabled INTEGER DEFAULT 1,
    forward_text INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, source_chat)
)
""")

# ----- SETTINGS TABLE -----
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

# Insert default global settings
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('system_open','0')")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('forwarding_enabled','1')")

conn.commit()

print("Bot is running...")
bot.infinity_polling()
