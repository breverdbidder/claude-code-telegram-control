#!/usr/bin/env python3
"""
AgentRemote v3.0 - Telegram Bot with Approval System
Supports LOCAL/CLOUD execution + human-in-the-loop approvals
"""

import os
import sys
import json
import psutil
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GITHUB_TOKEN = os.getenv('GH_TOKEN', os.getenv('GITHUB_TOKEN'))
GITHUB_REPO = "breverdbidder/claude-code-telegram-control"

# File paths
TASK_FILE = os.path.expanduser("~/claude_code_tasks/pending_task.txt")
APPROVAL_FILE = os.path.expanduser("~/claude_code_tasks/pending_approvals.json")
APPROVAL_RESPONSES = os.path.expanduser("~/claude_code_tasks/approval_responses.json")

# Execution mode state (per user)
user_execution_mode = {}

def detect_execution_mode():
    """Auto-detect if Claude Code is running locally"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'claude' in cmdline.lower() or 'code' in proc.info['name'].lower():
                return "local"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return "cloud"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    mode = detect_execution_mode()
    await update.message.reply_text(
        f"""🤖 *AgentRemote v3.0*

I can execute development tasks for you!

*Current Mode:* {mode.upper()}
• LOCAL: Claude Code on your desktop
• CLOUD: GitHub Actions (serverless)

*Commands:*
/task [description] - Execute a task
/cloud - Switch to cloud mode
/local - Switch to local mode
/auto - Auto-detect mode
/status - Check execution mode
/approvals - View pending approvals

