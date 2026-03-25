#!/usr/bin/env python3
"""
AgentRemote v5.0 — Dual-Lingo Interactive Agent
Features over v4:
  • Context-aware inline buttons after every task/notification
  • Hebrew RTL auto-detection + dual-lingo responses
  • /interactive loop mode (Telegram Mode)
  • CLAUDE.md enforcement of loop pattern
"""

import os
import sys
import json
import time
import re
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import requests
import psutil

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GITHUB_REPO = "breverdbidder/claude-code-telegram-control"
AUTHORIZED_USERS = os.getenv("AUTHORIZED_USERS", "").split(",")

SMART_ROUTER_URL = os.getenv(
    "SMART_ROUTER_URL", "https://litellm-proxy-dwhg.onrender.com/v1"
)
SMART_ROUTER_KEY = os.getenv(
    "SMART_ROUTER_KEY", "sk-biddeed-litellm-2026-secure"
)

# ── Gemini Flash — PRIMARY chat LLM (FREE on paid plan) ──────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

CHAT_SYSTEM_PROMPT = (
    "You are AgentRemote, a bilingual AI assistant (English + Hebrew). "
    "You help Ariel Shapira manage his real estate tech ecosystem: BidDeed.AI, ZoneWise.AI, "
    "and Everest Capital USA. You can also discuss his son Michael's competitive swimming. "
    "Auto-detect the user's language: if they write in Hebrew, respond fully in Hebrew. "
    "If English, respond in English. Keep responses concise (Telegram limit). "
    "For tasks that require code execution, suggest using /task or /interactive commands."
)

RATE_LIMIT_TASKS_PER_HOUR = int(os.getenv("RATE_LIMIT_TASKS_PER_HOUR", "10"))
user_task_counts: dict = {}

task_queue: list = []
task_history: list = []

EXEC_MODE = os.getenv("EXEC_MODE", "cloud")

# ── Interactive-loop state  {chat_id: bool} ───────────────────
interactive_sessions: dict = {}  # chat_id → True while in loop
last_task_context: dict = {}     # chat_id → {task, mode, timestamp}

# ══════════════════════════════════════════════════════════════
#  LANGUAGE DETECTION — Hebrew / English
# ══════════════════════════════════════════════════════════════

HEBREW_RANGE = re.compile(r"[\u0590-\u05FF]")

def detect_lang(text: str) -> str:
    """Return 'he' if text contains Hebrew characters, else 'en'."""
    if HEBREW_RANGE.search(text or ""):
        return "he"
    return "en"

def chat_with_gemini(user_message: str, lang: str = "en") -> str:
    """Call Gemini Flash for conversational responses. FREE on paid plan."""
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY not configured. Use /task for execution." if lang == "en" \
            else "⚠️ מפתח Gemini לא מוגדר. השתמש ב-/task לביצוע."
    try:
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{CHAT_SYSTEM_PROMPT}\n\nUser: {user_message}"}]}
            ],
            "generationConfig": {
                "maxOutputTokens": 1024,
                "temperature": 0.7,
            },
        }
        resp = requests.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "…")
            return "🤖 (empty response)"
        else:
            logger.warning(f"Gemini {resp.status_code}: {resp.text[:200]}")
            return f"⚠️ Gemini error ({resp.status_code}). Use /task for execution."
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        return f"⚠️ Chat error: {e}"


