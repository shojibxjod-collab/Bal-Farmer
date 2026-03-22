import os
import random
import string
import time
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ── Environment Variables ──────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID  = int(os.environ.get("OWNER_ID"))

bot = telebot.TeleBot(BOT_TOKEN)

# ── Name & Email Generation Data ───────────────────────────────────────────────
FIRST_NAMES = [
    "Alex", "Jordan", "Morgan", "Casey", "Riley", "Taylor", "Drew", "Avery",
    "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Hayden", "Jamie",
    "Kendall", "Logan", "Marlowe", "Nolan", "Oakley", "Parker", "Quinn",
    "Reese", "Skyler", "Tristan", "Uma", "Valentina", "Wesley", "Xander", "Yara"
]

LAST_NAMES = [
    "Hunt", "Cole", "Reed", "Stone", "Banks", "Fox", "Hart", "Lane",
    "Nash", "Park", "Reid", "Shaw", "Voss", "Wade", "York", "Zane",
    "Cross", "Drake", "Flynn", "Grant", "Hayes", "Knox", "Miles", "Pierce",
    "Rhodes", "Scott", "Todd", "Urban", "Vance", "Wells"
]

EMAIL_DOMAINS = [
    "gmail.com",
]

# ── In-Memory Storage ──────────────────────────────────────────────────────────
user_balance        = {}   # { uid: float }
user_state          = {}   # { uid: str }
user_used_accounts  = {}   # { uid: set of usernames }
user_current_task   = {}   # { uid: account dict }
user_profiles       = {}   # { uid: { name, username, join_date, tasks, withdrawals, referrals, referrer } }
user_last_bonus     = {}   # { uid: timestamp }
user_referrals      = {}   # { uid: [referred_uid, ...] }
all_used_usernames  = set() # globally unique emails

DAILY_BONUS_AMOUNT   = 0.10
REFERRAL_BONUS       = 0.20
DAILY_BONUS_INTERVAL = 86400  # 24 hours in seconds

# ── Account Generator ──────────────────────────────────────────────────────────
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*")
    ]
    pwd += random.choices(chars, k=length - 4)
    random.shuffle(pwd)
    return "".join(pwd)

def generate_unique_email(first, last):
    attempts = 0
    while attempts < 50:
        style = random.randint(1, 4)
        num   = random.randint(10, 9999)
        sep   = random.choice([".", "_", ""])
        domain = random.choice(EMAIL_DOMAINS)

        if style == 1:
            local = f"{first.lower()}{sep}{last.lower()}{num}"
        elif style == 2:
            local = f"{first.lower()}{num}"
        elif style == 3:
            local = f"{last.lower()}{sep}{first.lower()[:3]}{num}"
        else:
            local = f"{first.lower()[0]}{last.lower()}{num}"

        email = f"{local}@{domain}"
        if email not in all_used_usernames:
            all_used_usernames.add(email)
            return email
        attempts += 1

    # Fallback with timestamp
    email = f"{first.lower()}{last.lower()}{int(time.time())}@gmail.com"
    all_used_usernames.add(email)
    return email

def generate_account(uid):
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    email = generate_unique_email(first, last)

    used = user_used_accounts.get(uid, set())
    retry = 0
    while email in used and retry < 20:
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        email = generate_unique_email(first, last)
        retry += 1

    return {
        "first_name": first,
        "last_name":  last,
        "username":   email,
        "password":   generate_password()
    }

# ── Profile Helper ─────────────────────────────────────────────────────────────
def ensure_profile(uid, full_name="User", username="N/A"):
    if uid not in user_profiles:
        user_profiles[uid] = {
            "name":        full_name,
            "username":    username,
            "join_date":   time.strftime("%d %b %Y"),
            "tasks":       0,
            "withdrawals": 0,
            "referrals":   0,
            "referrer":    None
        }

def get_profile(uid):
    return user_profiles.get(uid, {})

# ── Balance Helpers ────────────────────────────────────────────────────────────
def get_balance(uid):
    return user_balance.get(uid, 0.00)

def set_balance(uid, amount):
    user_balance[uid] = round(amount, 2)

