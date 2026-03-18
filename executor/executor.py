#!/usr/bin/env python3
"""
AgentRemote V5 Executor
HTTP server running on Hetzner that executes tasks via Claude Code CLI (Max plan).
NO paid API calls. ALL execution through `claude` CLI authenticated on Max plan.

Container: agentremote-executor on 127.0.0.1:8318
"""

import asyncio
import json
import os
import subprocess
import time
import traceback
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import urlparse, parse_qs

import requests

# ── Config ────────────────────────────────────────────────────
PORT = int(os.getenv("EXECUTOR_PORT", "8318"))
AGENT_SECRET = os.getenv("AGENT_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
MAX_TASK_DURATION = int(os.getenv("MAX_TASK_DURATION", "300"))  # 5 min default
CLAUDE_CMD = os.getenv("CLAUDE_CMD", "claude")

# Task queue (simple in-memory, Supabase is the durable store)
task_queue = asyncio.Queue() if False else []  # Using list for threading
current_task = None
task_history = []
start_time = time.time()


# ── Telegram Helper ───────────────────────────────────────────
def tg_send(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
    """Send a message to Telegram. Fire and forget."""
    if not bot_token or not chat_id:
        return False
    try:
        # Escape problematic Markdown characters
        safe_text = text.replace("_", "\\_").replace("*", "\\*") if parse_mode == "Markdown" else text
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": safe_text[:4000],  # Telegram limit
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if r.status_code != 200:
            # Retry without parse mode if markdown fails
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000]},
                timeout=10,
            )
        return True
    except Exception as e:
        print(f"[TG] Send failed: {e}")
        return False


# ── Supabase Helper ───────────────────────────────────────────
def supabase_insert(table: str, data: dict) -> dict | None:
    """Insert a row into Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=data,
            timeout=10,
        )
        return r.json() if r.status_code in (200, 201) else None
    except Exception as e:
        print(f"[DB] Insert failed: {e}")
        return None


def supabase_update(table: str, id_val: str, data: dict) -> bool:
    """Update a row in Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id_val}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            },
            json=data,
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception:
        return False