# ── Bilingual string table ────────────────────────────────────
STRINGS = {
    # /start
    "welcome_title":       {"en": "🤖 AgentRemote v5.0",
                            "he": "🤖 AgentRemote גרסה 5.0"},
    "welcome_subtitle":    {"en": "Autonomous task execution via GitHub Actions.",
                            "he": "ביצוע משימות אוטונומי דרך GitHub Actions."},
    "section_tasks":       {"en": "📋 Task Commands",
                            "he": "📋 פקודות משימה"},
    "section_exec":        {"en": "⚡ Execution Mode",
                            "he": "⚡ מצב ביצוע"},
    "section_qa":          {"en": "📊 QA Commands",
                            "he": "📊 פקודות QA"},
    "section_new":         {"en": "🆕 v5 Features",
                            "he": "🆕 חידושי גרסה 5"},
    # task flow
    "task_queued":         {"en": "🚀 Task Queued",
                            "he": "🚀 משימה בתור"},
    "executing":           {"en": "⏳ Executing…",
                            "he": "⏳ מבצע…"},
    "cloud_triggered":     {"en": "✅ Cloud execution triggered",
                            "he": "✅ ביצוע בענן הופעל"},
    "cloud_monitor":       {"en": "GitHub Actions is running your task.\n📱 Notification on completion.",
                            "he": "GitHub Actions מריץ את המשימה.\n📱 תקבל הודעה בסיום."},
    "local_queued":        {"en": "✅ Task queued for local execution",
                            "he": "✅ משימה בתור לביצוע מקומי"},
    "exec_failed":         {"en": "❌ Execution failed",
                            "he": "❌ הביצוע נכשל"},
    # buttons
    "btn_run_again":       {"en": "🔄 Run Again",    "he": "🔄 הרץ שוב"},
    "btn_view_actions":    {"en": "📊 View Actions",  "he": "📊 צפה בריצות"},
    "btn_run_tests":       {"en": "🧪 Run Tests",     "he": "🧪 הרץ טסטים"},
    "btn_fix_bug":         {"en": "🐛 Fix Bug",       "he": "🐛 תקן באג"},
    "btn_deploy":          {"en": "🚀 Deploy",        "he": "🚀 פרוס"},
    "btn_status":          {"en": "📊 Status",        "he": "📊 סטטוס"},
    "btn_done":            {"en": "✅ Done for now",   "he": "✅ סיימנו לעכשיו"},
    "btn_next_task":       {"en": "📋 Next Task",     "he": "📋 משימה הבאה"},
    # interactive mode
    "interactive_on":      {"en": "🔄 Interactive Mode ON\n\nI'm in Telegram Mode — waiting for your commands.\nSend any message and I'll execute it.\nTap \"Done for now\" to exit.",
                            "he": "🔄 מצב אינטראקטיבי פעיל\n\nאני במצב טלגרם — מחכה לפקודות שלך.\nשלח כל הודעה ואבצע אותה.\nלחץ \"סיימנו לעכשיו\" לסיום."},
    "interactive_off":     {"en": "👋 Interactive Mode OFF. Back to command mode.\nUse /interactive to re-enter.",
                            "he": "👋 מצב אינטראקטיבי כבוי. חזרנו למצב פקודות.\nהשתמש ב- /interactive לחזור."},
    "interactive_exec":    {"en": "⚡ Executing from interactive loop:",
                            "he": "⚡ מבצע מתוך לולאה אינטראקטיבית:"},
    # general
    "unauthorized":        {"en": "❌ Unauthorized", "he": "❌ אין הרשאה"},
    "rate_limited":        {"en": "⚠️ Rate limit exceeded", "he": "⚠️ חריגה ממגבלת קצב"},
    "no_task_desc":        {"en": "Please provide a task description:\n/task Create a test file",
                            "he": "נא לספק תיאור משימה:\n/task צור קובץ בדיקה"},
}

def t(key: str, lang: str) -> str:
    """Translate key to language, fallback to English."""
    return STRINGS.get(key, {}).get(lang, STRINGS.get(key, {}).get("en", key))


# ══════════════════════════════════════════════════════════════
#  INLINE KEYBOARD BUILDERS
# ══════════════════════════════════════════════════════════════

def build_post_task_keyboard(lang: str, task_desc: str = "") -> InlineKeyboardMarkup:
    """Context-aware buttons shown after a task is dispatched."""
    task_lower = (task_desc or "").lower()

    row1 = [
        InlineKeyboardButton(t("btn_run_again", lang), callback_data="action:run_again"),
        InlineKeyboardButton(t("btn_view_actions", lang),
                             url=f"https://github.com/{GITHUB_REPO}/actions"),
    ]
    row2 = []

    # Context-aware: if task mentions test/bug/deploy, show relevant buttons
    if any(w in task_lower for w in ("test", "טסט", "בדיקה", "spec")):
        row2.append(InlineKeyboardButton(t("btn_run_tests", lang), callback_data="action:run_tests"))
    if any(w in task_lower for w in ("bug", "fix", "error", "באג", "תקן", "שגיאה")):
        row2.append(InlineKeyboardButton(t("btn_fix_bug", lang), callback_data="action:fix_bug"))
    if any(w in task_lower for w in ("deploy", "release", "push", "פרוס", "שחרר")):
        row2.append(InlineKeyboardButton(t("btn_deploy", lang), callback_data="action:deploy"))

    # Always offer status
    row2.append(InlineKeyboardButton(t("btn_status", lang), callback_data="action:status"))

    rows = [row1]
    if row2:
        rows.append(row2)
    return InlineKeyboardMarkup(rows)


