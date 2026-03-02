import os
import telebot
import psycopg2
from collections import defaultdict
import time
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

media_groups = defaultdict(list)
admin_state = {}

print("Database connected successfully.")

# ================= TABLES =================

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    status TEXT DEFAULT 'active',
    banned BOOLEAN DEFAULT FALSE
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS mappings (
    id SERIAL PRIMARY KEY,
    source_id BIGINT UNIQUE,
    target_id BIGINT,
    active BOOLEAN DEFAULT TRUE,
    forward_count BIGINT DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS forward_tracking (
    receiver_message_id BIGINT PRIMARY KEY,
    original_user_id BIGINT,
    original_username TEXT,
    mapping_id BIGINT,
    media_group_id TEXT,
    target_chat_id BIGINT
)
""")

conn.commit()

print("Tables ready.")
# ================= UTIL =================

def is_admin(user_id):
    return user_id == ADMIN_ID


# ================= ADD MAPPING =================

@bot.message_handler(commands=['addmap'])
def add_map(message):
    if not is_admin(message.from_user.id):
        return
    
    admin_state[message.from_user.id] = {"step": "source"}
    bot.reply_to(message, "Forward a message from SOURCE group.")


@bot.message_handler(func=lambda m: is_admin(m.from_user.id))
def handle_admin_mapping(message):

    if message.from_user.id not in admin_state:
        return

    if not message.forward_from_chat:
        bot.reply_to(message, "Please forward a message from a group.")
        return

    chat_id = message.forward_from_chat.id
    state = admin_state[message.from_user.id]

    # Step 1: Save source
    if state["step"] == "source":
        state["source"] = chat_id
        state["step"] = "target"
        bot.reply_to(message, "Now forward a message from TARGET group.")

    # Step 2: Save target
    elif state["step"] == "target":

        source_id = state["source"]
        target_id = chat_id

        cur.execute("""
            INSERT INTO mappings (source_id, target_id)
            VALUES (%s, %s)
            ON CONFLICT (source_id)
            DO UPDATE SET target_id = EXCLUDED.target_id
        """, (source_id, target_id))

        conn.commit()

        del admin_state[message.from_user.id]
        bot.reply_to(message, "Mapping saved successfully.")
# ================= FORWARD SYSTEM (STEP 3) =================

# ================= FORWARD SYSTEM (STEP 4 - WITH ALBUM) =================

# ================= FORWARD SYSTEM (STEP 5 - WITH TRACKING) =================

MEDIA_TYPES = ["photo", "video", "document", "audio"]

@bot.message_handler(content_types=MEDIA_TYPES)
def forward_media(message):

    # 1️⃣ Get mapping
    cur.execute(
        "SELECT id, target_id FROM mappings WHERE source_id=%s AND active=TRUE",
        (message.chat.id,)
    )
    result = cur.fetchone()

    if not result:
        return

    map_id, target_id = result
    # ================= CHECK BAN =================
    cur.execute("SELECT banned FROM users WHERE user_id=%s", (message.from_user.id,))
    row = cur.fetchone()

    if row and row[0] is True:
        return

    # ================= ALBUM =================
    if message.media_group_id:

        media_groups[message.media_group_id].append(message)
        time.sleep(1)

        album = media_groups.pop(message.media_group_id, None)
        if not album:
            return

        media_list = []

        for msg in album:
            if msg.content_type == "photo":
                media_list.append(
                    telebot.types.InputMediaPhoto(
                        msg.photo[-1].file_id,
                        caption=msg.caption
                    )
                )
            elif msg.content_type == "video":
                media_list.append(
                    telebot.types.InputMediaVideo(
                        msg.video.file_id,
                        caption=msg.caption
                    )
                )

        if not media_list:
            return

        try:
            sent_messages = bot.send_media_group(target_id, media_list)

            # 🔥 TRACK EACH MESSAGE
            for sent in sent_messages:
                cur.execute("""
                    INSERT INTO forward_tracking
                    (receiver_message_id, original_user_id, original_username, mapping_id, media_group_id, target_chat_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    sent.message_id,
                    album[0].from_user.id,
                    album[0].from_user.username,
                    map_id,
                    album[0].media_group_id,
                    target_id
                ))

            cur.execute(
                "UPDATE mappings SET forward_count = forward_count + 1 WHERE id=%s",
                (map_id,)
            )
            conn.commit()

        except Exception as e:
            print("Album forward error:", e)

    # ================= SINGLE MEDIA =================
    else:
        try:
            sent = bot.copy_message(target_id, message.chat.id, message.message_id)

            # 🔥 TRACK MESSAGE
            cur.execute("""
                INSERT INTO forward_tracking
                (receiver_message_id, original_user_id, original_username, mapping_id, media_group_id, target_chat_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                sent.message_id,
                message.from_user.id,
                message.from_user.username,
                map_id,
                None,
                target_id
            ))

            cur.execute(
                "UPDATE mappings SET forward_count = forward_count + 1 WHERE id=%s",
                (map_id,)
            )
            conn.commit()

        except Exception as e:
            print("Forward error:", e)
# ================= FORWARD SYSTEM (STEP 5 - WITH TRACKING) =================

MEDIA_TYPES = ["photo", "video", "document", "audio"]

@bot.message_handler(content_types=MEDIA_TYPES)
def forward_media(message):

    # 1️⃣ Get mapping
    cur.execute(
        "SELECT id, target_id FROM mappings WHERE source_id=%s AND active=TRUE",
        (message.chat.id,)
    )
    result = cur.fetchone()

    if not result:
        return

    map_id, target_id = result

    # ================= ALBUM =================
    if message.media_group_id:

        media_groups[message.media_group_id].append(message)
        time.sleep(1)

        album = media_groups.pop(message.media_group_id, None)
        if not album:
            return

        media_list = []

        for msg in album:
            if msg.content_type == "photo":
                media_list.append(
                    telebot.types.InputMediaPhoto(
                        msg.photo[-1].file_id,
                        caption=msg.caption
                    )
                )
            elif msg.content_type == "video":
                media_list.append(
                    telebot.types.InputMediaVideo(
                        msg.video.file_id,
                        caption=msg.caption
                    )
                )

        if not media_list:
            return

        try:
            sent_messages = bot.send_media_group(target_id, media_list)

            # 🔥 TRACK EACH MESSAGE
            for sent in sent_messages:
                cur.execute("""
                    INSERT INTO forward_tracking
                    (receiver_message_id, original_user_id, original_username, mapping_id, media_group_id, target_chat_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    sent.message_id,
                    album[0].from_user.id,
                    album[0].from_user.username,
                    map_id,
                    album[0].media_group_id,
                    target_id
                ))

            cur.execute(
                "UPDATE mappings SET forward_count = forward_count + 1 WHERE id=%s",
                (map_id,)
            )
            conn.commit()

        except Exception as e:
            print("Album forward error:", e)

    # ================= SINGLE MEDIA =================
    else:
        try:
            sent = bot.copy_message(target_id, message.chat.id, message.message_id)

            # 🔥 TRACK MESSAGE
            cur.execute("""
                INSERT INTO forward_tracking
                (receiver_message_id, original_user_id, original_username, mapping_id, media_group_id, target_chat_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                sent.message_id,
                message.from_user.id,
                message.from_user.username,
                map_id,
                None,
                target_id
            ))

            cur.execute(
                "UPDATE mappings SET forward_count = forward_count + 1 WHERE id=%s",
                (map_id,)
            )
            conn.commit()

        except Exception as e:
            print("Forward error:", e)
# ================= ADMIN: /ban =================

@bot.message_handler(commands=['ban'])
def ban_user(message):

    if not is_admin(message.from_user.id):
        return

    if not message.reply_to_message:
        bot.reply_to(message, "Reply to a forwarded message.")
        return

    replied_id = message.reply_to_message.message_id

    # Get original user
    cur.execute("""
        SELECT original_user_id
        FROM forward_tracking
        WHERE receiver_message_id=%s
    """, (replied_id,))

    data = cur.fetchone()

    if not data:
        bot.reply_to(message, "No tracking data found.")
        return

    user_id = data[0]

    # Ensure user exists in users table
    cur.execute("""
        INSERT INTO users (user_id, banned)
        VALUES (%s, TRUE)
        ON CONFLICT (user_id)
        DO UPDATE SET banned = TRUE
    """, (user_id,))

    conn.commit()

    bot.reply_to(message, "🚫 User banned successfully.")
# ================= ADMIN: /delete =================

@bot.message_handler(commands=['delete'])
def delete_user_messages(message):

    if not is_admin(message.from_user.id):
        return

    if not message.reply_to_message:
        bot.reply_to(message, "Reply to a forwarded message.")
        return

    replied_id = message.reply_to_message.message_id

    # Find original user
    cur.execute("""
        SELECT original_user_id
        FROM forward_tracking
        WHERE receiver_message_id=%s
    """, (replied_id,))

    data = cur.fetchone()

    if not data:
        bot.reply_to(message, "No tracking data found.")
        return

    user_id = data[0]

    # Get all forwarded messages of this user
    cur.execute("""
        SELECT receiver_message_id, target_chat_id
        FROM forward_tracking
        WHERE original_user_id=%s
    """, (user_id,))

    rows = cur.fetchall()

    deleted = 0

    for msg_id, chat_id in rows:
        try:
            bot.delete_message(chat_id, msg_id)
            deleted += 1
        except:
            pass

    bot.reply_to(message, f"🗑 Deleted {deleted} messages.")
# ================= RUN =================

print("Bot started...")
bot.infinity_polling(skip_pending=True)