*Example:*
/task Create hello.txt with "AgentRemote works!"
""",
        parse_mode='Markdown'
    )

async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute a task"""
    chat_id = update.effective_chat.id
    
    task_text = ' '.join(context.args) if context.args else None
    if not task_text:
        await update.message.reply_text(
            "❌ Please provide a task description\n\n"
            "Example: /task Create hello.txt"
        )
        return
    
    mode = user_execution_mode.get(chat_id, detect_execution_mode())
    
    await update.message.reply_text(
        f"🚀 *Task Queued*\n\n"
        f"*Mode:* {mode.upper()}\n"
        f"*Task:* {task_text}\n\n"
        f"⏳ Executing...",
        parse_mode='Markdown'
    )
    
    if mode == "local":
        os.makedirs(os.path.dirname(TASK_FILE), exist_ok=True)
        with open(TASK_FILE, 'w') as f:
            f.write(task_text)
        
        await update.message.reply_text(
            "✅ Task written to Claude Code task file\n"
            "Claude will pick it up on next check"
        )
    
    elif mode == "cloud":
        if not GITHUB_TOKEN:
            await update.message.reply_text("❌ GitHub token not configured")
            return
        
        payload = {
            "event_type": "execute-task",
            "client_payload": {
                "task": task_text,
                "chat_id": str(chat_id),
                "message_id": str(update.message.message_id)
            }
        }
        
        try:
            response = requests.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/dispatches",
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json"
                },
                json=payload
            )
            
            if response.status_code == 204:
                await update.message.reply_text(
                    "☁️ Cloud execution triggered via GitHub Actions.\n"
                    "You'll receive a notification when complete."
                )
            else:
                await update.message.reply_text(
                    f"❌ Failed to trigger cloud execution.\n"
                    f"Status: {response.status_code}\n"
                    f"Response: {response.text[:200]}"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

async def cloud_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch to cloud mode"""
    chat_id = update.effective_chat.id
    user_execution_mode[chat_id] = "cloud"
    await update.message.reply_text(
        "☁️ *Switched to CLOUD mode*\n\n"
        "Tasks will execute via GitHub Actions.\n"
        "Works even when your desktop is offline!",
        parse_mode='Markdown'
    )

async def local_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch to local mode"""
    chat_id = update.effective_chat.id
    user_execution_mode[chat_id] = "local"
    await update.message.reply_text(
        "💻 *Switched to LOCAL mode*\n\n"
        "Tasks will execute via Claude Code on your desktop.\n"
        "Faster but requires desktop to be running.",
        parse_mode='Markdown'
    )

async def auto_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-detect execution mode"""
    chat_id = update.effective_chat.id
    mode = detect_execution_mode()
    user_execution_mode[chat_id] = mode
    
    await update.message.reply_text(
        f"🔄 *Auto-detected mode: {mode.upper()}*\n\n"
        f"{'Claude Code is running locally' if mode == 'local' else 'No local Claude Code detected - using cloud'}",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check execution mode and pending tasks"""
    chat_id = update.effective_chat.id
    mode = user_execution_mode.get(chat_id, detect_execution_mode())
    
    pending_count = 0
    if os.path.exists(APPROVAL_FILE):
        try:
            with open(APPROVAL_FILE, 'r') as f:
                approvals = json.load(f)
                pending_count = len(approvals)
        except:
            pass
    
    await update.message.reply_text(
        f"📊 *AgentRemote Status*\n\n"
        f"*Execution Mode:* {mode.upper()}\n"
        f"*Pending Approvals:* {pending_count}\n"
        f"*GitHub Repo:* {GITHUB_REPO}",
        parse_mode='Markdown'
    )

async def approvals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View and manage pending approvals"""
    if not os.path.exists(APPROVAL_FILE):
        await update.message.reply_text("✅ No pending approvals")
        return
    
    try:
        with open(APPROVAL_FILE, 'r') as f:
            approvals = json.load(f)
    except:
        await update.message.reply_text("✅ No pending approvals")
        return
    
    if not approvals:
        await update.message.reply_text("✅ No pending approvals")
        return
    
    for approval_id, data in approvals.items():
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_yes:{approval_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"approve_no:{approval_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔐 *Approval Request*\n\n"
            f"*Task:* {data.get('task', 'Unknown')}\n"
            f"*Request:* {data.get('request', 'Unknown')}\n"
            f"*Time:* {data.get('created_at', 'Unknown')[:19]}\n\n"
            f"Choose an action:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approval button clicks"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(':')
    if len(parts) != 2:
        return
    
    action_part = parts[0]
    approval_id = parts[1]
    action = action_part.split('_')[1]
    
    approvals = {}
    if os.path.exists(APPROVAL_FILE):
        try:
            with open(APPROVAL_FILE, 'r') as f:
                approvals = json.load(f)
        except:
            pass
    
    if approval_id not in approvals:
        await query.edit_message_text("⚠️ Approval request expired or already processed")
        return
    
    approval_data = approvals[approval_id]
    
    response = {
        'approval_id': approval_id,
        'action': 'approved' if action == 'yes' else 'rejected',
        'timestamp': datetime.now().isoformat(),
        'task': approval_data.get('task', 'Unknown'),
        'request': approval_data.get('request', 'Unknown')
    }
    
    responses = {}
    if os.path.exists(APPROVAL_RESPONSES):
        try:
            with open(APPROVAL_RESPONSES, 'r') as f:
                responses = json.load(f)
        except:
            pass
    
    responses[approval_id] = response
    
    os.makedirs(os.path.dirname(APPROVAL_RESPONSES), exist_ok=True)
    with open(APPROVAL_RESPONSES, 'w') as f:
        json.dump(responses, f, indent=2)
    
    del approvals[approval_id]
    with open(APPROVAL_FILE, 'w') as f:
        json.dump(approvals, f, indent=2)
    
    emoji = "✅" if action == 'yes' else "❌"
    status = "APPROVED" if action == 'yes' else "REJECTED"
    
    await query.edit_message_text(
        f"{emoji} *{status}*\n\n"
        f"*Task:* {approval_data.get('task', 'Unknown')}\n"
        f"*Request:* {approval_data.get('request', 'Unknown')}\n"
        f"*Time:* {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"✓ Response sent to Claude Code",
        parse_mode='Markdown'
    )

def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    print("🤖 AgentRemote v3.0 starting...")
    print(f"📡 Execution mode: {detect_execution_mode().upper()}")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("cloud", cloud_mode))
    app.add_handler(CommandHandler("local", local_mode))
    app.add_handler(CommandHandler("auto", auto_mode))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("approvals", approvals_command))
    app.add_handler(CallbackQueryHandler(handle_approval_callback))
    
    print("✅ AgentRemote v3.0 is running!")
    print("💬 Send /start in Telegram to begin")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