def build_interactive_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Buttons shown during interactive loop."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_run_tests", lang), callback_data="action:run_tests"),
            InlineKeyboardButton(t("btn_fix_bug", lang), callback_data="action:fix_bug"),
            InlineKeyboardButton(t("btn_deploy", lang), callback_data="action:deploy"),
        ],
        [
            InlineKeyboardButton(t("btn_status", lang), callback_data="action:status"),
            InlineKeyboardButton(t("btn_done", lang), callback_data="action:done"),
        ],
    ])


def build_completion_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Buttons shown when GHA webhook reports task completion."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_run_again", lang), callback_data="action:run_again"),
            InlineKeyboardButton(t("btn_next_task", lang), callback_data="action:next_task"),
        ],
        [
            InlineKeyboardButton(t("btn_view_actions", lang),
                                 url=f"https://github.com/{GITHUB_REPO}/actions"),
            InlineKeyboardButton(t("btn_done", lang), callback_data="action:done"),
        ],
    ])


# ══════════════════════════════════════════════════════════════
#  CORE HELPERS (unchanged from v4)
# ══════════════════════════════════════════════════════════════

def detect_claude_code_running() -> bool:
    try:
        for proc in psutil.process_iter(["name", "cmdline"]):
            name = proc.info.get("name", "") or ""
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "claude" in name.lower() or "claude-code" in cmdline.lower():
                return True
    except Exception:
        pass
    return False


def get_effective_mode() -> str:
    if EXEC_MODE == "auto":
        return "local" if detect_claude_code_running() else "cloud"
    return EXEC_MODE


def check_authentication(user_id: str) -> bool:
    if not AUTHORIZED_USERS or AUTHORIZED_USERS == [""]:
        return True
    return str(user_id) in AUTHORIZED_USERS


def check_rate_limit(user_id: str) -> bool:
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    if user_id in user_task_counts:
        user_task_counts[user_id] = [
            (ts, tsk) for ts, tsk in user_task_counts[user_id] if ts > hour_ago
        ]
    else:
        user_task_counts[user_id] = []
    return len(user_task_counts[user_id]) < RATE_LIMIT_TASKS_PER_HOUR


def record_task(user_id: str, task_desc: str):
    if user_id not in user_task_counts:
        user_task_counts[user_id] = []
    user_task_counts[user_id].append((datetime.now(), task_desc))


def execute_cloud_task(task_desc: str, chat_id: str, message_id: str) -> dict:
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
        headers = {
            "Authorization": f"token {GH_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "event_type": "execute-task",
            "client_payload": {
                "task": task_desc,
                "chat_id": chat_id,
                "message_id": message_id,
                "smart_router_url": SMART_ROUTER_URL,
                "smart_router_key": SMART_ROUTER_KEY,
                "use_smart_router": True,
            },
        }
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 204:
            entry = {
                "task": task_desc,
                "chat_id": chat_id,
                "timestamp": datetime.now().isoformat(),
                "status": "queued",
            }
            task_queue.append(entry)
            task_history.append({**entry, "status": "success"})
            return {"success": True, "message": "Task queued successfully"}
        else:
            error_msg = f"GitHub API error: {response.status_code}"
            logger.error(f"{error_msg}: {response.text}")
            task_history.append({
                "task": task_desc, "chat_id": chat_id,
                "timestamp": datetime.now().isoformat(),
                "status": "failed", "error": error_msg,
            })
            return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Error triggering cloud execution: {e}"
        logger.error(error_msg)
        task_history.append({
            "task": task_desc, "chat_id": chat_id,
            "timestamp": datetime.now().isoformat(),
            "status": "failed", "error": error_msg,
        })
        return {"success": False, "error": error_msg}


