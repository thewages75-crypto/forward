import telebot
import psycopg2
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================

BOT_TOKEN = "8052676385:AAEtbmDGuJrEMDOnaMLtL--r1FcxePLjZRs"

ADMIN_ID = 7949704649

bot = telebot.TeleBot(BOT_TOKEN)

# ================= DATABASE =================

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

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

# ================= UTIL =================

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_user_status(user_id):
    cur.execute("SELECT status FROM users WHERE user_id=%s", (user_id,))
    result = cur.fetchone()
    return result[0] if result else None

# ================= USER PANEL =================

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()

    if is_admin(message.from_user.id):
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
    else:
        markup.add(InlineKeyboardButton("📩 Request Access", callback_data="request_access"))
        markup.add(InlineKeyboardButton("📊 My Status", callback_data="my_status"))

    bot.send_message(message.chat.id, "Welcome to Media Router Bot", reply_markup=markup)

# ================= CALLBACKS =================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):

    user_id = call.from_user.id

    # USER REQUEST ACCESS
    if call.data == "request_access":
        cur.execute("INSERT INTO users (user_id, status) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user_id, "pending"))
        conn.commit()

        bot.send_message(call.message.chat.id, "Access request sent to admin.")
        bot.send_message(ADMIN_ID, f"User {user_id} requested access.\nApprove?",
                         reply_markup=approve_keyboard(user_id))

    # CHECK STATUS
    elif call.data == "my_status":
        status = get_user_status(user_id)
        bot.send_message(call.message.chat.id, f"Your status: {status}")

    # ADMIN PANEL
    elif call.data == "admin_panel" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 Pending Requests", callback_data="pending"))
        markup.add(InlineKeyboardButton("➕ Add Mapping", callback_data="add_map"))
        markup.add(InlineKeyboardButton("📑 View Mappings", callback_data="view_maps"))
        bot.send_message(call.message.chat.id, "Admin Panel", reply_markup=markup)

    # VIEW PENDING
    elif call.data == "pending" and is_admin(user_id):
        cur.execute("SELECT user_id FROM users WHERE status='pending'")
        users = cur.fetchall()
        if not users:
            bot.send_message(call.message.chat.id, "No pending requests.")
        else:
            for u in users:
                bot.send_message(call.message.chat.id,
                                 f"Approve user {u[0]}?",
                                 reply_markup=approve_keyboard(u[0]))

    # VIEW MAPPINGS
    elif call.data == "view_maps" and is_admin(user_id):
        cur.execute("SELECT id, source_id, target_id, active FROM mappings")
        maps = cur.fetchall()
        if not maps:
            bot.send_message(call.message.chat.id, "No mappings found.")
        else:
            for m in maps:
                bot.send_message(call.message.chat.id,
                                 f"ID: {m[0]}\nSource: {m[1]}\nTarget: {m[2]}\nActive: {m[3]}")

    # APPROVE USER
    elif call.data.startswith("approve_") and is_admin(user_id):
        target_user = int(call.data.split("_")[1])
        cur.execute("UPDATE users SET status='approved' WHERE user_id=%s", (target_user,))
        conn.commit()
        bot.send_message(call.message.chat.id, f"User {target_user} approved.")
        bot.send_message(target_user, "Your access has been approved.")

# ================= APPROVE KEYBOARD =================

def approve_keyboard(user_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}")
    )
    return markup

# ================= FORWARD ENGINE =================

MEDIA_TYPES = ["photo", "video", "document", "audio", "voice", "animation"]

@bot.message_handler(content_types=MEDIA_TYPES)
def forward_media(message):

    user_status = get_user_status(message.from_user.id)
    if user_status != "approved":
        return

    cur.execute("SELECT target_id FROM mappings WHERE source_id=%s AND active=TRUE",
                (message.chat.id,))
    mapping = cur.fetchone()

    if mapping:
        target_id = mapping[0]
        try:
            bot.copy_message(target_id, message.chat.id, message.message_id)
        except Exception as e:
            print("Forward error:", e)

print("Bot running...")
bot.infinity_polling()
