import os
import random
import string
import time
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ── Environment Variables ──────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID  = int(os.environ.get("OWNER_ID", "0"))

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

EMAIL_DOMAINS = ["gmail.com"]

# ── In-Memory Storage ──────────────────────────────────────────────────────────
user_balance        = {}   # { uid: float }
user_state          = {}   # { uid: str }
user_used_accounts  = {}   # { uid: set of emails }
user_current_task   = {}   # { uid: account dict }
user_profiles       = {}   # { uid: { name, username, join_date, tasks, withdrawals, referrals, referrer } }
user_last_bonus     = {}   # { uid: timestamp }
user_referrals      = {}   # { uid: [referred_uid, ...] }
all_used_usernames  = set()
banned_users        = set()

# ── Pending Task Storage ───────────────────────────────────────────────────────
# { uid: { "account": {...}, "submitted_at": timestamp } }
pending_tasks = {}

TASK_REWARD          = 0.25
DAILY_BONUS_AMOUNT   = 0.15
REFERRAL_BONUS       = 0.10
DAILY_BONUS_INTERVAL = 86400
MIN_WITHDRAWAL       = 3.00

# ══════════════════════════════════════════════════════════════════════════════
# ACCOUNT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

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
    for _ in range(50):
        style  = random.randint(1, 4)
        num    = random.randint(10, 9999)
        sep    = random.choice([".", "_", "-"])
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

    # Fallback
    email = f"{first.lower()}{last.lower()}{int(time.time())}@gmail.com"
    all_used_usernames.add(email)
    return email

def generate_account(uid):
    used = user_used_accounts.get(uid, set())
    for _ in range(20):
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        email = generate_unique_email(first, last)
        if email not in used:
            return {
                "first_name": first,
                "last_name":  last,
                "username":   email,
                "password":   generate_password()
            }
    # Last resort
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    return {
        "first_name": first,
        "last_name":  last,
        "username":   generate_unique_email(first, last),
        "password":   generate_password()
    }

# ══════════════════════════════════════════════════════════════════════════════
# PROFILE & BALANCE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

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

def get_balance(uid):
    return user_balance.get(uid, 0.00)

def set_balance(uid, amount):
    user_balance[uid] = round(max(0.0, amount), 2)

def add_balance(uid, amount):
    set_balance(uid, get_balance(uid) + amount)

def deduct_balance(uid, amount):
    """Deduct safely — never goes below 0."""
    current = get_balance(uid)
    set_balance(uid, max(0.0, current - amount))

def set_state(uid, state):
    user_state[uid] = state

def get_state(uid):
    return user_state.get(uid, "")

def clear_state(uid):
    user_state.pop(uid, None)

# ── Daily Bonus ────────────────────────────────────────────────────────────────

def can_claim_bonus(uid):
    last = user_last_bonus.get(uid, 0)
    return (time.time() - last) >= DAILY_BONUS_INTERVAL