# ══════════════════════════════════════════════════════════════
#  DISPATCH TASK — unified for commands + buttons + interactive
# ══════════════════════════════════════════════════════════════

async def dispatch_task(task_desc: str, chat_id: str, message_id: str,
                        lang: str, reply_func, user_id: str):
    """Fire a task and reply with context-aware buttons."""
    mode = get_effective_mode()
    mode_label = "☁️ Cloud" if mode == "cloud" else "🖥️ Local"

    # Escape for MarkdownV2
    safe_task = task_desc[:200].replace(".", "\\.").replace("-", "\\-").replace("(", "\\(").replace(")", "\\)")

    await reply_func(
        f"*{t('task_queued', lang)}*\n\n"
        f"📋 `{safe_task}`\n"
        f"⚡ Mode: {mode_label}\n\n"
        f"{t('executing', lang)}",
        parse_mode="MarkdownV2",
    )

    if mode == "cloud":
        result = execute_cloud_task(task_desc, chat_id, message_id)
    else:
        try:
            task_file = os.path.expanduser(
                f"~/claude_tasks/{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            )
            os.makedirs(os.path.dirname(task_file), exist_ok=True)
            with open(task_file, "w") as f:
                f.write(f"# Task\n{task_desc}\n")
            result = {"success": True, "message": f"Written: {task_file}"}
        except Exception as e:
            result = {"success": False, "error": str(e)}

    record_task(user_id, task_desc)

    # Store context for button callbacks
    last_task_context[chat_id] = {
        "task": task_desc,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "lang": lang,
    }

    kb = build_post_task_keyboard(lang, task_desc)

    if result["success"]:
        if mode == "cloud":
            await reply_func(
                f"*{t('cloud_triggered', lang)}*\n\n"
                f"{t('cloud_monitor', lang)}",
                parse_mode="Markdown",
                reply_markup=kb,
            )
        else:
            await reply_func(
                f"*{t('local_queued', lang)}*",
                parse_mode="Markdown",
                reply_markup=kb,
            )
    else:
        err = result.get("error", "Unknown error")
        await reply_func(
            f"*{t('exec_failed', lang)}*\n\n`{err}`",
            parse_mode="Markdown",
            reply_markup=kb,
        )


# ══════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_authentication(str(uid)):
        await update.message.reply_text(t("unauthorized", "en"))
        return

    lang = detect_lang(update.message.text or "")

    # RTL marker for Hebrew
    rtl = "\u200F" if lang == "he" else ""

    lines = [
        f"*{rtl}{t('welcome_title', lang)}*",
        f"{rtl}{t('welcome_subtitle', lang)}",
        "",
        f"*{rtl}{t('section_tasks', lang)}*",
        f"{rtl}/task `<description>` — {'בצע משימה' if lang == 'he' else 'Execute a task'}",
        f"{rtl}/status — {'סטטוס מערכת' if lang == 'he' else 'System status'}",
        f"{rtl}/queue — {'תור פעיל' if lang == 'he' else 'Active queue'}",
        f"{rtl}/history — {'היסטוריה' if lang == 'he' else 'Past tasks'}",
        "",
        f"*{rtl}{t('section_exec', lang)}*",
        f"{rtl}/mode — {'הצג מצב' if lang == 'he' else 'Show mode'}",
        f"{rtl}/cloud — {'ענן' if lang == 'he' else 'Force cloud'}",
        f"{rtl}/local — {'מקומי' if lang == 'he' else 'Force local'}",
        f"{rtl}/auto — {'אוטומטי' if lang == 'he' else 'Auto-detect'}",
        "",
        f"*{rtl}{t('section_qa', lang)}*",
        f"{rtl}/qa — {'ציוני QA' if lang == 'he' else 'QA scores'}",
        f"{rtl}/qa\\_trigger — {'הפעל QA' if lang == 'he' else 'Run QA now'}",
        f"{rtl}/qa\\_issues — {'בעיות קריטיות' if lang == 'he' else 'Critical issues'}",
        "",
        f"*{rtl}{t('section_new', lang)}*",
        f"{rtl}/interactive — {'מצב אינטראקטיבי (לולאה)' if lang == 'he' else 'Interactive loop mode'}",
        f"{rtl}{'כפתורים חכמים אחרי כל משימה' if lang == 'he' else 'Smart buttons after every task'}",
        f"{rtl}{'זיהוי שפה אוטומטי — עברית/English' if lang == 'he' else 'Auto language — English/עברית'}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    if not check_authentication(uid):
        await update.message.reply_text(t("unauthorized", "en"))
        return

    lang = detect_lang(" ".join(context.args) if context.args else "")

    if not check_rate_limit(uid):
        await update.message.reply_text(t("rate_limited", lang))
        return

    task_desc = " ".join(context.args)
    if not task_desc:
        await update.message.reply_text(t("no_task_desc", lang))
        return

    await dispatch_task(
        task_desc, chat_id, str(update.message.message_id),
        lang, update.message.reply_text, uid,
    )


# ── Interactive loop ──────────────────────────────────────────

async def cmd_interactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enter Telegram Mode — infinite interactive loop."""
    uid = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    if not check_authentication(uid):
        await update.message.reply_text(t("unauthorized", "en"))
        return

    lang = detect_lang(update.message.text or "")
    interactive_sessions[chat_id] = True

    kb = build_interactive_keyboard(lang)
    await update.message.reply_text(
        t("interactive_on", lang),
        reply_markup=kb,
    )


async def handle_interactive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages: interactive loop → task dispatch, otherwise → Gemini chat."""
    chat_id = str(update.effective_chat.id)
    uid = str(update.effective_user.id)

    if not check_authentication(uid):
        return

    text = update.message.text or ""
    lang = detect_lang(text)

    # ── INTERACTIVE MODE: dispatch as task ────────────────────
    if interactive_sessions.get(chat_id):
        if not check_rate_limit(uid):
            await update.message.reply_text(t("rate_limited", lang))
            return

        await update.message.reply_text(
            f"*{t('interactive_exec', lang)}*\n`{text[:100]}`",
            parse_mode="Markdown",
        )

        await dispatch_task(
            text, chat_id, str(update.message.message_id),
            lang, update.message.reply_text, uid,
        )

        kb = build_interactive_keyboard(lang)
        rtl = "\u200F" if lang == "he" else ""
        prompt = f"{rtl}{'מה הלאה?' if lang == 'he' else 'What next?'}"
        await update.message.reply_text(prompt, reply_markup=kb)
        return

    # ── NORMAL MODE: conversational chat via Gemini Flash (FREE) ─
    response = chat_with_gemini(text, lang)

    # Build light keyboard for chat responses
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                t("btn_status", lang), callback_data="action:status"
            ),
            InlineKeyboardButton(
                "📋 /task" if lang == "en" else "📋 משימה",
                callback_data="action:next_task",
            ),
        ]
    ])

    await update.message.reply_text(response, reply_markup=kb)


