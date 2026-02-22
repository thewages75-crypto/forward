import os
import telebot
import psycopg2
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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
    source_id BIGINT,
    target_id BIGINT,
    active BOOLEAN DEFAULT TRUE
)
""")

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

    # REQUEST ACCESS
    if call.data == "request_access":

        cur.execute(
            "INSERT INTO users (user_id, status) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, "pending")
        )
        conn.commit()

        bot.send_message(call.message.chat.id, "Access request sent to admin.")

        approve_markup = InlineKeyboardMarkup()
        approve_markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}")
        )

        bot.send_message(
            ADMIN_ID,
            f"User {user_id} requested access.",
            reply_markup=approve_markup
        )

    # CHECK STATUS
    elif call.data == "my_status":
        status = get_user_status(user_id)
        bot.send_message(call.message.chat.id, f"Your status: {status}")

    # APPROVE USER
    elif call.data.startswith("approve_") and is_admin(user_id):
        target_user = int(call.data.split("_")[1])
        cur.execute("UPDATE users SET status='approved' WHERE user_id=%s", (target_user,))
        conn.commit()

        bot.send_message(call.message.chat.id, f"User {target_user} approved.")
        bot.send_message(target_user, "Your access has been approved.")
    elif call.data == "admin_panel" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Add Mapping", callback_data="add_map"))
        markup.add(InlineKeyboardButton("📋 View Mappings", callback_data="view_maps"))
        bot.send_message(call.message.chat.id, "Admin Panel", reply_markup=markup)
    elif call.data == "add_map" and is_admin(user_id):
        admin_state[user_id] = {"step": "source"}
        bot.send_message(call.message.chat.id, "Send SOURCE group/channel ID:")
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
@bot.message_handler(func=lambda message: is_admin(message.from_user.id))
def handle_admin_input(message):

    user_id = message.from_user.id

    if user_id not in admin_state:
        return

    state = admin_state[user_id]

    # Step 1: Get source
    if state["step"] == "source":
        try:
            source_id = int(message.text)
            admin_state[user_id]["source"] = source_id
            admin_state[user_id]["step"] = "target"
            bot.reply_to(message, "Now send TARGET group/channel ID:")
        except:
            bot.reply_to(message, "Invalid ID. Send numeric SOURCE ID.")

    # Step 2: Get target
    elif state["step"] == "target":
        try:
            target_id = int(message.text)
            source_id = admin_state[user_id]["source"]

            cur.execute(
                "INSERT INTO mappings (source_id, target_id, active) VALUES (%s, %s, TRUE)",
                (source_id, target_id)
            )
            conn.commit()

            bot.reply_to(message, "Mapping added successfully.")

            del admin_state[user_id]

        except:
            bot.reply_to(message, "Invalid ID. Send numeric TARGET ID.")       
MEDIA_TYPES = ["photo", "video", "document", "audio", "voice", "animation"]

@bot.message_handler(content_types=MEDIA_TYPES)
def forward_media(message):

    cur.execute(
        "SELECT target_id FROM mappings WHERE source_id=%s AND active=TRUE",
        (message.chat.id,)
    )
    result = cur.fetchone()

    if result:
        target_id = result[0]
        try:
            bot.copy_message(target_id, message.chat.id, message.message_id)
            print("Forwarded successfully")
        except Exception as e:
            print("Forward error:", e)
print("Bot started...")
bot.infinity_polling(skip_pending=True)
