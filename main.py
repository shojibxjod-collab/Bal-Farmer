import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ── Environment Variables ──────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID  = int(os.environ.get("OWNER_ID"))

bot = telebot.TeleBot(BOT_TOKEN)

# ── In-Memory Storage ──────────────────────────────────────────────────────────
user_balance = {}   # { user_id: float }
user_state   = {}   # { user_id: str }  — tracks conversation state

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_balance(uid: int) -> float:
    return user_balance.get(uid, 0.00)

def set_balance(uid: int, amount: float):
    user_balance[uid] = amount

def set_state(uid: int, state: str):
    user_state[uid] = state

def get_state(uid: int) -> str:
    return user_state.get(uid, "")

def clear_state(uid: int):
    user_state.pop(uid, None)

# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("1️⃣ Tasks"))
    kb.row(KeyboardButton("2️⃣ Wallet"))
    kb.row(KeyboardButton("3️⃣ Withdraw"))
    return kb

def tasks_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("Create Account - Earn 0.35$"))
    kb.row(KeyboardButton("🔙 Back"))
    return kb

def task_action_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("Done ✅"))
    kb.row(KeyboardButton("Cancel Create Account ❌"))
    return kb

def back_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("Back 🔙"))
    return kb

def withdraw_method_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("Binance ✅"), KeyboardButton("bkash ✅"))
    kb.row(KeyboardButton("Back 🔙"))
    return kb

# ── /start ────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    clear_state(uid)
    bot.send_message(
        uid,
        "Hi Sir , Welcome To My Earn Zone",
        reply_markup=main_menu_keyboard()
    )

# ── /addbalance  (owner only) ─────────────────────────────────────────────────
@bot.message_handler(commands=["addbalance"])
def cmd_add_balance(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "⛔ You are not authorized.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "Usage: /addbalance USER_ID AMOUNT")
        return

    try:
        target_uid = int(parts[1])
        amount     = float(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid USER_ID or AMOUNT.")
        return

    new_balance = get_balance(target_uid) + amount
    set_balance(target_uid, new_balance)
    bot.send_message(
        message.chat.id,
        f"✅ Added {amount:.2f}$ to user {target_uid}.\n"
        f"New balance: {new_balance:.2f}$"
    )

# ── Main Text Handler ─────────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    uid  = message.from_user.id
    text = message.text.strip()
    state = get_state(uid)

    # ── Awaiting withdrawal addresses ─────────────────────────────────────────
    if state == "awaiting_binance_address":
        _process_withdrawal(uid, message, method="Binance")
        return

    if state == "awaiting_bkash_number":
        _process_withdrawal(uid, message, method="bkash")
        return

    # ── Main Menu ─────────────────────────────────────────────────────────────
    if text == "1️⃣ Tasks":
        clear_state(uid)
        bot.send_message(uid, "📋 Choose a task:", reply_markup=tasks_keyboard())

    elif text == "2️⃣ Wallet":
        clear_state(uid)
        bal = get_balance(uid)
        bot.send_message(
            uid,
            f"💰 Your Wallet Balance: {bal:.2f} $",
            reply_markup=back_keyboard()
        )

    elif text == "3️⃣ Withdraw":
        clear_state(uid)
        bot.send_message(
            uid,
            "💸 Choose your withdrawal method:",
            reply_markup=withdraw_method_keyboard()
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────
    elif text == "Create Account - Earn 0.35$":
        clear_state(uid)
        account_info = (
            "First Name 📛 = Deogrej\n"
            "Last Name = 🚫\n"
            "Username 👾 = Sekanulkejixas1918@gmail.com\n"
            "Password 🔑 = FAIiowla6HS72"
        )
        bot.send_message(uid, account_info, reply_markup=task_action_keyboard())

    elif text == "Done ✅":
        clear_state(uid)
        bot.send_message(
            uid,
            "❤️ Sir , Please Wait , We're check-in your report 💌",
            reply_markup=main_menu_keyboard()
        )

    elif text == "Cancel Create Account ❌":
        clear_state(uid)
        bot.send_message(
            uid,
            "Hi Sir , Welcome To My Earn Zone",
            reply_markup=main_menu_keyboard()
        )

    # ── Withdraw Methods ──────────────────────────────────────────────────────
    elif text == "Binance ✅":
        set_state(uid, "awaiting_binance_address")
        bot.send_message(
            uid,
            "Enter your (BEP-20) address.",
            reply_markup=ReplyKeyboardRemove()
        )

    elif text == "bkash ✅":
        set_state(uid, "awaiting_bkash_number")
        bot.send_message(
            uid,
            "Enter your bkash Number 📱",
            reply_markup=ReplyKeyboardRemove()
        )

    # ── Back / Fallback ───────────────────────────────────────────────────────
    elif text in ("Back 🔙", "🔙 Back"):
        clear_state(uid)
        bot.send_message(
            uid,
            "Hi Sir , Welcome To My Earn Zone",
            reply_markup=main_menu_keyboard()
        )

    else:
        # Unknown input — nudge user back to menu
        bot.send_message(
            uid,
            "Please use the menu buttons below.",
            reply_markup=main_menu_keyboard()
        )

# ── Withdrawal Logic ──────────────────────────────────────────────────────────
def _process_withdrawal(uid: int, message, method: str):
    bal = get_balance(uid)
    clear_state(uid)

    if bal < 2.0:
        bot.send_message(
            uid,
            "Minimum withdrawal is 2$.",
            reply_markup=main_menu_keyboard()
        )
    else:
        set_balance(uid, 0.0)
        bot.send_message(
            uid,
            "✅ Your Withdrawal request Submitted.",
            reply_markup=main_menu_keyboard()
        )

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