def add_balance(uid, amount):
    set_balance(uid, get_balance(uid) + amount)

# ── State Helpers ──────────────────────────────────────────────────────────────
def set_state(uid, state):
    user_state[uid] = state

def get_state(uid):
    return user_state.get(uid, "")

def clear_state(uid):
    user_state.pop(uid, None)

# ── Daily Bonus Helper ─────────────────────────────────────────────────────────
def can_claim_bonus(uid):
    last = user_last_bonus.get(uid, 0)
    return (time.time() - last) >= DAILY_BONUS_INTERVAL

def time_until_next_bonus(uid):
    last    = user_last_bonus.get(uid, 0)
    elapsed = time.time() - last
    remaining = DAILY_BONUS_INTERVAL - elapsed
    if remaining <= 0:
        return "Available now!"
    hours   = int(remaining // 3600)
    minutes = int((remaining % 3600) // 60)
    return f"{hours}h {minutes}m"

# ── Keyboards ──────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("1️⃣ Tasks"),      KeyboardButton("2️⃣ Wallet"))
    kb.row(KeyboardButton("3️⃣ Withdraw"),   KeyboardButton("4️⃣ Referral"))
    kb.row(KeyboardButton("🎁 Daily Bonus"), KeyboardButton("👤 Profile"))
    return kb

def tasks_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📧 Create Account - Earn 0.35$"))
    kb.row(KeyboardButton("🔙 Back"))
    return kb

def task_action_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("Done ✅"))
    kb.row(KeyboardButton("Cancel Create Account ❌"))
    return kb

def back_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🔙 Back"))
    return kb

def withdraw_method_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("Binance ✅"), KeyboardButton("bkash ✅"))
    kb.row(KeyboardButton("🔙 Back"))
    return kb

# ── Welcome Message ────────────────────────────────────────────────────────────
def send_main_menu(uid, custom_text=None):
    text = custom_text or (
        "💎 *Earn Zone*\n"
        "━━━━━━━━━━━━━━━\n"
        "Welcome Sir! 👋\n\n"
        "Select an option below 👇"
    )
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

