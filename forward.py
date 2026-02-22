import telebot
import sqlite3
from telebot.types import BotCommand

BOT_TOKEN = "8330293981:AAFTEqKOPNMQtonlVE-xnomlPzsAXVVd-Pg"
ADMIN_ID = 8352768379  # your telegram id

bot = telebot.TeleBot(BOT_TOKEN)

# ===== DATABASE SETUP =====
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

# ===== CHECK USER ACCESS FOR GROUP COMMANDS =====

def can_user_use_system(user_id):
    if is_system_open():
        return True
    return is_user_approved(user_id)
# ===== TOTAL ANONYMOUS SENDER =====

def send_total_anonymous(message, target):

    if message.content_type == "photo":
        bot.send_photo(target, message.photo[-1].file_id)

    elif message.content_type == "video":
        bot.send_video(target, message.video.file_id)

    elif message.content_type == "document":
        bot.send_document(target, message.document.file_id)

    elif message.content_type == "audio":
        bot.send_audio(target, message.audio.file_id)

    elif message.content_type == "voice":
        bot.send_voice(target, message.voice.file_id)

    elif message.content_type == "animation":
        bot.send_animation(target, message.animation.file_id)
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
# ===== ADMIN ADD ROUTE =====

@bot.message_handler(commands=['addroute'])
def add_route(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) < 3:
        bot.reply_to(message, "Usage: /addroute <source_chat> <target_chat> [mode]")
        return
    try:
        source_chat = int(parts[1])
        target_chat = int(parts[2])

    except ValueError:
        bot.reply_to(message, "Invalid chat IDs.")
        return

    mode = 0
    if len(parts) >= 4:
        mode = int(parts[3])
        if mode not in (0, 1, 2):
            bot.reply_to(message, "Mode must be 0, 1, or 2.")
            return

    cursor.execute(
        "INSERT INTO routes (source_chat, target_chat, anon_mode) VALUES (?, ?, ?)",
        (source_chat, target_chat, mode)
    )
    conn.commit()

    bot.reply_to(message, f"Route added:\n{source_chat} → {target_chat}\nMode: {mode}")
# ===== ADMIN REMOVE ROUTE =====

@bot.message_handler(commands=['removeroute'])
def remove_route(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) < 3:
        bot.reply_to(message, "Usage: /removeroute <source_chat> <target_chat>")
        return

    source_chat = int(parts[1])
    target_chat = int(parts[2])

    cursor.execute(
        "DELETE FROM routes WHERE source_chat=? AND target_chat=?",
        (source_chat, target_chat)
    )
    conn.commit()

    bot.reply_to(message, f"Route removed:\n{source_chat} → {target_chat}")
    
# ===== ADMIN LIST ROUTES =====

@bot.message_handler(commands=['listroutes'])
def list_routes(message):
    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    cursor.execute("SELECT source_chat, target_chat, anon_mode FROM routes")
    rows = cursor.fetchall()

    if not rows:
        bot.reply_to(message, "No routes configured.")
        return

    text = "Configured Routes:\n\n"

    for source, target, mode in rows:
        text += f"{source} → {target} | Mode: {mode}\n"

    bot.reply_to(message, text)
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
@bot.message_handler(func=lambda id: True)
def get_id(id):
    print("Group ID:", m.chat.id)
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
# ===== USER TEXT ON =====

@bot.message_handler(commands=['text_on'])
def text_on(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, forward_text)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET forward_text=1
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Text forwarding enabled for this group.")

# ===== MENU COMMAND =====

@bot.message_handler(commands=['menu'])
def show_menu(message):

    user_id = message.from_user.id
    chat_type = message.chat.type

    # ---- PRIVATE CHAT ----
    if chat_type == "private":

        if is_admin(user_id):
            text = """
📌 ADMIN COMMANDS:

/approve <user_id>
/removeuser <user_id>
/open
/close
/global_stop
/global_start
/addroute <source> <target> <mode>
/removeroute <source> <target>
/listroutes
/stats
"""
        else:
            text = """
📌 USER COMMANDS:

/request - Request access
/menu - Show this menu
"""
        bot.reply_to(message, text)
        return

    # ---- GROUP CHAT ----
    if not can_user_use_system(user_id):
        return

    text = """
📌 GROUP USER COMMANDS:

/anon_semi
/anon_total
/anon_off
/stop
/start
/text_on
/text_off
/menu
"""
    bot.reply_to(message, text)
# ===== ADMIN STATS =====

