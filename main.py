import os
import random
import string
import time
import sqlite3
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ── Environment Variables ──────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID  = int(os.environ.get("OWNER_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)

# ── Constants ──────────────────────────────────────────────────────────────────
TASK_REWARD          = 0.25
DAILY_BONUS_AMOUNT   = 0.15
REFERRAL_BONUS       = 0.10
DAILY_BONUS_INTERVAL = 86400
MIN_WITHDRAWAL       = 3.00
DB_PATH              = "bot_data.db"

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

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SETUP
# ══════════════════════════════════════════════════════════════════════════════

def get_conn():
    """Return a thread-safe SQLite connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrency
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    """Create all tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                uid             INTEGER PRIMARY KEY,
                name            TEXT    NOT NULL DEFAULT 'User',
                username        TEXT    NOT NULL DEFAULT 'N/A',
                join_date       TEXT    NOT NULL,
                balance         REAL    NOT NULL DEFAULT 0.0,
                tasks_count     INTEGER NOT NULL DEFAULT 0,
                withdrawals_count INTEGER NOT NULL DEFAULT 0,
                referrals_count INTEGER NOT NULL DEFAULT 0,
                referrer_id     INTEGER
            );

            CREATE TABLE IF NOT EXISTS states (
                uid   INTEGER PRIMARY KEY,
                state TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS pending_tasks (
                task_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                uid          INTEGER NOT NULL,
                first_name   TEXT    NOT NULL,
                last_name    TEXT    NOT NULL,
                email        TEXT    NOT NULL,
                password     TEXT    NOT NULL,
                submitted_at REAL    NOT NULL,
                FOREIGN KEY (uid) REFERENCES users(uid)
            );

            CREATE TABLE IF NOT EXISTS bonus_log (
                uid        INTEGER PRIMARY KEY,
                last_claim REAL    NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS used_emails (
                email TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS current_tasks (
                uid        INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name  TEXT NOT NULL,
                email      TEXT NOT NULL,
                password   TEXT NOT NULL
            );
        """)

init_db()

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

def _email_is_used(email: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM used_emails WHERE email = ?", (email,)
        ).fetchone()
    return row is not None

def _mark_email_used(email: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO used_emails (email) VALUES (?)", (email,)
        )

def generate_unique_email(first: str, last: str) -> str:
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
        if not _email_is_used(email):
            _mark_email_used(email)
            return email

    # Fallback — virtually guaranteed unique
    email = f"{first.lower()}{last.lower()}{int(time.time())}@gmail.com"
    _mark_email_used(email)
    return email

def generate_account(uid: int) -> dict:
    """
    Generate an account whose email hasn't been used by this user before.
    Checks both the global used_emails table and that user's pending/approved history.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT email FROM pending_tasks WHERE uid = ?", (uid,)
        ).fetchall()
    user_emails = {r["email"] for r in rows}

    for _ in range(20):
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        email = generate_unique_email(first, last)
        if email not in user_emails:
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

def ensure_profile(uid: int, full_name: str = "User", username: str = "N/A"):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (uid, name, username, join_date, balance)
            VALUES (?, ?, ?, ?, 0.0)
            ON CONFLICT(uid) DO UPDATE SET
                name     = excluded.name,
                username = excluded.username
            """,
            (uid, full_name, username, time.strftime("%d %b %Y"))
        )

def get_profile(uid: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE uid = ?", (uid,)
        ).fetchone()
    return dict(row) if row else {}

def get_balance(uid: int) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT balance FROM users WHERE uid = ?", (uid,)
        ).fetchone()
    return round(row["balance"], 2) if row else 0.0

def set_balance(uid: int, amount: float):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET balance = ? WHERE uid = ?",
            (round(max(0.0, amount), 2), uid)
        )

def add_balance(uid: int, amount: float):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET balance = ROUND(MAX(0, balance + ?), 2) WHERE uid = ?",
            (amount, uid)
        )

def deduct_balance(uid: int, amount: float):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET balance = ROUND(MAX(0, balance - ?), 2) WHERE uid = ?",
            (amount, uid)
        )

# ── State helpers ──────────────────────────────────────────────────────────────

def set_state(uid: int, state: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO states (uid, state) VALUES (?, ?) "
            "ON CONFLICT(uid) DO UPDATE SET state = excluded.state",
            (uid, state)
        )

def get_state(uid: int) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT state FROM states WHERE uid = ?", (uid,)
        ).fetchone()
    return row["state"] if row else ""

def clear_state(uid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM states WHERE uid = ?", (uid,))

# ── Current (in-progress) task helpers ────────────────────────────────────────

def set_current_task(uid: int, account: dict):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO current_tasks (uid, first_name, last_name, email, password)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                email      = excluded.email,
                password   = excluded.password
            """,
            (uid, account["first_name"], account["last_name"],
             account["username"], account["password"])
        )

def get_current_task(uid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM current_tasks WHERE uid = ?", (uid,)
        ).fetchone()
    if not row:
        return None
    return {
        "first_name": row["first_name"],
        "last_name":  row["last_name"],
        "username":   row["email"],
        "password":   row["password"]
    }

def clear_current_task(uid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM current_tasks WHERE uid = ?", (uid,))

# ── Daily Bonus helpers ────────────────────────────────────────────────────────

def can_claim_bonus(uid: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_claim FROM bonus_log WHERE uid = ?", (uid,)
        ).fetchone()
    last = row["last_claim"] if row else 0
    return (time.time() - last) >= DAILY_BONUS_INTERVAL

def time_until_next_bonus(uid: int) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_claim FROM bonus_log WHERE uid = ?", (uid,)
        ).fetchone()
    last      = row["last_claim"] if row else 0
    remaining = DAILY_BONUS_INTERVAL - (time.time() - last)
    if remaining <= 0:
        return "Available now!"
    hours   = int(remaining // 3600)
    minutes = int((remaining % 3600) // 60)
    return f"{hours}h {minutes}m"

def record_bonus_claim(uid: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO bonus_log (uid, last_claim) VALUES (?, ?) "
            "ON CONFLICT(uid) DO UPDATE SET last_claim = excluded.last_claim",
            (uid, time.time())
        )

# ── Pending task helpers ───────────────────────────────────────────────────────

def add_pending_task(uid: int, account: dict) -> int:
    """Insert a pending task and return its task_id."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO pending_tasks (uid, first_name, last_name, email, password, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uid, account["first_name"], account["last_name"],
             account["username"], account["password"], time.time())
        )
        return cur.lastrowid

def get_pending_tasks_for_user(uid: int) -> list[dict]:
    """Return all pending tasks for a user, oldest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM pending_tasks WHERE uid = ? ORDER BY submitted_at ASC",
            (uid,)
        ).fetchall()
    return [dict(r) for r in rows]

def get_all_pending_tasks() -> list[dict]:
    """Return every pending task across all users, oldest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM pending_tasks ORDER BY submitted_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]

def get_pending_task_by_id(task_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pending_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    return dict(row) if row else None

def delete_pending_task(task_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM pending_tasks WHERE task_id = ?", (task_id,))

def get_oldest_pending_task_for_user(uid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pending_tasks WHERE uid = ? ORDER BY submitted_at ASC LIMIT 1",
            (uid,)
        ).fetchone()
    return dict(row) if row else None

# ── Owner check ────────────────────────────────────────────────────────────────

def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS  (unchanged from original)
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

def send_main_menu(uid: int, custom_text: str = None):
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

    clear_state(uid)
    clear_current_task(uid)
    ensure_profile(uid, full_name, username)

    # Referral handling
    parts = message.text.split()
    if len(parts) > 1:
        try:
            referrer_uid = int(parts[1])
            profile      = get_profile(uid)

            if (referrer_uid != uid
                    and profile.get("referrer_id") is None
                    and get_profile(referrer_uid)):

                add_balance(referrer_uid, REFERRAL_BONUS)
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE users SET referrals_count = referrals_count + 1 WHERE uid = ?",
                        (referrer_uid,)
                    )
                    conn.execute(
                        "UPDATE users SET referrer_id = ? WHERE uid = ?",
                        (referrer_uid, uid)
                    )

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

def _owner_only(message) -> bool:
    if not is_owner(message.from_user.id):
        try:
            bot.send_message(message.chat.id, "⛔ You are not authorized.")
        except Exception:
            pass
        return False
    return True

def _parse_uid_amount(parts, message, require_amount=True):
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
            bot.send_message(message.chat.id,
                             "❌ Invalid AMOUNT. Must be a positive number.")
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

    profile = get_profile(target_uid)
    if not profile:
        bot.send_message(message.chat.id,
                         f"❌ User `{target_uid}` not found.", parse_mode="Markdown")
        return

    pending_count = len(get_pending_tasks_for_user(target_uid))

    bot.send_message(
        message.chat.id,
        f"👤 *User Info*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 User ID: `{target_uid}`\n"
        f"📛 Name: {profile.get('name', 'N/A')}\n"
        f"💰 Balance: *{profile.get('balance', 0):.2f}$*\n"
        f"✅ Tasks Done: *{profile.get('tasks_count', 0)}*\n"
        f"💸 Withdrawals: *{profile.get('withdrawals_count', 0)}*\n"
        f"👥 Referrals: *{profile.get('referrals_count', 0)}*\n"
        f"⏳ Pending Tasks: *{pending_count}*",
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

    if not get_profile(target_uid):
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

    if not get_profile(target_uid):
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

# ── /pending ───────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["pending"])
def cmd_pending(message):
    if not _owner_only(message):
        return

    tasks = get_all_pending_tasks()

    if not tasks:
        bot.send_message(message.chat.id, "✅ No pending tasks right now.")
        return

    lines = ["📋 *Pending Tasks*\n━━━━━━━━━━━━━━━"]
    for i, task in enumerate(tasks, 1):
        uid      = task["uid"]
        profile  = get_profile(uid)
        sub_time = time.strftime("%d %b %Y %H:%M",
                                 time.localtime(task["submitted_at"]))
        lines.append(
            f"\n*{i}.* 👤 {profile.get('name', 'N/A')} (`{uid}`)\n"
            f"   🆔 Task ID: `{task['task_id']}`\n"
            f"   📧 {task['email']}\n"
            f"   🕐 {sub_time}\n"
            f"   ✅ `/approve {task['task_id']}`  "
            f"❌ `/reject {task['task_id']}`"
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

# ── /approve TASK_ID ───────────────────────────────────────────────────────────
@bot.message_handler(commands=["approve"])
def cmd_approve(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    task_id, _ = _parse_uid_amount(parts, message, require_amount=False)
    if task_id is None:
        return

    task = get_pending_task_by_id(task_id)
    if not task:
        bot.send_message(message.chat.id,
                         f"❌ No pending task found with ID `{task_id}`.",
                         parse_mode="Markdown")
        return

    uid = task["uid"]
    delete_pending_task(task_id)

    # Credit reward & update stats
    add_balance(uid, TASK_REWARD)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET tasks_count = tasks_count + 1 WHERE uid = ?", (uid,)
        )

    bot.send_message(
        message.chat.id,
        f"✅ Task `{task_id}` approved for `{uid}`.\n"
        f"💰 Credited *{TASK_REWARD:.2f}$*.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            uid,
            f"✅ *Task Approved!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 *+{TASK_REWARD:.2f}$* has been added to your balance!\n"
            f"💎 New Balance: *{get_balance(uid):.2f}$*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception:
        pass

# ── /reject TASK_ID ────────────────────────────────────────────────────────────
@bot.message_handler(commands=["reject"])
def cmd_reject(message):
    if not _owner_only(message):
        return

    parts = message.text.split()
    task_id, _ = _parse_uid_amount(parts, message, require_amount=False)
    if task_id is None:
        return

    task = get_pending_task_by_id(task_id)
    if not task:
        bot.send_message(message.chat.id,
                         f"❌ No pending task found with ID `{task_id}`.",
                         parse_mode="Markdown")
        return

    uid = task["uid"]
    delete_pending_task(task_id)

    bot.send_message(
        message.chat.id,
        f"❌ Task `{task_id}` rejected for `{uid}`.",
        parse_mode="Markdown"
    )
    try:
        bot.send_message(
            uid,
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

def _show_profile(uid: int):
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
        f"✅ Tasks Done: *{profile.get('tasks_count', 0)}*\n"
        f"💸 Total Withdrawn: *{profile.get('withdrawals_count', 0)}*\n"
        f"👥 Referrals: *{profile.get('referrals_count', 0)}*\n\n"
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
            clear_current_task(uid)
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
                bot_info = bot.get_me()
                ref_link = f"[t.me](https://t.me/{bot_info.username}?start={uid})"
            except Exception:
                ref_link = "Unable to generate link"

            profile   = get_profile(uid)
            ref_count = profile.get("referrals_count", 0)
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
                record_bonus_claim(uid)
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
        elif text == "📧 Create Account - Earn 0.25$":
            clear_state(uid)

            account = generate_account(uid)
            set_current_task(uid, account)

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
            account = get_current_task(uid)

            if not account:
                bot.send_message(
                    uid,
                    "⚠️ No active task found. Please start a new task first.",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Move task to pending queue — no balance credited yet
            task_id = add_pending_task(uid, account)
            clear_current_task(uid)
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

            # Notify owner
            profile = get_profile(uid)
            try:
                bot.send_message(
                    OWNER_ID,
                    f"📋 *New Task Submission*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"👤 {profile.get('name', 'N/A')} (`{uid}`)\n"
                    f"🆔 Task ID: `{task_id}`\n"
                    f"📧 {account.get('username', 'N/A')}\n\n"
                    f"✅ `/approve {task_id}`\n"
                    f"❌ `/reject {task_id}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # ── Cancel Task ────────────────────────────────────────────────────────
        elif text == "❌ Cancel Task":
            clear_current_task(uid)
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
            clear_current_task(uid)
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

def _process_withdrawal(uid: int, message, method: str):
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
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET withdrawals_count = withdrawals_count + 1 WHERE uid = ?",
            (uid,)
        )

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
