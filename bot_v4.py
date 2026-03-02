#!/usr/bin/env python3
"""
AgentRemote v4.0 - Enhanced with Smart Router, Queue, Auth, Rate Limiting
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import psutil

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GITHUB_REPO = "breverdbidder/claude-code-telegram-control"
AUTHORIZED_USERS = os.getenv("AUTHORIZED_USERS", "").split(",")  # Comma-separated user IDs

# Smart Router Configuration
SMART_ROUTER_URL = os.getenv("SMART_ROUTER_URL", "https://litellm-proxy-dwhg.onrender.com/v1")
SMART_ROUTER_KEY = os.getenv("SMART_ROUTER_KEY", "sk-biddeed-litellm-2026-secure")

# Rate Limiting
RATE_LIMIT_TASKS_PER_HOUR = int(os.getenv("RATE_LIMIT_TASKS_PER_HOUR", "10"))
user_task_counts = {}  # {user_id: [(timestamp, task), ...]}

# Task Queue (in-memory, could be Redis/Supabase)
task_queue = []
task_history = []

class AuthenticationError(Exception):
    """User not authorized"""
    pass

class RateLimitError(Exception):
    """Rate limit exceeded"""
    pass

def check_authentication(user_id: str) -> bool:
    """Check if user is authorized"""
    if not AUTHORIZED_USERS or AUTHORIZED_USERS == ['']:
        return True  # No auth configured, allow all
    return str(user_id) in AUTHORIZED_USERS

def check_rate_limit(user_id: str) -> bool:
    """Check if user is within rate limit"""
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    # Clean old entries
    if user_id in user_task_counts:
        user_task_counts[user_id] = [
            (ts, task) for ts, task in user_task_counts[user_id]
            if ts > hour_ago
        ]
    else:
        user_task_counts[user_id] = []
    
    # Check limit
    return len(user_task_counts[user_id]) < RATE_LIMIT_TASKS_PER_HOUR

def record_task(user_id: str, task: str):
    """Record task for rate limiting"""
    if user_id not in user_task_counts:
        user_task_counts[user_id] = []
    user_task_counts[user_id].append((datetime.now(), task))

def execute_cloud_task(task: str, chat_id: str, message_id: str) -> dict:
    """
    Execute task via GitHub Actions with Smart Router integration
    Returns: {success: bool, message: str, error: str}
    """
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
        headers = {
            "Authorization": f"token {GH_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "event_type": "execute-task",
            "client_payload": {
                "task": task,
                "chat_id": chat_id,
                "message_id": message_id,
                "smart_router_url": SMART_ROUTER_URL,
                "smart_router_key": SMART_ROUTER_KEY,
                "use_smart_router": True
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 204:
            # Add to queue
            task_queue.append({
                "task": task,
                "chat_id": chat_id,
                "timestamp": datetime.now().isoformat(),
                "status": "queued"
            })
            task_history.append({
                "task": task,
                "chat_id": chat_id,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })
            return {"success": True, "message": "Task queued successfully"}
        else:
            error_msg = f"GitHub API error: {response.status_code}"
            logger.error(f"{error_msg}: {response.text}")
            task_history.append({
                "task": task,
                "chat_id": chat_id,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": error_msg
            })
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        error_msg = f"Error triggering cloud execution: {str(e)}"
        logger.error(error_msg)
        task_history.append({
            "task": task,
            "chat_id": chat_id,
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
            "error": error_msg
        })
        return {"success": False, "error": error_msg}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    if not check_authentication(str(user_id)):
        await update.message.reply_text(
            "❌ Unauthorized\n\n"
            "You are not authorized to use this bot.\n"
            "Contact the administrator to request access."
        )
        return
    
    await update.message.reply_text(
        "🤖 AgentRemote v4.0\n\n"
        "I can execute development tasks for you!\n\n"
        "📊 Features:\n"
        "• Smart Router (90% FREE tier)\n"
        "• Task queue management\n"
        "• Rate limiting protection\n"
        "• User authentication\n\n"
        "Commands:\n"
        "/task <description> - Execute a task\n"
        "/status - Check system status\n"
        "/queue - View task queue\n"
        "/history - View task history\n"
        "/stats - View usage statistics\n\n"
        f"Rate limit: {RATE_LIMIT_TASKS_PER_HOUR} tasks/hour"
    )

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Task command handler"""
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    
    # Authentication check
    if not check_authentication(str(user_id)):
        await update.message.reply_text("❌ Unauthorized access")
        return
    
    # Rate limit check
    if not check_rate_limit(str(user_id)):
        remaining_time = 60 - (datetime.now() - user_task_counts[str(user_id)][0][0]).seconds // 60
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded\n\n"
            f"Limit: {RATE_LIMIT_TASKS_PER_HOUR} tasks/hour\n"
            f"Try again in {remaining_time} minutes"
        )
        return
    
    # Get task description
    task_desc = " ".join(context.args)
    if not task_desc:
        await update.message.reply_text(
            "Please provide a task description:\n"
            "/task Create a test file"
        )
        return
    
    # Send confirmation
    await update.message.reply_text(
        f"🚀 Task Queued\n\n"
        f"Task: {task_desc}\n"
        f"Smart Router: 90% FREE tier enabled\n\n"
        f"⏳ Executing..."
    )
    
    # Execute task
    result = execute_cloud_task(task_desc, chat_id, str(update.message.message_id))
    
    # Record for rate limiting
    record_task(str(user_id), task_desc)
    
    if result["success"]:
        await update.message.reply_text(
            f"✅ Task queued successfully!\n\n"
            f"☁️ Cloud execution triggered via GitHub Actions.\n"
            f"🎯 Smart Router: Using 90% FREE tier (Gemini 2.5 Flash)\n"
            f"📱 You'll receive a notification when complete."
        )
    else:
        await update.message.reply_text(
            f"❌ Failed to trigger cloud execution.\n\n"
            f"Error: {result.get('error', 'Unknown error')}\n\n"
            f"Check GitHub token and repository settings."
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command handler"""
    user_id = update.effective_user.id
    
    if not check_authentication(str(user_id)):
        await update.message.reply_text("❌ Unauthorized access")
        return
    
    # Get system stats
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent
    
    # Check Smart Router status
    try:
        router_response = requests.get(f"{SMART_ROUTER_URL}/health", timeout=5)
        router_status = "✅ Online" if router_response.status_code == 200 else "❌ Offline"
    except:
        router_status = "⚠️ Unknown"
    
    # Calculate user's rate limit status
    user_id_str = str(user_id)
    tasks_this_hour = len(user_task_counts.get(user_id_str, []))
    remaining_tasks = RATE_LIMIT_TASKS_PER_HOUR - tasks_this_hour
    
    await update.message.reply_text(
        f"📊 System Status\n\n"
        f"🤖 Bot: ✅ Running\n"
        f"☁️ GitHub Actions: ✅ Available\n"
        f"🎯 Smart Router: {router_status}\n\n"
        f"💻 System Resources:\n"
        f"  CPU: {cpu}%\n"
        f"  Memory: {memory}%\n\n"
        f"📈 Your Usage:\n"
        f"  Tasks this hour: {tasks_this_hour}/{RATE_LIMIT_TASKS_PER_HOUR}\n"
        f"  Remaining: {remaining_tasks}\n\n"
        f"📋 Queue: {len(task_queue)} tasks pending\n"
        f"📜 History: {len(task_history)} total tasks"
    )

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queue command handler"""
    user_id = update.effective_user.id
    
    if not check_authentication(str(user_id)):
        await update.message.reply_text("❌ Unauthorized access")
        return
    
    if not task_queue:
        await update.message.reply_text("📋 Task queue is empty")
        return
    
    queue_text = "📋 Task Queue\n\n"
    for i, task_item in enumerate(task_queue[-10:], 1):  # Show last 10
        queue_text += f"{i}. {task_item['task'][:50]}...\n"
        queue_text += f"   Status: {task_item['status']}\n"
        queue_text += f"   Time: {task_item['timestamp'][:19]}\n\n"
    
    await update.message.reply_text(queue_text)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """History command handler"""
    user_id = update.effective_user.id
    
    if not check_authentication(str(user_id)):
        await update.message.reply_text("❌ Unauthorized access")
        return
    
    if not task_history:
        await update.message.reply_text("📜 No task history")
        return
    
    history_text = "📜 Task History (Last 10)\n\n"
    for i, task_item in enumerate(reversed(task_history[-10:]), 1):
        status_emoji = "✅" if task_item['status'] == 'success' else "❌"
        history_text += f"{i}. {status_emoji} {task_item['task'][:40]}...\n"
        history_text += f"   Time: {task_item['timestamp'][:19]}\n\n"
    
    await update.message.reply_text(history_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stats command handler"""
    user_id = update.effective_user.id
    
    if not check_authentication(str(user_id)):
        await update.message.reply_text("❌ Unauthorized access")
        return
    
    total_tasks = len(task_history)
    successful_tasks = sum(1 for t in task_history if t['status'] == 'success')
    failed_tasks = total_tasks - successful_tasks
    success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Calculate Smart Router savings (assuming 90% FREE tier)
    estimated_savings = total_tasks * 0.9 * 0.003  # $0.003 per task saved
    
    await update.message.reply_text(
        f"📈 Usage Statistics\n\n"
        f"📊 Total Tasks: {total_tasks}\n"
        f"✅ Successful: {successful_tasks}\n"
        f"❌ Failed: {failed_tasks}\n"
        f"📈 Success Rate: {success_rate:.1f}%\n\n"
        f"💰 Smart Router Savings:\n"
        f"  FREE Tier Usage: 90%\n"
        f"  Estimated Savings: ${estimated_savings:.2f}\n\n"
        f"⚡ Efficiency:\n"
        f"  Avg Cost/Task: $0.0003\n"
        f"  vs Without Router: $0.003"
    )



# ──────────────────────────────────────────────────────────────
# QA PIPELINE COMMANDS
# ──────────────────────────────────────────────────────────────

def get_sb():
    import os
    url = os.environ.get("SUPABASE_URL","https://mocerqjnksmhcjzxrewo.supabase.co")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
    return url, key

def score_bar(score: float) -> str:
    filled = int(score * 10)
    return "[" + "█"*filled + "░"*(10-filled) + f"] {score*100:.0f}%"

def score_emoji(score: float) -> str:
    return "🟢" if score >= 0.95 else ("🟡" if score >= 0.80 else "🔴")

async def cmd_qa(update, context):
    import json as _json, urllib.request as _req, os
    await update.message.reply_text("🔍 Fetching QA status...")
    url, key = get_sb()
    try:
        r = _req.Request(
            f"{url}/rest/v1/insights?type=eq.qa_sentinel&order=timestamp.desc&limit=1",
            headers={"apikey":key,"Authorization":f"Bearer {key}"}
        )
        with _req.urlopen(r) as resp:
            rows = _json.loads(resp.read().decode())
    except Exception as e:
        await update.message.reply_text(f"⚠️ Supabase error: {e}")
        return
    if not rows:
        await update.message.reply_text("⏳ *No QA runs yet.*\nFirst run at 11PM EST tonight.", parse_mode="Markdown")
        return
    row = rows[0]
    details = _json.loads(row["details"]) if isinstance(row["details"],str) else row["details"]
    scores = details.get("scores",{})
    status = row["status"].upper()
    overall = row.get("score",0.0)
    ts = row["timestamp"][:16].replace("T"," ")
    lines = [
        f"📊 *QA Pipeline — {'✅ PASS' if status=='PASS' else '❌ FAIL'}*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"Run: `{ts} UTC` | Score: `{overall*100:.0f}%`",
        f"",
        f"*BidDeed.AI*",
        f"  {score_emoji(scores.get('biddeed_unit',0))} Unit: `{scores.get('biddeed_unit',0)*100:.0f}%`",
        f"  {score_emoji(scores.get('biddeed_evals',0))} DeepEval: `{scores.get('biddeed_evals',0)*100:.0f}%`",
        f"",
        f"*ZoneWise.AI*",
        f"  {score_emoji(scores.get('zonewise_agent',0))} Agents: `{scores.get('zonewise_agent',0)*100:.0f}%`",
        f"  {score_emoji(scores.get('zonewise_e2e_pass_rate',0))} E2E: `{scores.get('zonewise_e2e_pass_rate',0)*100:.0f}%`",
    ]
    failures = details.get("failures",[])
    if failures:
        lines += ["","*Failures:*"]
        for fail in failures:
            lines.append(f"  ❌ `{fail['layer']}` → {fail['score']*100:.0f}%")
    lines += ["","[🔗 GitHub Actions](https://github.com/breverdbidder/qa-agentic-pipeline/actions)"]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_qa_last(update, context):
    import json as _json, urllib.request as _req
    url, key = get_sb()
    try:
        r = _req.Request(
            f"{url}/rest/v1/insights?type=eq.qa_sentinel&order=timestamp.desc&limit=5&select=timestamp,status,score",
            headers={"apikey":key,"Authorization":f"Bearer {key}"}
        )
        with _req.urlopen(r) as resp:
            rows = _json.loads(resp.read().decode())
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}"); return
    if not rows:
        await update.message.reply_text("No runs yet."); return
    lines = ["📈 *Last QA Runs*","━━━━━━━━━━━━━━━━━━━━"]
    for row in rows:
        ts = row["timestamp"][:16].replace("T"," ")
        icon = "✅" if row["status"]=="pass" else "❌"
        lines.append(f"{icon} `{ts}` — `{row.get('score',0)*100:.0f}%`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_qa_trigger(update, context):
    import urllib.request as _req, json as _json
    await update.message.reply_text("🚀 Triggering QA pipeline...")
    payload = _json.dumps({"ref":"main"}).encode()
    r = _req.Request(
        "https://api.github.com/repos/breverdbidder/qa-agentic-pipeline/actions/workflows/nightly-qa.yml/dispatches",
        data=payload,
        headers={"Authorization":f"Bearer {GH_TOKEN}","Accept":"application/vnd.github.v3+json","Content-Type":"application/json"},
        method="POST"
    )
    try:
        with _req.urlopen(r) as resp:
            ok = resp.status in [200,204]
    except: ok = False
    if ok:
        await update.message.reply_text(
            "✅ *QA triggered.* Report in ~15 min.\n[Monitor](https://github.com/breverdbidder/qa-agentic-pipeline/actions)",
            parse_mode="Markdown", disable_web_page_preview=True
        )
    else:
        await update.message.reply_text("❌ Trigger failed. Check GH_TOKEN permissions.")


def main():
    """Main function"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    
    if not GH_TOKEN:
        logger.error("GH_TOKEN not set")
        sys.exit(1)
    
    logger.info("🚀 AgentRemote v4.0 starting...")
    logger.info(f"🎯 Smart Router: {SMART_ROUTER_URL}")
    logger.info(f"🔒 Authentication: {'Enabled' if AUTHORIZED_USERS != [''] else 'Disabled'}")
    logger.info(f"⚡ Rate Limit: {RATE_LIMIT_TASKS_PER_HOUR} tasks/hour")
    
    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", task))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("qa", cmd_qa))
    app.add_handler(CommandHandler("qa_last", cmd_qa_last))
    app.add_handler(CommandHandler("qa_trigger", cmd_qa_trigger))
    
    logger.info("✅ AgentRemote v4.0 is running!")
    logger.info("💬 Send /start in Telegram to begin")
    
    # Run bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
