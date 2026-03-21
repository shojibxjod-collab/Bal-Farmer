import os
import random
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ── Environment Variables ──────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID  = int(os.environ.get("OWNER_ID"))

bot = telebot.TeleBot(BOT_TOKEN)

# ── Account Pool ───────────────────────────────────────────────────────────────
ACCOUNT_POOL = [
    {
        "first_name": "Deogrej",
        "last_name": "🚫",
        "username": "Sekanulkejixas1918@gmail.com",
        "password": "FAIiowla6HS72"
    },
    {
        "first_name": "Marlvin",
        "last_name": "🚫",
        "username": "Trowbeckgdpb921@gmail.com",
        "password": "Xp92#mLqR7"
    },
    {
        "first_name": "Jobrina",
        "last_name": "🚫",
        "username": "jobryinamvweltz044@gmail.com",
        "password": "Bv83!qZnT1"
    },
    {
        "first_name": "Huxley",
        "last_name": "🚫",
        "username": "huxleykirafton@gmail.com",
        "password": "Kd71@wPsN5"
    },
    {
        "first_name": "Catrinel",
        "last_name": "🚫",
        "username": "catrinsaelns199@gmail.com",
        "password": "Zm64#rJkW9"
    },
    {
        "first_name": "Brennick",
        "last_name": "🚫",
        "username": "brreemnnickbnox82@gmail.com",
        "password": "Yw38!dHmQ2"
    },
    {
        "first_name": "Sylvara",
        "last_name": "🚫",
        "username": "sylvarjko6ight77@gmail.com",
        "password": "Tc55@vBnL6"
    },
    {
        "first_name": "Ondrej",
        "last_name": "🚫",
        "username": "ondrej0pkalmar33@gmail.com",
        "password": "Nq47#eSxK3"
    },
    {
        "first_name": "Fiorentina",
        "last_name": "🚫",
        "username": "fiorenntinahvirx@gmail.com",
        "password": "Gp19!uYcM8"
    },
    {
        "first_name": "Zephran",
        "last_name": "🚫",
        "username": "zephranbkoldwell@gmail.com",
        "password": "Rj62@oTlV4"
    },
    {
        "first_name": "Lyndorel",
        "last_name": "🚫",
        "username": "lyndorelhjo0anks55@gmail.com",
        "password": "Wh93#iKpU7"
    },
]

# ── In-Memory Storage ──────────────────────────────────────────────────────────
user_balance      = {}   # { user_id: float }
user_state        = {}   # { user_id: str }
user_used_accounts = {}  # { user_id: set of username strings }
user_current_task = {}   # { user_id: account dict } — account shown for current task

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

def get_available_account(uid: int):
    """Return a random unused account for this user, or None if all used."""
    used = user_used_accounts.get(uid, set())
    available = [acc for acc in ACCOUNT_POOL if acc["username"] not in used]
    if not available:
        return None
    return random.choice(available)

def mark_account_used(uid: int, username: str):
    if uid not in user_used_accounts:
        user_used_accounts[uid] = set()
    user_used_accounts[uid].add(username)

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
    user_current_task.pop(uid, None)

    # Notify owner about new user
    try:
        bot.send_message(
            OWNER_ID,
            f"👤 New User Started Bot!\n"
            f"• Name: {message.from_user.full_name}\n"
            f"• Username: @{message.from_user.username or 'N/A'}\n"
            f"• User ID: {uid}"
        )
    except Exception:
        pass

    bot.send_message(
        uid,
        "Hi Sir , Welcome To My Earn Zone",
        reply_markup=main_menu_keyboard()
    )

# ── /addbalance (owner only) ───────────────────────────────────────────────────
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

    # Notify the user their balance was topped up
    try:
        bot.send_message(
            target_uid,
            f"🎉 Your balance has been updated!\n"
            f"💰 New Balance: {new_balance:.2f}$"
        )
    except Exception:
        pass

# ── Main Text Handler ─────────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    uid   = message.from_user.id
    text  = message.text.strip()
    state = get_state(uid)

    # ── Awaiting withdrawal input ─────────────────────────────────────────────
    if state == "awaiting_binance_address":
        _process_withdrawal(uid, message, method="Binance")
        return

    if state == "awaiting_bkash_number":
        _process_withdrawal(uid, message, method="bkash")
        return

    # ── Main Menu Buttons ─────────────────────────────────────────────────────
    if text == "1️⃣ Tasks":
        clear_state(uid)
        user_current_task.pop(uid, None)
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

    # ── Task Flow ─────────────────────────────────────────────────────────────
    elif text == "Create Account - Earn 0.35$":
        clear_state(uid)
        account = get_available_account(uid)

        if account is None:
            # All accounts exhausted for this user
            bot.send_message(
                uid,
                "⚠️ Email not available.\n\n"
                "You have already used all available accounts. "
                "Please wait for new tasks to be added.",
                reply_markup=tasks_keyboard()
            )
            return

        # Store which account we showed this user for this task session
        user_current_task[uid] = account

        account_info = (
            f"First Name 📛 = {account['first_name']}\n"
            f"Last Name = {account['last_name']}\n"
            f"Username 👾 = {account['username']}\n"
            f"Password 🔑 = {account['password']}"
        )
        bot.send_message(uid, account_info, reply_markup=task_action_keyboard())

    elif text == "Done ✅":
        # Mark the account as used only when user confirms Done
        account = user_current_task.get(uid)
        if account:
            mark_account_used(uid, account["username"])
            user_current_task.pop(uid, None)

        clear_state(uid)
        bot.send_message(
            uid,
            "❤️ Sir , Please Wait , We're check-in your report 💌",
            reply_markup=main_menu_keyboard()
        )

    elif text == "Cancel Create Account ❌":
        # Do NOT mark account as used — user cancelled
        user_current_task.pop(uid, None)
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
        user_current_task.pop(uid, None)
        bot.send_message(
            uid,
            "Hi Sir , Welcome To My Earn Zone",
            reply_markup=main_menu_keyboard()
        )

    else:
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
            "❌ Minimum withdrawal is 2$.",
            reply_markup=main_menu_keyboard()
        )
    else:
        set_balance(uid, 0.0)
        bot.send_message(
            uid,
            "✅ Your Withdrawal request Submitted.",
            reply_markup=main_menu_keyboard()
        )

        # Notify owner about withdrawal request
        try:
            bot.send_message(
                OWNER_ID,
                f"💸 Withdrawal Request!\n"
                f"• Method: {method}\n"
                f"• Address/Number: {message.text.strip()}\n"
                f"• Amount: {bal:.2f}$\n"
                f"• User ID: {uid}\n"
                f"• Name: {message.from_user.full_name}"
            )
        except Exception:
            pass

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
