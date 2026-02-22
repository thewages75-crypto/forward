import os
import telebot
import psycopg2
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from collections import defaultdict
import time

media_groups = defaultdict(list)
# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL missing")

# ================= INIT =================

bot = telebot.TeleBot(BOT_TOKEN)
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cur = conn.cursor()

# ================= RUNTIME STATE =================
admin_state = {}

# ================= UTIL FUNCTIONS =================
def is_admin(user_id):
    return user_id == ADMIN_ID
# ================= TABLES =================

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    status TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS mappings (
    id SERIAL PRIMARY KEY,
    source_id BIGINT UNIQUE,
    target_id BIGINT,
    active BOOLEAN DEFAULT TRUE
)
""")
cur.execute("""
ALTER TABLE mappings
ADD COLUMN IF NOT EXISTS forward_count BIGINT DEFAULT 0
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS media_logs (
    file_id TEXT PRIMARY KEY,
    source_id BIGINT,
    forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.commit()

conn.commit()

print("Database connected successfully.")
# ================= UTIL =================
admin_state = {}

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_user_status(user_id):
    cur.execute("SELECT status FROM users WHERE user_id=%s", (user_id,))
    result = cur.fetchone()
    return result[0] if result else None

# ================= START =================

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()

    if is_admin(message.from_user.id):
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
    else:
        markup.add(InlineKeyboardButton("📩 Request Access", callback_data="request_access"))
        markup.add(InlineKeyboardButton("📊 My Status", callback_data="my_status"))

    bot.send_message(message.chat.id, "Welcome to Media Router Bot", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):

    user_id = call.from_user.id

    # ================= ADMIN PANEL =================
    if call.data == "admin_panel" and is_admin(user_id):

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Add Mapping", callback_data="add_map"))
        markup.add(InlineKeyboardButton("📋 View Mappings", callback_data="view_maps"))
        markup.add(InlineKeyboardButton("🔄 Toggle Mapping", callback_data="toggle_map"))
        markup.add(InlineKeyboardButton("📊 Stats", callback_data="stats"))

        bot.send_message(call.message.chat.id, "👑 Admin Panel", reply_markup=markup)

    # ================= ADD MAPPING =================
    elif call.data == "add_map" and is_admin(user_id):

        admin_state[user_id] = {"step": "source"}

        bot.send_message(
            call.message.chat.id,
            "Forward ANY message from the SOURCE group/channel."
        )

    # ================= VIEW MAPPINGS =================
    elif call.data == "view_maps" and is_admin(user_id):

        cur.execute("SELECT id, source_id, target_id, active FROM mappings")
        rows = cur.fetchall()

        if not rows:
            bot.send_message(call.message.chat.id, "No mappings found.")
        else:
            for row in rows:
                bot.send_message(
                    call.message.chat.id,
                    f"ID: {row[0]}\nSource: {row[1]}\nTarget: {row[2]}\nActive: {row[3]}"
                )

    # ================= TOGGLE MENU =================
    elif call.data == "toggle_map" and is_admin(user_id):

        cur.execute("SELECT id, source_id, active FROM mappings")
        rows = cur.fetchall()

        if not rows:
            bot.send_message(call.message.chat.id, "No mappings found.")
        else:
            for row in rows:
                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton(
                        "Toggle",
                        callback_data=f"toggle_{row[0]}"
                    )
                )
                bot.send_message(
                    call.message.chat.id,
                    f"ID: {row[0]}\nSource: {row[1]}\nActive: {row[2]}",
                    reply_markup=markup
                )

    # ================= TOGGLE ACTION =================
    elif call.data.startswith("toggle_") and is_admin(user_id):

        map_id = int(call.data.split("_")[1])

        cur.execute(
            "UPDATE mappings SET active = NOT active WHERE id=%s RETURNING active",
            (map_id,)
        )
        new_status = cur.fetchone()[0]
        conn.commit()

        bot.send_message(call.message.chat.id,
                         f"Mapping {map_id} active = {new_status}")

    # ================= STATS =================
    elif call.data == "stats" and is_admin(user_id):

        cur.execute("SELECT COUNT(*) FROM mappings")
        total_maps = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(forward_count), 0) FROM mappings")
        total_forwards = cur.fetchone()[0]

        bot.send_message(
            call.message.chat.id,
            f"Total mappings: {total_maps}\nTotal forwards: {total_forwards}"
        )