# ── Callback query handler for ALL inline buttons ─────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()

    chat_id = str(query.message.chat_id)
    uid = str(query.from_user.id)
    data = query.data or ""
    action = data.replace("action:", "")

    # Detect lang from last context or default
    ctx = last_task_context.get(chat_id, {})
    lang = ctx.get("lang", "en")

    if action == "done":
        # Exit interactive mode
        interactive_sessions[chat_id] = False
        await query.message.reply_text(t("interactive_off", lang))
        return

    if action == "next_task":
        # Prompt for next task
        rtl = "\u200F" if lang == "he" else ""
        prompt = f"{rtl}{'שלח את המשימה הבאה:' if lang == 'he' else 'Send your next task:'}"
        await query.message.reply_text(prompt)
        # Enable interactive mode so free-text works
        interactive_sessions[chat_id] = True
        return

    if action == "status":
        # Quick inline status
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        mode = get_effective_mode()
        tasks_hour = len(user_task_counts.get(uid, []))
        await query.message.reply_text(
            f"📊 *{'סטטוס' if lang == 'he' else 'Status'}*\n\n"
            f"🤖 Bot: ✅\n"
            f"⚡ Mode: `{mode}`\n"
            f"💻 CPU: `{cpu}%` | RAM: `{mem}%`\n"
            f"📋 Tasks/hr: `{tasks_hour}/{RATE_LIMIT_TASKS_PER_HOUR}`",
            parse_mode="Markdown",
        )
        return

    if action == "view_actions":
        # Already handled via URL button, but just in case
        return

    # ── Task-dispatching buttons ──────────────────────────────
    task_map = {
        "run_again":  ctx.get("task", "echo 'no previous task'"),
        "run_tests":  "Run all tests and report results to Telegram",
        "fix_bug":    "Analyze recent errors in logs, identify the bug, and fix it",
        "deploy":     "Deploy latest changes to production (Cloudflare + Render)",
    }

    task_desc = task_map.get(action)
    if task_desc:
        await dispatch_task(
            task_desc, chat_id, str(query.message.message_id),
            lang, query.message.reply_text, uid,
        )
        # If in interactive mode, re-show loop keyboard
        if interactive_sessions.get(chat_id):
            kb = build_interactive_keyboard(lang)
            rtl = "\u200F" if lang == "he" else ""
            await query.message.reply_text(
                f"{rtl}{'מה הלאה?' if lang == 'he' else 'What next?'}",
                reply_markup=kb,
            )