# ── /start ─────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid       = message.from_user.id
    full_name = message.from_user.full_name
    username  = message.from_user.username or "N/A"

    clear_state(uid)
    user_current_task.pop(uid, None)
    ensure_profile(uid, full_name, username)

    # ── Referral handling ──────────────────────────────────────────────────────
    parts = message.text.split()
    if len(parts) > 1:
        try:
            referrer_uid = int(parts[1])
            profile      = get_profile(uid)

            if (referrer_uid != uid
                    and profile.get("referrer") is None
                    and referrer_uid in user_profiles):

                # Credit referrer
                add_balance(referrer_uid, REFERRAL_BONUS)
                user_profiles[referrer_uid]["referrals"] += 1
                if referrer_uid not in user_referrals:
                    user_referrals[referrer_uid] = []
                user_referrals[referrer_uid].append(uid)

                # Mark new user's referrer
                user_profiles[uid]["referrer"] = referrer_uid

                # Notify referrer
                try:
                    bot.send_message(
                        referrer_uid,
                        f"🎉 *New Referral!*\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"👤 {full_name} joined using your link!\n"
                        f"💰 You earned *+{REFERRAL_BONUS:.2f}$*\n"
                        f"💎 New Balance: *{get_balance(referrer_uid):.2f}$*",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        except (ValueError, KeyError):
            pass

    # ── Notify owner ───────────────────────────────────────────────────────────
    try:
        bot.send_message(
            OWNER_ID,
            f"👤 *New User Started Bot!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"• Name: {full_name}\n"
            f"• Username: @{username}\n"
            f"• User ID: `{uid}`",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    send_main_menu(uid)

# ── /profile ───────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["profile"])
def cmd_profile(message):
    uid = message.from_user.id
    ensure_profile(uid, message.from_user.full_name)
    _show_profile(uid)

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

    add_balance(target_uid, amount)
    new_bal = get_balance(target_uid)

    bot.send_message(
        message.chat.id,
        f"✅ Added *{amount:.2f}$* to user `{target_uid}`.\n"
        f"💰 New Balance: *{new_bal:.2f}$*",
        parse_mode="Markdown"
    )

    try:
        bot.send_message(
            target_uid,
            f"🎉 *Balance Updated!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Added: *+{amount:.2f}$*\n"
            f"💎 New Balance: *{new_bal:.2f}$*",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ── Profile Display Helper ─────────────────────────────────────────────────────
def _show_profile(uid):
    profile = get_profile(uid)
    bal     = get_balance(uid)
    bonus_status = "✅ Available" if can_claim_bonus(uid) else f"⏳ {time_until_next_bonus(uid)}"

    text = (
        f"👤 *Your Profile*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 User ID: `{uid}`\n"
        f"📛 Name: {profile.get('name', 'N/A')}\n"
        f"📅 Joined: {profile.get('join_date', 'N/A')}\n\n"
        f"💰 Balance: *{bal:.2f}$*\n"
        f"✅ Tasks Done: *{profile.get('tasks', 0)}*\n"
        f"💸 Total Withdrawn: *{profile.get('withdrawals', 0)}*\n"
        f"👥 Referrals: *{profile.get('referrals', 0)}*\n\n"
        f"🎁 Daily Bonus: {bonus_status}"
    )
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=back_keyboard())

# ── Main Text Handler ──────────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    uid   = message.from_user.id
    text  = message.text.strip()
    state = get_state(uid)

    ensure_profile(uid, message.from_user.full_name,
                   message.from_user.username or "N/A")

    # ── Awaiting withdrawal input ──────────────────────────────────────────────
    if state == "awaiting_binance_address":
        _process_withdrawal(uid, message, method="Binance")
        return

    if state == "awaiting_bkash_number":
        _process_withdrawal(uid, message, method="bkash")
        return

    # ── Main Menu ──────────────────────────────────────────────────────────────
    if text == "1️⃣ Tasks":
        clear_state(uid)
        user_current_task.pop(uid, None)
        bot.send_message(
            uid,
            "📋 *Tasks Menu*\n"
            "━━━━━━━━━━━━━━━\n"
            "Complete tasks to earn money! 💰",
            parse_mode="Markdown",
            reply_markup=tasks_keyboard()
        )

    elif text == "2️⃣ Wallet":
        clear_state(uid)
        bal = get_balance(uid)
        bot.send_message(
            uid,
            f"💰 *Your Wallet*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💎 Balance: *{bal:.2f}$*\n\n"
            f"Minimum withdrawal: *2.00$*",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    elif text == "3️⃣ Withdraw":
        clear_state(uid)
        bot.send_message(
            uid,
            "💸 *Withdraw*\n"
            "━━━━━━━━━━━━━━━\n"
            "Choose your withdrawal method 👇",
            parse_mode="Markdown",
            reply_markup=withdraw_method_keyboard()
        )

    elif text == "4️⃣ Referral":
        clear_state(uid)
        bot_info  = bot.get_me()
        ref_link  = f"[t.me](https://t.me/{bot_info.username}?start={uid})"
        ref_count = get_profile(uid).get("referrals", 0)
        bot.send_message(
            uid,
            f"👥 *Referral System*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Invite friends & earn *{REFERRAL_BONUS:.2f}$* per referral!\n\n"
            f"🔗 *Your Referral Link:*\n"
            f"`{ref_link}`\n\n"
            f"👤 Total Referrals: *{ref_count}*\n"
            f"💰 Total Earned: *{ref_count * REFERRAL_BONUS:.2f}$*\n\n"
            f"📤 Share your link and start earning!",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    elif text == "🎁 Daily Bonus":
        clear_state(uid)
        if can_claim_bonus(uid):
            add_balance(uid, DAILY_BONUS_AMOUNT)
            user_last_bonus[uid] = time.time()
            bot.send_message(
                uid,
                f"🎁 *Daily Bonus Claimed!*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 You received: *+{DAILY_BONUS_AMOUNT:.2f}$*\n"
                f"💎 New Balance: *{get_balance(uid):.2f}$*\n\n"
                f"⏳ Come back tomorrow for more!",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        else:
            remaining = time_until_next_bonus(uid)
            bot.send_message(
                uid,
                f"⏳ *Daily Bonus Not Ready*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"You already claimed today's bonus.\n\n"
                f"🕐 Next bonus in: *{remaining}*",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

    elif text == "👤 Profile":
        clear_state(uid)
        _show_profile(uid)

    # ── Task Flow ──────────────────────────────────────────────────────────────
    elif text == "📧 Create Account - Earn 0.35$":
        clear_state(uid)
        account = generate_account(uid)
        used    = user_used_accounts.get(uid, set())

        # Safety check — try a few times to get unused
        attempts = 0
        while account["username"] in used and attempts < 10:
            account  = generate_account(uid)
            attempts += 1

        user_current_task[uid] = account

        account_info = (
            f"📧 *New Account Task*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"First Name 📛 = `{account['first_name']}`\n"
            f"Last Name = 🚫\n"
            f"Username 👾 = `{account['username']}`\n"
            f"Password 🔑 = `{account['password']}`\n\n"
            f"✅ Complete the task and click *Done*\n"
            f"💰 Reward: *0.35$*"
        )
        bot.send_message(
            uid,
            account_info,
            parse_mode="Markdown",
            reply_markup=task_action_keyboard()
        )

    elif text == "Done ✅":
        account = user_current_task.get(uid)
        if account:
            if uid not in user_used_accounts:
                user_used_accounts[uid] = set()
            user_used_accounts[uid].add(account["username"])
            user_current_task.pop(uid, None)
            user_profiles[uid]["tasks"] += 1

        clear_state(uid)
        bot.send_message(
            uid,
            "❤️ *Task Submitted!*\n"
            "━━━━━━━━━━━━━━━\n"
            "Sir, Please Wait...\n"
            "We're checking your report 💌\n\n"
            "Balance will be added after verification ✅",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

    elif text == "Cancel Create Account ❌":
        user_current_task.pop(uid, None)
        clear_state(uid)
        send_main_menu(uid)

    # ── Withdraw Methods ───────────────────────────────────────────────────────
    elif text == "Binance ✅":
        set_state(uid, "awaiting_binance_address")
        bot.send_message(
            uid,
            "🔐 *Binance Withdrawal*\n"
            "━━━━━━━━━━━━━━━\n"
            "Enter your *(BEP-20)* wallet address 👇",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

    elif text == "bkash ✅":
        set_state(uid, "awaiting_bkash_number")
        bot.send_message(
            uid,
            "📱 *bkash Withdrawal*\n"
            "━━━━━━━━━━━━━━━\n"
            "Enter your *bkash Number* 👇",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

    # ── Back ───────────────────────────────────────────────────────────────────
    elif text in ("🔙 Back", "Back 🔙"):
        clear_state(uid)
        user_current_task.pop(uid, None)
        send_main_menu(uid)

    else:
        bot.send_message(
            uid,
            "⚠️ Please use the menu buttons below.",
            reply_markup=main_menu_keyboard()
        )

# ── Withdrawal Logic ───────────────────────────────────────────────────────────
def _process_withdrawal(uid, message, method):
    bal = get_balance(uid)
    clear_state(uid)

    if bal < 2.0:
        bot.send_message(
            uid,
            f"❌ *Minimum withdrawal is 2.00$*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Your Balance: *{bal:.2f}$*\n"
            f"📉 You need: *{(2.0 - bal):.2f}$* more",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return

    set_balance(uid, 0.0)
    user_profiles[uid]["withdrawals"] += 1

    bot.send_message(
        uid,
        f"✅ *Withdrawal Submitted!*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💸 Amount: *{bal:.2f}$*\n"
        f"🏦 Method: *{method}*\n"
        f"📬 Address: `{message.text.strip()}`\n\n"
        f"⏳ Processing time: 24-48 hours",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

    try:
        bot.send_message(
            OWNER_ID,
            f"💸 *Withdrawal Request!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Name: {message.from_user.full_name}\n"
            f"🆔 User ID: `{uid}`\n"
            f"🏦 Method: *{method}*\n"
            f"📬 Address: `{message.text.strip()}`\n"
            f"💰 Amount: *{bal:.2f}$*",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("💎 Earn Zone Bot is running...")
    bot.infinity_polling()