@bot.message_handler(func=lambda message: is_admin(message.from_user.id))
def handle_admin_input(message):

    user_id = message.from_user.id

    if user_id not in admin_state:
        return

    state = admin_state[user_id]

    # Make sure message is forwarded
    if not message.forward_from_chat:
        bot.reply_to(message, "Please forward a message from the group/channel.")
        return

    chat_id = message.forward_from_chat.id

    # STEP 1 — GET SOURCE
    if state["step"] == "source":
        admin_state[user_id]["source"] = chat_id
        admin_state[user_id]["step"] = "target"

        bot.reply_to(message,
                     f"Source saved: {chat_id}\n\nNow forward a message from TARGET group/channel.")

    # STEP 2 — GET TARGET
    elif state["step"] == "target":

        source_id = admin_state[user_id]["source"]
        target_id = chat_id

        cur.execute(
            "INSERT INTO mappings (source_id, target_id, active) VALUES (%s, %s, TRUE)",
            (source_id, target_id)
        )
        conn.commit()

        bot.reply_to(message,
                     f"Mapping created successfully.\n\nSource: {source_id}\nTarget: {target_id}")

        del admin_state[user_id]
MEDIA_TYPES = ["photo", "video", "document", "audio"]

@bot.message_handler(content_types=MEDIA_TYPES)
def forward_media(message):

    cur.execute(
        "SELECT id, target_id FROM mappings WHERE source_id=%s AND active=TRUE",
        (message.chat.id,)
    )
    result = cur.fetchone()

    if not result:
        return

    map_id, target_id = result

    # If message is part of album
    if message.media_group_id:

        media_groups[message.media_group_id].append(message)

        # Wait briefly to collect full album
        time.sleep(1)

        # Only process once
        if len(media_groups[message.media_group_id]) > 0:

            album = media_groups.pop(message.media_group_id)

            media_list = []

            for msg in album:
                if msg.content_type == "photo":
                    media_list.append(
                        telebot.types.InputMediaPhoto(
                            msg.photo[-1].file_id,
                            caption=msg.caption if msg.caption else None
                        )
                    )

                elif msg.content_type == "video":
                    media_list.append(
                        telebot.types.InputMediaVideo(
                            msg.video.file_id,
                            caption=msg.caption if msg.caption else None
                        )
                    )

            try:
                bot.send_media_group(target_id, media_list)

                cur.execute(
                    "UPDATE mappings SET forward_count = forward_count + 1 WHERE id=%s",
                    (map_id,)
                )
                conn.commit()


            except Exception as e:
                print("Album forward error:", e)

    else:
        # Single media (normal case)
        # Get file_id depending on type
        file_id = None

        if message.content_type == "photo":
            file_id = message.photo[-1].file_id

        elif message.content_type == "video":
            file_id = message.video.file_id

        elif message.content_type == "document":
            file_id = message.document.file_id

        elif message.content_type == "audio":
            file_id = message.audio.file_id

        # If no file_id, skip
        if not file_id:
            return

        # Check duplicate
        cur.execute("SELECT file_id FROM media_logs WHERE file_id=%s", (file_id,))
        exists = cur.fetchone()

        if exists:
            print("Duplicate detected, skipping.")
            return

        # Forward
        try:
            bot.copy_message(target_id, message.chat.id, message.message_id)

            # Store file_id
            cur.execute(
                "INSERT INTO media_logs (file_id, source_id) VALUES (%s, %s)",
                (file_id, message.chat.id)
            )
            conn.commit()

        except Exception as e:
            print("Forward error:", e)
print("Bot started...")
bot.infinity_polling(skip_pending=True)