# ── Status / Queue / History (preserved from v4) ─────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not check_authentication(uid):
        await update.message.reply_text(t("unauthorized", "en"))
        return
    lang = detect_lang(update.message.text or "")
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    try:
        rr = requests.get(f"{SMART_ROUTER_URL}/health", timeout=5)
        router = "✅ Online" if rr.status_code == 200 else "❌ Offline"
    except Exception:
        router = "⚠️ Unknown"
    tasks_hour = len(user_task_counts.get(uid, []))
    remaining = RATE_LIMIT_TASKS_PER_HOUR - tasks_hour
    mode = get_effective_mode()
    in_loop = interactive_sessions.get(str(update.effective_chat.id), False)

    rtl = "\u200F" if lang == "he" else ""
    await update.message.reply_text(
        f"{rtl}📊 *{'סטטוס מערכת' if lang == 'he' else 'System Status'}*\n\n"
        f"🤖 Bot: ✅  |  ⚡ Mode: `{mode}`\n"
        f"🔄 {'לולאה:' if lang == 'he' else 'Loop:'} `{'ON' if in_loop else 'OFF'}`\n"
        f"☁️ GitHub Actions: ✅\n"
        f"🎯 Smart Router: {router}\n\n"
        f"💻 CPU: `{cpu}%` | RAM: `{mem}%`\n"
        f"📋 {'משימות/שעה' if lang == 'he' else 'Tasks/hr'}: `{tasks_hour}/{RATE_LIMIT_TASKS_PER_HOUR}` "
        f"({'נותרו' if lang == 'he' else 'left'}: `{remaining}`)\n"
        f"📋 {'בתור' if lang == 'he' else 'Queue'}: `{len(task_queue)}` | "
        f"{'היסטוריה' if lang == 'he' else 'History'}: `{len(task_history)}`",
        parse_mode="Markdown",
    )


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not check_authentication(uid):
        await update.message.reply_text(t("unauthorized", "en"))
        return
    lang = detect_lang(update.message.text or "")
    if not task_queue:
        rtl = "\u200F" if lang == "he" else ""
        await update.message.reply_text(f"{rtl}📋 {'תור ריק' if lang == 'he' else 'Queue empty'}")
        return
    lines = [f"📋 {'תור משימות' if lang == 'he' else 'Task Queue'}\n"]
    for i, item in enumerate(task_queue[-10:], 1):
        lines.append(f"{i}. {item['task'][:50]}…  ({item['status']})")
    await update.message.reply_text("\n".join(lines))


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not check_authentication(uid):
        await update.message.reply_text(t("unauthorized", "en"))
        return
    lang = detect_lang(update.message.text or "")
    if not task_history:
        rtl = "\u200F" if lang == "he" else ""
        await update.message.reply_text(f"{rtl}📜 {'אין היסטוריה' if lang == 'he' else 'No history'}")
        return
    lines = [f"📜 {'היסטוריה (10 אחרונות)' if lang == 'he' else 'History (Last 10)'}\n"]
    for i, item in enumerate(reversed(task_history[-10:]), 1):
        emoji = "✅" if item["status"] == "success" else "❌"
        lines.append(f"{i}. {emoji} {item['task'][:40]}…  {item['timestamp'][:16]}")
    await update.message.reply_text("\n".join(lines))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not check_authentication(uid):
        await update.message.reply_text(t("unauthorized", "en"))
        return
    total = len(task_history)
    ok = sum(1 for t_ in task_history if t_["status"] == "success")
    rate = (ok / total * 100) if total else 0
    lang = detect_lang(update.message.text or "")
    rtl = "\u200F" if lang == "he" else ""
    await update.message.reply_text(
        f"{rtl}📈 *{'סטטיסטיקות' if lang == 'he' else 'Stats'}*\n\n"
        f"{'סה\"כ' if lang == 'he' else 'Total'}: {total}\n"
        f"✅ {'הצלחות' if lang == 'he' else 'OK'}: {ok}\n"
        f"❌ {'כשלונות' if lang == 'he' else 'Failed'}: {total - ok}\n"
        f"📈 {'אחוז הצלחה' if lang == 'he' else 'Success rate'}: {rate:.0f}%",
        parse_mode="Markdown",
    )