def time_until_next_bonus(uid):
    last      = user_last_bonus.get(uid, 0)
    remaining = DAILY_BONUS_INTERVAL - (time.time() - last)
    if remaining <= 0:
        return "Available now!"
    hours   = int(remaining // 3600)
    minutes = int((remaining % 3600) // 60)
    return f"{hours}h {minutes}m"

# ── Owner check ────────────────────────────────────────────────────────────────

def is_owner(uid):
    return uid == OWNER_ID

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📋 Tasks"),       KeyboardButton("💰 Wallet"))
    kb.row(KeyboardButton("💸 Withdraw"),    KeyboardButton("🫂 Referral"))
    kb.row(KeyboardButton("🎁 Daily Bonus"), KeyboardButton("👤 Profile"))
    return kb

def tasks_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📧 Create Account - Earn 0.25$"))
    kb.row(KeyboardButton("🔙 Back"))
    return kb

def task_action_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Done"))
    kb.row(KeyboardButton("❌ Cancel Task"))
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

# ══════════════════════════════════════════════════════════════════════════════
# SEND MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

def send_main_menu(uid, custom_text=None):
    text = custom_text or (
        "💎 *Earn Farmer*\n"
        "━━━━━━━━━━━━━━━\n"
        "Welcome! 👋\n\n"
        "Select an option below 👇"
    )
    try:
        bot.send_message(uid, text, parse_mode="Markdown",
                         reply_markup=main_menu_keyboard())
    except Exception as e:
        print(f"[send_main_menu] Error for uid {uid}: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid       = message.from_user.id
    full_name = message.from_user.full_name or "User"
    username  = message.from_user.username or "N/A"

    if uid in banned_users:
        try:
            bot.send_message(uid, "⛔ You have been banned from using this bot.")
        except Exception:
            pass
        return

    clear_state(uid)
    user_current_task.pop(uid, None)
    ensure_profile(uid, full_name, username)

    # Referral handling
    parts = message.text.split()
    if len(parts) > 1:
        try:
            referrer_uid = int(parts[1])
            profile      = get_profile(uid)

            if (referrer_uid != uid
                    and profile.get("referrer") is None
                    and referrer_uid in user_profiles):

                add_balance(referrer_uid, REFERRAL_BONUS)
                user_profiles[referrer_uid]["referrals"] = \
                    user_profiles[referrer_uid].get("referrals", 0) + 1

                user_referrals.setdefault(referrer_uid, []).append(uid)
                user_profiles[uid]["referrer"] = referrer_uid

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

    # Notify owner
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

# ══════════════════════════════════════════════════════════════════════════════
# OWNER ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

def _owner_only(message):
    """Returns True and sends error if not owner."""
    if not is_owner(message.from_user.id):
        try:
            bot.send_message(message.chat.id, "⛔ You are not authorized.")
        except Exception:
            pass
        return False
    return True

def _parse_uid_amount(parts, message, require_amount=True):
    """
    Parse and validate USER_ID [AMOUNT] from command parts.
    Returns (uid, amount) or (uid, None) or (None, None) on error.
    """
    try:
        target_uid = int(parts[1])
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "❌ Invalid USER_ID.")
        return None, None

    amount = None
    if require_amount:
        try:
            amount = float(parts[2])
            if amount < 0:
                raise ValueError
        except (IndexError, ValueError):
            bot.send_message(message.chat.id, "❌ Invalid AMOUNT. Must be a positive number.")
            return None, None

    return target_uid, amount

# ── /check USER_ID ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["check"])
def cmd_check(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, _ = _parse_uid_amount(parts, message, require_amount=False)
    if target_uid is None:
        return

    profile = user_profiles.get(target_uid)
    if not profile:
        bot.send_message(message.chat.id,
                         f"❌ User `{target_uid}` not found.", parse_mode="Markdown")
        return

    bal         = get_balance(target_uid)
    has_pending = target_uid in pending_tasks
    is_banned   = target_uid in banned_users

    bot.send_message(
        message.chat.id,
        f"👤 *User Info*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 User ID: `{target_uid}`\n"
        f"📛 Name: {profile.get('name', 'N/A')}\n"
        f"💰 Balance: *{bal:.2f}$*\n"
        f"✅ Tasks Done: *{profile.get('tasks', 0)}*\n"
        f"💸 Withdrawals: *{profile.get('withdrawals', 0)}*\n"
        f"👥 Referrals: *{profile.get('referrals', 0)}*\n"
        f"⏳ Pending Task: *{'Yes' if has_pending else 'No'}*\n"
        f"⛔ Banned: *{'Yes' if is_banned else 'No'}*",
        parse_mode="Markdown"
    )

# ── /add USER_ID AMOUNT ────────────────────────────────────────────────────────
@bot.message_handler(commands=["add", "addbalance"])
def cmd_add_balance(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, amount = _parse_uid_amount(parts, message)
    if target_uid is None:
        return

    ensure_profile(target_uid)
    add_balance(target_uid, amount)
    new_bal = get_balance(target_uid)

    bot.send_message(
        message.chat.id,
        f"✅ Added *{amount:.2f}$* to `{target_uid}`.\n"
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

# ── /remove USER_ID AMOUNT ─────────────────────────────────────────────────────
@bot.message_handler(commands=["remove"])
def cmd_remove_balance(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, amount = _parse_uid_amount(parts, message)
    if target_uid is None:
        return

    if target_uid not in user_profiles:
        bot.send_message(message.chat.id,
                         f"❌ User `{target_uid}` not found.", parse_mode="Markdown")
        return

    old_bal = get_balance(target_uid)
    deduct_balance(target_uid, amount)
    new_bal = get_balance(target_uid)

    bot.send_message(
        message.chat.id,
        f"✅ Removed *{amount:.2f}$* from `{target_uid}`.\n"
        f"💰 Old: *{old_bal:.2f}$* → New: *{new_bal:.2f}$*",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            target_uid,
            f"⚠️ *Balance Updated*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💸 Deducted: *-{amount:.2f}$*\n"
            f"💎 New Balance: *{new_bal:.2f}$*",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ── /set USER_ID AMOUNT ────────────────────────────────────────────────────────
@bot.message_handler(commands=["set"])
def cmd_set_balance(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, amount = _parse_uid_amount(parts, message)
    if target_uid is None:
        return

    if target_uid not in user_profiles:
        bot.send_message(message.chat.id,
                         f"❌ User `{target_uid}` not found.", parse_mode="Markdown")
        return

    set_balance(target_uid, amount)

    bot.send_message(
        message.chat.id,
        f"✅ Balance set to *{amount:.2f}$* for `{target_uid}`.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            target_uid,
            f"💎 *Balance Updated*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Your balance was set to *{amount:.2f}$*.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ── /ban USER_ID ───────────────────────────────────────────────────────────────
@bot.message_handler(commands=["ban"])
def cmd_ban(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, _ = _parse_uid_amount(parts, message, require_amount=False)
    if target_uid is None:
        return

    if target_uid == OWNER_ID:
        bot.send_message(message.chat.id, "❌ You cannot ban yourself.")
        return

    if target_uid in banned_users:
        bot.send_message(
            message.chat.id,
            f"⚠️ User `{target_uid}` is already banned.",
            parse_mode="Markdown"
        )
        return

    banned_users.add(target_uid)

    profile = user_profiles.get(target_uid)
    name    = profile.get("name", "N/A") if profile else "N/A"

    bot.send_message(
        message.chat.id,
        f"⛔ *User Banned*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 User ID: `{target_uid}`\n"
        f"📛 Name: {name}\n"
        f"✅ Successfully banned.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            target_uid,
            "⛔ You have been banned from the bot."
        )
    except Exception:
        pass

# ── /unban USER_ID ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["unban"])
def cmd_unban(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, _ = _parse_uid_amount(parts, message, require_amount=False)
    if target_uid is None:
        return

    if target_uid not in banned_users:
        bot.send_message(
            message.chat.id,
            f"⚠️ User `{target_uid}` is not banned.",
            parse_mode="Markdown"
        )
        return

    banned_users.discard(target_uid)

    profile = user_profiles.get(target_uid)
    name    = profile.get("name", "N/A") if profile else "N/A"

    bot.send_message(
        message.chat.id,
        f"✅ *User Unbanned*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 User ID: `{target_uid}`\n"
        f"📛 Name: {name}\n"
        f"✅ Successfully unbanned.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            target_uid,
            "✅ You have been unbanned. You can use the bot again."
        )
    except Exception:
        pass

# ── /pending ───────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["pending"])
def cmd_pending(message):
    if not _owner_only(message):
        return

    if not pending_tasks:
        bot.send_message(message.chat.id, "✅ No pending tasks right now.")
        return

    lines = ["📋 *Pending Tasks*\n━━━━━━━━━━━━━━━"]
    for i, (uid, task_data) in enumerate(pending_tasks.items(), 1):
        profile  = user_profiles.get(uid, {})
        account  = task_data.get("account", {})
        sub_time = time.strftime("%d %b %Y %H:%M",
                                 time.localtime(task_data.get("submitted_at", 0)))
        lines.append(
            f"\n*{i}.* 👤 {profile.get('name', 'N/A')} (`{uid}`)\n"
            f"   📧 {account.get('username', 'N/A')}\n"
            f"   🕐 {sub_time}\n"
            f"   ✅ `/approve {uid}`  ❌ `/reject {uid}`"
        )

    full_text = "\n".join(lines)
    if len(full_text) <= 4096:
        bot.send_message(message.chat.id, full_text, parse_mode="Markdown")
    else:
        chunk = lines[0]
        for line in lines[1:]:
            if len(chunk) + len(line) > 4000:
                bot.send_message(message.chat.id, chunk, parse_mode="Markdown")
                chunk = line
            else:
                chunk += "\n" + line
        if chunk:
            bot.send_message(message.chat.id, chunk, parse_mode="Markdown")

# ── /approve USER_ID ───────────────────────────────────────────────────────────
@bot.message_handler(commands=["approve"])
def cmd_approve(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, _ = _parse_uid_amount(parts, message, require_amount=False)
    if target_uid is None:
        return

    if target_uid not in pending_tasks:
        bot.send_message(message.chat.id,
                         f"❌ No pending task found for `{target_uid}`.",
                         parse_mode="Markdown")
        return

    task_data = pending_tasks.pop(target_uid)
    account   = task_data.get("account", {})

    user_used_accounts.setdefault(target_uid, set()).add(
        account.get("username", "")
    )

    add_balance(target_uid, TASK_REWARD)
    if target_uid in user_profiles:
        user_profiles[target_uid]["tasks"] = \
            user_profiles[target_uid].get("tasks", 0) + 1

    bot.send_message(
        message.chat.id,
        f"✅ Task approved for `{target_uid}`.\n"
        f"💰 Credited *{TASK_REWARD:.2f}$*.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            target_uid,
            f"✅ *Task Approved!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 *+{TASK_REWARD:.2f}$* has been added to your balance!\n"
            f"💎 New Balance: *{get_balance(target_uid):.2f}$*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception:
        pass

# ── /reject USER_ID ────────────────────────────────────────────────────────────
@bot.message_handler(commands=["reject"])
def cmd_reject(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    target_uid, _ = _parse_uid_amount(parts, message, require_amount=False)
    if target_uid is None:
        return

    if target_uid not in pending_tasks:
        bot.send_message(message.chat.id,
                         f"❌ No pending task found for `{target_uid}`.",
                         parse_mode="Markdown")
        return

    pending_tasks.pop(target_uid)

    bot.send_message(
        message.chat.id,
        f"❌ Task rejected for `{target_uid}`.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            target_uid,
            f"❌ *Task Rejected*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Your submission was not approved.\n"
            f"Please try again carefully. 🙏",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# PROFILE DISPLAY
# ══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["profile"])
def cmd_profile(message):
    uid = message.from_user.id
    ensure_profile(uid, message.from_user.full_name or "User")
    _show_profile(uid)

def _show_profile(uid):
    profile      = get_profile(uid)
    bal          = get_balance(uid)
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
    try:
        bot.send_message(uid, text, parse_mode="Markdown",
                         reply_markup=back_keyboard())
    except Exception as e:
        print(f"[_show_profile] Error for uid {uid}: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN TEXT HANDLER
# ══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    uid   = message.from_user.id
    text  = message.text.strip()
    state = get_state(uid)

    if uid in banned_users:
        try:
            bot.send_message(uid, "⛔ You have been banned from using this bot.")
        except Exception:
            pass
        return

    ensure_profile(uid,
                   message.from_user.full_name or "User",
                   message.from_user.username or "N/A")

    try:
        # ── Withdrawal input states ────────────────────────────────────────────
        if state == "awaiting_binance_address":
            _process_withdrawal(uid, message, method="Binance")
            return

        if state == "awaiting_bkash_number":
            _process_withdrawal(uid, message, method="bkash")
            return

        # ── Tasks Menu ─────────────────────────────────────────────────────────
        if text == "📋 Tasks":
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

        # ── Wallet ─────────────────────────────────────────────────────────────
        elif text == "💰 Wallet":
            clear_state(uid)
            bal = get_balance(uid)
            bot.send_message(
                uid,
                f"💰 *Your Wallet*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💎 Balance: *{bal:.2f}$*\n\n"
                f"Minimum withdrawal: *{MIN_WITHDRAWAL:.2f}$*",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )

        # ── Withdraw ───────────────────────────────────────────────────────────
        elif text == "💸 Withdraw":
            clear_state(uid)
            bot.send_message(
                uid,
                "💸 *Withdraw*\n"
                "━━━━━━━━━━━━━━━\n"
                "Choose your withdrawal method 👇",
                parse_mode="Markdown",
                reply_markup=withdraw_method_keyboard()
            )

        # ── Referral ───────────────────────────────────────────────────────────
        elif text == "🫂 Referral":
            clear_state(uid)
            try:
                bot_info  = bot.get_me()
                ref_link  = f"[t.me](https://t.me/{bot_info.username}?start={uid})"
            except Exception:
                ref_link = "Unable to generate link"

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

        # ── Daily Bonus ────────────────────────────────────────────────────────
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
                bot.send_message(
                    uid,
                    f"⏳ *Daily Bonus Not Ready*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"You already claimed today's bonus.\n\n"
                    f"🕐 Next bonus in: *{time_until_next_bonus(uid)}*",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )

        # ── Profile ────────────────────────────────────────────────────────────
        elif text == "👤 Profile":
            clear_state(uid)
            _show_profile(uid)

        # ── Start Task ─────────────────────────────────────────────────────────
        elif text == "📧 Create Account - Earn 0.30$":
            clear_state(uid)

            if uid in pending_tasks:
                bot.send_message(
                    uid,
                    "⏳ *You already have a pending task.*\n"
                    "━━━━━━━━━━━━━━━\n"
                    "Please wait for it to be approved or rejected before starting a new one.",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
                return

            account = generate_account(uid)
            user_current_task[uid] = account

            bot.send_message(
                uid,
                f"📧 *New Account Task*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"First Name 📛 = `{account['first_name']}`\n"
                f"Last Name = 🚫\n"
                f"Username 👾 = `{account['username']}`\n"
                f"Password 🔑 = `{account['password']}`\n\n"
                f"✅ Complete the task and click *Done*\n"
                f"💰 Reward: *{TASK_REWARD:.2f}$*",
                parse_mode="Markdown",
                reply_markup=task_action_keyboard()
            )

        # ── Done ───────────────────────────────────────────────────────────────
        elif text == "✅ Done":
            account = user_current_task.get(uid)

            if not account:
                bot.send_message(
                    uid,
                    "⚠️ No active task found. Please start a new task first.",
                    reply_markup=main_menu_keyboard()
                )
                return

            if uid in pending_tasks:
                bot.send_message(
                    uid,
                    "⏳ Your previous task is still under review.",
                    reply_markup=main_menu_keyboard()
                )
                return

            pending_tasks[uid] = {
                "account":      account,
                "submitted_at": time.time()
            }
            user_current_task.pop(uid, None)
            clear_state(uid)

            bot.send_message(
                uid,
                "📨 *Task Submitted!*\n"
                "━━━━━━━━━━━━━━━\n"
                "Your task is under review. ✅\n\n"
                "💰 Balance will be added after verification.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

            profile = get_profile(uid)
            try:
                bot.send_message(
                    OWNER_ID,
                    f"📋 *New Task Submission*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"👤 {profile.get('name', 'N/A')} (`{uid}`)\n"
                    f"📧 {account.get('username', 'N/A')}\n\n"
                    f"✅ `/approve {uid}`\n"
                    f"❌ `/reject {uid}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # ── Cancel Task ────────────────────────────────────────────────────────
        elif text == "❌ Cancel Task":
            user_current_task.pop(uid, None)
            clear_state(uid)
            send_main_menu(uid)

        # ── Withdraw Methods ───────────────────────────────────────────────────
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

        # ── Back ───────────────────────────────────────────────────────────────
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

    except Exception as e:
        print(f"[handle_text] Unhandled error for uid {uid}: {e}")
        try:
            bot.send_message(uid,
                             "⚠️ Something went wrong. Please try again.",
                             reply_markup=main_menu_keyboard())
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# WITHDRAWAL LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def _process_withdrawal(uid, message, method):
    bal = get_balance(uid)
    clear_state(uid)

    if bal < MIN_WITHDRAWAL:
        try:
            bot.send_message(
                uid,
                f"❌ *Minimum withdrawal is {MIN_WITHDRAWAL:.2f}$*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 Your Balance: *{bal:.2f}$*\n"
                f"📉 You need: *{(MIN_WITHDRAWAL - bal):.2f}$* more",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        except Exception:
            pass
        return

    address = message.text.strip()
    set_balance(uid, 0.0)
    if uid in user_profiles:
        user_profiles[uid]["withdrawals"] = \
            user_profiles[uid].get("withdrawals", 0) + 1

    try:
        bot.send_message(
            uid,
            f"✅ *Withdrawal Submitted!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💸 Amount: *{bal:.2f}$*\n"
            f"🏦 Method: *{method}*\n"
            f"📬 Address: `{address}`\n\n"
            f"⏳ Processing time: 24-48 hours",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        print(f"[_process_withdrawal] Error notifying user {uid}: {e}")

    try:
        bot.send_message(
            OWNER_ID,
            f"💸 *Withdrawal Request!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Name: {message.from_user.full_name}\n"
            f"🆔 User ID: `{uid}`\n"
            f"🏦 Method: *{method}*\n"
            f"📬 Address: `{address}`\n"
            f"💰 Amount: *{bal:.2f}$*",
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("💎 Earn Farmer Bot is running...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