@bot.message_handler(commands=['stats'])
def stats(message):

    if message.chat.type != "private":
        return

    if not is_admin(message.from_user.id):
        return

    # Approved users
    cursor.execute("SELECT COUNT(*) FROM users WHERE approved=1")
    approved_count = cursor.fetchone()[0]

    # Total routes
    cursor.execute("SELECT COUNT(*) FROM routes")
    route_count = cursor.fetchone()[0]

    # Total overrides
    cursor.execute("SELECT COUNT(*) FROM user_group_modes")
    override_count = cursor.fetchone()[0]

    # System settings
    system_status = "OPEN" if is_system_open() else "CLOSED"
    forwarding_status = "ON" if is_global_forwarding_enabled() else "OFF"

    text = f"""
📊 SYSTEM STATS

Approved Users: {approved_count}
Routes: {route_count}
User Overrides: {override_count}

System: {system_status}
Global Forwarding: {forwarding_status}
"""

    bot.reply_to(message, text)
# ===== USER TEXT OFF =====

@bot.message_handler(commands=['text_off'])
def text_off(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, forward_text)
        VALUES (?, ?, 0)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET forward_text=0
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Text forwarding disabled for this group.")
# ===== USER START FORWARDING =====

@bot.message_handler(commands=['start'])
def start_forwarding(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, forwarding_enabled)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET forwarding_enabled=1
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Forwarding resumed for you in this group.")
# ===== USER STOP FORWARDING =====

@bot.message_handler(commands=['stop'])
def stop_forwarding(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, forwarding_enabled)
        VALUES (?, ?, 0)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET forwarding_enabled=0
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Forwarding stopped for you in this group.")
# ===== USER ANON OFF =====

@bot.message_handler(commands=['anon_off'])
def anon_off(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, anon_mode)
        VALUES (?, ?, 0)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET anon_mode=0
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Anonymous mode disabled for this group.")
# ===== USER ANON TOTAL =====

@bot.message_handler(commands=['anon_total'])
def anon_total(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, anon_mode)
        VALUES (?, ?, 2)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET anon_mode=2
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Total anonymous mode enabled for this group.")
# ===== USER ANON SEMI =====

@bot.message_handler(commands=['anon_semi'])
def anon_semi(message):

    if message.chat.type == "private":
        return

    user_id = message.from_user.id
    source_chat = message.chat.id

    if not can_user_use_system(user_id):
        return

    cursor.execute("""
        INSERT INTO user_group_modes (user_id, source_chat, anon_mode)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, source_chat)
        DO UPDATE SET anon_mode=1
    """, (user_id, source_chat))

    conn.commit()

    bot.reply_to(message, "Semi-anonymous mode enabled for this group.")
    
# ===== FORWARDING ENGINE =====

@bot.message_handler(func=lambda message: True, content_types=[
    'text','photo','video','document','audio','voice','animation'
])
def forward_engine(message):
    # ---- Ignore Bot Messages (Anti-loop) ----
    if message.from_user and message.from_user.is_bot:
        return
    user_id = message.from_user.id
    source_chat = message.chat.id

    # ---- Global Forwarding Check ----
    if not is_global_forwarding_enabled():
        return

    # ---- System Access Check ----
    if not is_system_open():
        if not is_user_approved(user_id):
            return

    # ---- Route Exists Check ----
    cursor.execute(
        "SELECT target_chat, anon_mode FROM routes WHERE source_chat=?",
        (source_chat,)
    )
    routes = cursor.fetchall()

    if not routes:
        return

    # ---- User Group Override ----
    cursor.execute("""
        SELECT anon_mode, forwarding_enabled, forward_text
        FROM user_group_modes
        WHERE user_id=? AND source_chat=?
    """, (user_id, source_chat))

    override = cursor.fetchone()

    if override:
        user_anon_mode, user_forward_enabled, user_forward_text = override

        if user_forward_enabled == 0:
            return
    else:
        user_anon_mode = 0
        user_forward_text = 0

    # ---- Text Rule ----
    if message.content_type == "text":
        if not override or user_forward_text == 0:
            return

    # ---- Forward Loop ----
    for target_chat, route_mode in routes:

        final_mode = user_anon_mode if user_anon_mode != 0 else route_mode

        # Block total anonymous text
        if message.content_type == "text" and final_mode == 2:
            continue

        try:
            if final_mode == 0:
                bot.forward_message(target_chat, source_chat, message.message_id)

            elif final_mode == 1:
                bot.copy_message(target_chat, source_chat, message.message_id)

            elif final_mode == 2:
                send_total_anonymous(message, target_chat)

        except Exception as e:
            print("Forward error:", e)
            
print("Bot is running...")
bot.infinity_polling()