# ── Mode commands (preserved) ─────────────────────────────────

async def cmd_cloud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global EXEC_MODE
    EXEC_MODE = "cloud"
    lang = detect_lang(update.message.text or "")
    rtl = "\u200F" if lang == "he" else ""
    await update.message.reply_text(
        f"{rtl}☁️ *{'מצב ענן הופעל' if lang == 'he' else 'Cloud mode activated'}*\n\n"
        f"{rtl}{'משימות ירוצו ב-GitHub Actions — עובד גם כשהמחשב ישן.' if lang == 'he' else 'Tasks run via GitHub Actions — works offline.'}",
        parse_mode="Markdown",
    )


async def cmd_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global EXEC_MODE
    EXEC_MODE = "local"
    lang = detect_lang(update.message.text or "")
    rtl = "\u200F" if lang == "he" else ""
    await update.message.reply_text(
        f"{rtl}🖥️ *{'מצב מקומי הופעל' if lang == 'he' else 'Local mode activated'}*\n\n"
        f"{rtl}{'דורש מחשב פעיל עם Claude Code.' if lang == 'he' else 'Requires desktop + Claude Code running.'}",
        parse_mode="Markdown",
    )


async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global EXEC_MODE
    EXEC_MODE = "auto"
    current = get_effective_mode()
    cc = detect_claude_code_running()
    lang = detect_lang(update.message.text or "")
    rtl = "\u200F" if lang == "he" else ""
    await update.message.reply_text(
        f"{rtl}🔄 *{'מצב אוטומטי' if lang == 'he' else 'Auto mode activated'}*\n\n"
        f"Claude Code: `{'פעיל' if cc else 'כבוי'}` → `{current}`",
        parse_mode="Markdown",
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = get_effective_mode()
    cc = detect_claude_code_running()
    lang = detect_lang(update.message.text or "")
    rtl = "\u200F" if lang == "he" else ""
    icon = "☁️" if mode == "cloud" else "🖥️"
    await update.message.reply_text(
        f"{rtl}⚡ *{'מצב ביצוע' if lang == 'he' else 'Execution Mode'}*\n\n"
        f"{'הגדרה' if lang == 'he' else 'Setting'}: `{EXEC_MODE}`\n"
        f"{'בפועל' if lang == 'he' else 'Effective'}: {icon} `{mode}`\n"
        f"Claude Code: `{'פעיל' if cc else 'כבוי'}`\n\n"
        f"[Actions](https://github.com/{GITHUB_REPO}/actions)",
        parse_mode="Markdown",
    )


# ── QA commands (preserved from v4) ──────────────────────────

def get_sb():
    url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return url, key

def score_bar(s): return "[" + "█" * int(s * 10) + "░" * (10 - int(s * 10)) + f"] {s*100:.0f}%"
def score_emoji(s): return "🟢" if s >= 0.95 else ("🟡" if s >= 0.80 else "🔴")


async def cmd_qa(update, context):
    import urllib.request as _req
    await update.message.reply_text("🔍 Fetching QA…")
    url, key = get_sb()
    try:
        r = _req.Request(
            f"{url}/rest/v1/insights?type=eq.qa_sentinel&order=timestamp.desc&limit=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        with _req.urlopen(r) as resp:
            rows = json.loads(resp.read().decode())
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}"); return
    if not rows:
        await update.message.reply_text("⏳ No QA runs yet."); return
    row = rows[0]
    details = json.loads(row["details"]) if isinstance(row["details"], str) else row["details"]
    scores = details.get("scores", {})
    status = row["status"].upper()
    overall = row.get("score", 0.0)
    ts = row["timestamp"][:16].replace("T", " ")
    lines = [
        f"📊 *QA — {'✅ PASS' if status == 'PASS' else '❌ FAIL'}*",
        f"`{ts} UTC` | `{overall*100:.0f}%`", "",
        f"*BidDeed.AI*",
        f"  {score_emoji(scores.get('biddeed_unit',0))} Unit: `{scores.get('biddeed_unit',0)*100:.0f}%`",
        f"  {score_emoji(scores.get('biddeed_evals',0))} DeepEval: `{scores.get('biddeed_evals',0)*100:.0f}%`", "",
        f"*ZoneWise.AI*",
        f"  {score_emoji(scores.get('zonewise_agent',0))} Agents: `{scores.get('zonewise_agent',0)*100:.0f}%`",
        f"  {score_emoji(scores.get('zonewise_e2e_pass_rate',0))} E2E: `{scores.get('zonewise_e2e_pass_rate',0)*100:.0f}%`",
    ]
    failures = details.get("failures", [])
    if failures:
        lines += ["", "*Failures:*"]
        for f_ in failures:
            lines.append(f"  ❌ `{f_['layer']}` → {f_['score']*100:.0f}%")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_qa_trigger(update, context):
    import urllib.request as _req
    await update.message.reply_text("🚀 Triggering QA…")
    payload = json.dumps({"ref": "main"}).encode()
    r = _req.Request(
        "https://api.github.com/repos/breverdbidder/qa-agentic-pipeline/actions/workflows/nightly-qa.yml/dispatches",
        data=payload,
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github.v3+json",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _req.urlopen(r) as resp:
            ok = resp.status in [200, 204]
    except Exception:
        ok = False
    if ok:
        await update.message.reply_text("✅ QA triggered. ~15 min.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Trigger failed.")


async def cmd_qa_issues(update, context):
    import urllib.request as _req
    try:
        r = _req.Request(
            "https://api.github.com/repos/breverdbidder/qa-agentic-pipeline/issues?labels=qa-critical&state=open",
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"},
        )
        with _req.urlopen(r) as resp:
            issues = json.loads(resp.read().decode())
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}"); return
    if not issues:
        await update.message.reply_text("✅ No open QA issues."); return
    lines = [f"🚨 *{len(issues)} Open QA Issue(s)*"]
    for iss in issues[:5]:
        lines.append(f"• [{iss['title'][:55]}]({iss['html_url']})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    if not GH_TOKEN:
        logger.error("GH_TOKEN not set")
        sys.exit(1)

    logger.info("🚀 AgentRemote v5.0 starting — Dual-Lingo Interactive Agent")
    logger.info(f"⚡ Mode: {EXEC_MODE}")
    logger.info(f"🔒 Auth: {'ON' if AUTHORIZED_USERS != [''] else 'OFF'}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("stats", cmd_stats))
    # Execution mode
    app.add_handler(CommandHandler("cloud", cmd_cloud))
    app.add_handler(CommandHandler("local", cmd_local))
    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("mode", cmd_mode))
    # QA
    app.add_handler(CommandHandler("qa", cmd_qa))
    app.add_handler(CommandHandler("qa_trigger", cmd_qa_trigger))
    app.add_handler(CommandHandler("qa_issues", cmd_qa_issues))
    # v5: Interactive loop
    app.add_handler(CommandHandler("interactive", cmd_interactive))
    # v5: Inline button callbacks
    app.add_handler(CallbackQueryHandler(button_callback))
    # v5: Free-text handler for interactive mode (MUST be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interactive_message))

    logger.info("✅ AgentRemote v5.0 ready — /start to begin")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
