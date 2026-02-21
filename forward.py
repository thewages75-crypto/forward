import telebot
import sqlite3

BOT_TOKEN = "8506525365:AAFp3b9_TBam2bE2d5838mqh1ZNKe7aVYVU"
ADMIN_ID = 8031705675  # your telegram id

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect("forward.db", check_same_thread=False)
cursor = conn.cursor()

# -------- DATABASE --------

cursor.execute("CREATE TABLE IF NOT EXISTS sources (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS targets (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

conn.commit()

# Default settings
def set_default():
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('forward_enabled','true')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('media_only','false')")
    conn.commit()

set_default()

# -------- ADMIN CHECK --------

def is_admin(user_id):
    return user_id == ADMIN_ID

# -------- ADMIN COMMANDS --------

@bot.message_handler(commands=['addsource'])
def add_source(message):
    if not is_admin(message.from_user.id):
        return
    
    chat_id = int(message.text.split()[1])
    cursor.execute("INSERT OR IGNORE INTO sources VALUES (?)", (chat_id,))
    conn.commit()
    bot.reply_to(message, "Source added.")

@bot.message_handler(commands=['addtarget'])
def add_target(message):
    if not is_admin(message.from_user.id):
        return
    
    chat_id = int(message.text.split()[1])
    cursor.execute("INSERT OR IGNORE INTO targets VALUES (?)", (chat_id,))
    conn.commit()
    bot.reply_to(message, "Target added.")

@bot.message_handler(commands=['removesource'])
def remove_source(message):
    if not is_admin(message.from_user.id):
        return
    
    chat_id = int(message.text.split()[1])
    cursor.execute("DELETE FROM sources WHERE chat_id=?", (chat_id,))
    conn.commit()
    bot.reply_to(message, "Source removed.")

@bot.message_handler(commands=['removetarget'])
def remove_target(message):
    if not is_admin(message.from_user.id):
        return
    
    chat_id = int(message.text.split()[1])
    cursor.execute("DELETE FROM targets WHERE chat_id=?", (chat_id,))
    conn.commit()
    bot.reply_to(message, "Target removed.")

@bot.message_handler(commands=['enable'])
def enable_forward(message):
    if not is_admin(message.from_user.id):
        return
    
    cursor.execute("UPDATE settings SET value='true' WHERE key='forward_enabled'")
    conn.commit()
    bot.reply_to(message, "Forwarding enabled.")

@bot.message_handler(commands=['disable'])
def disable_forward(message):
    if not is_admin(message.from_user.id):
        return
    
    cursor.execute("UPDATE settings SET value='false' WHERE key='forward_enabled'")
    conn.commit()
    bot.reply_to(message, "Forwarding disabled.")

@bot.message_handler(commands=['mediaonly'])
def media_only(message):
    if not is_admin(message.from_user.id):
        return
    
    cursor.execute("UPDATE settings SET value='true' WHERE key='media_only'")
    conn.commit()
    bot.reply_to(message, "Media-only mode enabled.")

@bot.message_handler(commands=['allmessages'])
def all_messages(message):
    if not is_admin(message.from_user.id):
        return
    
    cursor.execute("UPDATE settings SET value='false' WHERE key='media_only'")
    conn.commit()
    bot.reply_to(message, "All messages mode enabled.")

# -------- FORWARD LOGIC --------

@bot.message_handler(func=lambda message: True, content_types=[
    'text','photo','video','document','audio','voice','animation','sticker'
])
def forward_handler(message):

    cursor.execute("SELECT value FROM settings WHERE key='forward_enabled'")
    if cursor.fetchone()[0] == 'false':
        return

    cursor.execute("SELECT chat_id FROM sources")
    sources = [x[0] for x in cursor.fetchall()]
    
    if message.chat.id not in sources:
        return

    cursor.execute("SELECT value FROM settings WHERE key='media_only'")
    media_only_mode = cursor.fetchone()[0] == 'true'

    if media_only_mode and message.content_type == "text":
        return

    cursor.execute("SELECT chat_id FROM targets")
    targets = [x[0] for x in cursor.fetchall()]

    for target in targets:
        try:
            bot.forward_message(target, message.chat.id, message.message_id)
        except Exception as e:
            print("Forward error:", e)
import telebot

BOT_TOKEN = "8506525365:AAFp3b9_TBam2bE2d5838mqh1ZNKe7aVYVU"
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def get_chat_id(message):
    print("Chat ID:", message.chat.id)

bot.polling()
print("Bot Running...")
bot.infinity_polling()