# ── Claude Code CLI Executor ──────────────────────────────────
def execute_claude_task(task: str, timeout: int = MAX_TASK_DURATION) -> dict:
    """
    Execute a task using Claude Code CLI (Max plan, $0).
    Returns {success, output, duration_ms, error}
    """
    start = time.time()
    try:
        # Use claude --print for single-shot execution
        # --output-format text for clean output
        # --max-turns 25 for bounded execution
        result = subprocess.run(
            [
                CLAUDE_CMD,
                "--print",
                "--output-format", "text",
                "--max-turns", "25",
                "--verbose",
                task,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.expanduser("~"),
        )

        duration_ms = int((time.time() - start) * 1000)
        output = result.stdout.strip()
        error = result.stderr.strip() if result.returncode != 0 else ""

        return {
            "success": result.returncode == 0,
            "output": output[:50000],  # Cap at 50K chars
            "error": error[:5000],
            "duration_ms": duration_ms,
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Task timed out after {timeout}s",
            "duration_ms": int((time.time() - start) * 1000),
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "",
            "error": "Claude CLI not found. Is it installed and on PATH?",
            "duration_ms": 0,
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
            "exit_code": -1,
        }


# ── Task Processing (async in background thread) ─────────────
def process_task(payload: dict):
    """Process a task in background thread. Sends results to Telegram + Supabase."""
    global current_task
    current_task = payload

    task_text = payload.get("task", "")
    chat_id = payload.get("chat_id", "")
    bot_token = payload.get("bot_token", "")
    source = payload.get("source", "unknown")
    task_id = None

    # Log to Supabase
    db_row = supabase_insert("agent_tasks", {
        "source": source,
        "task": task_text[:10000],
        "status": "processing",
        "chat_id": chat_id,
        "metadata": json.dumps({"command": payload.get("command", ""), "started_at": datetime.now(timezone.utc).isoformat()}),
    })
    if db_row and isinstance(db_row, list) and len(db_row) > 0:
        task_id = db_row[0].get("id")

    # Execute via Claude CLI
    result = execute_claude_task(task_text)

    # Update Supabase
    if task_id:
        supabase_update("agent_tasks", task_id, {
            "status": "completed" if result["success"] else "failed",
            "result": result["output"] or result["error"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": json.dumps({
                "command": payload.get("command", ""),
                "duration_ms": result["duration_ms"],
                "exit_code": result["exit_code"],
            }),
        })

    # Send result to Telegram
    if result["success"] and result["output"]:
        emoji = "✅"
        reply = result["output"]
        if len(reply) > 3500:
            reply = reply[:3500] + "\n\n... (truncated, full result in Supabase)"
        tg_send(bot_token, chat_id, f"{emoji} Done ({result['duration_ms']}ms)\n\n{reply}", parse_mode="")
    else:
        error_msg = result["error"] or "Unknown error"
        tg_send(bot_token, chat_id, f"❌ Failed ({result['duration_ms']}ms)\n\n{error_msg}", parse_mode="")

    # Track history
    task_history.append({
        "task": task_text[:100],
        "success": result["success"],
        "duration_ms": result["duration_ms"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(task_history) > 50:
        task_history.pop(0)

    current_task = None


# ── HTTP Request Handler ──────────────────────────────────────
class AgentHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}" if args else "")

    def _send(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _auth_check(self) -> bool:
        if not AGENT_SECRET:
            return True  # No secret configured = open (dev mode)
        key = self.headers.get("X-Agent-Key", "")
        if key != AGENT_SECRET:
            self._send(401, {"error": "Unauthorized"})
            return False
        return True

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/health":
            self._send(200, {
                "service": "agentremote-executor",
                "version": "5.0.0",
                "status": "healthy",
                "uptime_s": int(time.time() - start_time),
                "current_task": current_task.get("task", "")[:80] if current_task else None,
                "tasks_completed": len(task_history),
            })
            return

        if parsed.path == "/status":
            if not self._auth_check():
                return
            self._send(200, {
                "status": "busy" if current_task else "idle",
                "current_task": current_task.get("task", "")[:200] if current_task else None,
                "queue_depth": 0,
                "recent_tasks": task_history[-5:],
                "uptime_s": int(time.time() - start_time),
            })
            return

        if parsed.path == "/history":
            if not self._auth_check():
                return
            params = parse_qs(parsed.query)
            n = min(int(params.get("n", ["10"])[0]), 50)
            self._send(200, {"tasks": task_history[-n:]})
            return

        self._send(404, {"error": "Not found"})

    def do_POST(self):
        if not self._auth_check():
            return

        parsed = urlparse(self.path)
        body = self._read_body()

        if parsed.path == "/task":
            task = body.get("task", "")
            if not task:
                self._send(400, {"error": "Missing 'task' field"})
                return

            if current_task:
                self._send(202, {"status": "queued", "message": "Another task is running. Queued."})
                # Queue for later
                Thread(target=lambda: (time.sleep(10), process_task(body)), daemon=True).start()
                return

            # Process in background
            Thread(target=process_task, args=(body,), daemon=True).start()
            self._send(202, {"status": "accepted", "message": "Task accepted, processing..."})
            return

        if parsed.path == "/brief":
            brief_task = (
                "Run the morning brief: "
                "1) Check Gmail for urgent/unread emails from the last 24 hours. "
                "2) Check Google Calendar for today's events. "
                "3) Check GitHub notifications for all breverdbidder repos. "
                "4) Summarize everything as a prioritized brief. "
                "Format as a clean text summary with priorities numbered."
            )
            body["task"] = brief_task
            body["command"] = "/brief"
            Thread(target=process_task, args=(body,), daemon=True).start()
            self._send(202, {"status": "accepted", "message": "Morning brief started..."})
            return

        self._send(404, {"error": "Not found"})


# ── Main ──────────────────────────────────────────────────────
def main():
    server = HTTPServer(("0.0.0.0", PORT), AgentHandler)
    print(f"🤖 AgentRemote V5 Executor running on port {PORT}")
    print(f"   Claude CLI: {CLAUDE_CMD}")
    print(f"   Max task duration: {MAX_TASK_DURATION}s")
    print(f"   Supabase: {'configured' if SUPABASE_KEY else 'NOT configured'}")
    print(f"   Auth: {'enabled' if AGENT_SECRET else 'OPEN (dev mode)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
