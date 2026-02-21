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
# ===== ACCESS CONTROL HELPERS =====

# ===== GLOBAL FORWARDING CHECK =====

def is_global_forwarding_enabled():
    cursor.execute("SELECT value FROM settings WHERE key='forwarding_enabled'")
    return cursor.fetchone()[0] == '1'
def is_admin(user_id):
    return user_id == ADMIN_ID



def is_user_approved(user_id):
    cursor.execute("SELECT approved FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] == 1


def is_system_open():
    cursor.execute("SELECT value FROM settings WHERE key='system_open'")
    return cursor.fetchone()[0] == '1'

# ===== USER REQUEST ACCESS =====

@bot.message_handler(commands=['request'])
def request_access(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    cursor.execute("INSERT OR IGNORE INTO users (user_id, approved) VALUES (?, 0)", (user_id,))
    conn.commit()

    bot.reply_to(message, "Your access request has been sent to the admin.")

    bot.send_message(
        ADMIN_ID,
        f"Access request from user: {user_id}"
    )
# ===== ADMIN APPROVE USER =====

@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /approve <user_id>")
        return

    user_id = int(parts[1])

    cursor.execute("UPDATE users SET approved=1 WHERE user_id=?", (user_id,))
    conn.commit()

    bot.reply_to(message, f"User {user_id} approved.")
# ===== ADMIN REMOVE USER =====

@bot.message_handler(commands=['removeuser'])
def remove_user(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /removeuser <user_id>")
        return

    user_id = int(parts[1])

    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()

    bot.reply_to(message, f"User {user_id} removed.")
# ===== ADMIN OPEN SYSTEM =====

@bot.message_handler(commands=['open'])
def open_system(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("UPDATE settings SET value='1' WHERE key='system_open'")
    conn.commit()

    bot.reply_to(message, "System is now OPEN.")


# ===== ADMIN CLOSE SYSTEM =====

@bot.message_handler(commands=['close'])
def close_system(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("UPDATE settings SET value='0' WHERE key='system_open'")
    conn.commit()

    bot.reply_to(message, "System is now CLOSED.")
    
# ===== ADMIN OPEN SYSTEM =====

@bot.message_handler(commands=['open'])
def open_system(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("UPDATE settings SET value='1' WHERE key='system_open'")
    conn.commit()

    bot.reply_to(message, "System is now OPEN.")


# ===== ADMIN CLOSE SYSTEM =====

@bot.message_handler(commands=['close'])
def close_system(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("UPDATE settings SET value='0' WHERE key='system_open'")
    conn.commit()

    bot.reply_to(message, "System is now CLOSED.")
    
# ===== ADMIN GLOBAL STOP =====

@bot.message_handler(commands=['global_stop'])
def global_stop(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("UPDATE settings SET value='0' WHERE key='forwarding_enabled'")
    conn.commit()

    bot.reply_to(message, "Global forwarding DISABLED.")
# ===== ADMIN GLOBAL START =====

@bot.message_handler(commands=['global_start'])
def global_start(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("UPDATE settings SET value='1' WHERE key='forwarding_enabled'")
    conn.commit()

    bot.reply_to(message, "Global forwarding ENABLED.")
print("Bot is running...")
bot.infinity_polling()
