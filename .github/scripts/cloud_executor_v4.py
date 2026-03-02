#!/usr/bin/env python3
"""
AgentRemote Cloud Executor v4.0
Multi-phase execution using Claude tool_use API in GitHub Actions
Phases: ANALYZE → PLAN → IMPLEMENT → VERIFY → REPORT
Sends live progress updates to Telegram during execution.
"""

import os
import sys
import json
import subprocess
import requests
import time
from datetime import datetime
from anthropic import Anthropic

# ── Config ────────────────────────────────────────────────────
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
GH_TOKEN        = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
GREPTILE_KEY    = os.environ.get("GREPTILE_API_KEY", "")
BOT_TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID         = os.environ.get("CHAT_ID", "")
TASK            = os.environ.get("TASK_DESCRIPTION", "No task provided")
GITHUB_OUTPUT   = os.environ.get("GITHUB_OUTPUT", "/dev/stdout")
GITHUB_REPO     = os.environ.get("GITHUB_REPOSITORY", "breverdbidder/claude-code-telegram-control")
RUN_URL         = f"https://github.com/{GITHUB_REPO}/actions"
MODEL           = "claude-sonnet-4-20250514"

client = Anthropic(api_key=ANTHROPIC_KEY)

# ── Telegram ──────────────────────────────────────────────────
def tg(msg: str, parse_mode: str = "Markdown") -> bool:
    """Send progress update to Telegram. Never raises — fire and forget."""
    if not BOT_TOKEN or not CHAT_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": parse_mode,
                  "disable_web_page_preview": True},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False

# ── Bash executor ─────────────────────────────────────────────
def run(cmd: str, cwd: str = ".") -> tuple[int, str, str]:
    """Run a shell command, return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=300
    )
    return result.returncode, result.stdout[:8000], result.stderr[:2000]

def run_safe(cmd: str, cwd: str = ".") -> str:
    """Run command, return stdout+stderr combined. Never raises."""
    try:
        rc, out, err = run(cmd, cwd)
        combined = out + ("\n" + err if err else "")
        return f"[exit {rc}]\n{combined}" if rc != 0 else combined
    except subprocess.TimeoutExpired:
        return "[TIMEOUT after 300s]"
    except Exception as e:
        return f"[ERROR: {e}]"

# ── Tools definition for Claude ───────────────────────────────
TOOLS = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command in the GitHub Actions environment. "
            "Working dir is repo root. Git, pip, npm, curl all available. "
            "Use for: reading files, writing files, running tests, git operations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
                "cwd": {"type": "string", "description": "Working directory (default: .)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates or overwrites).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    },
    {
        "name": "greptile_audit",
        "description": "Run a Greptile code audit on the repo and return the score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Audit question or focus area"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "report_progress",
        "description": "Send a progress update to the user via Telegram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phase": {"type": "string", "enum": ["ANALYZE", "PLAN", "IMPLEMENT", "VERIFY", "REPORT"]},
                "message": {"type": "string"}
            },
            "required": ["phase", "message"]
        }
    }
]

# ── Tool handlers ─────────────────────────────────────────────
def handle_tool(name: str, inp: dict) -> str:
    if name == "bash":
        cmd = inp["command"]
        cwd = inp.get("cwd", ".")
        print(f"  💻 bash: {cmd[:100]}")
        result = run_safe(cmd, cwd)
        print(f"     → {result[:200]}")
        return result

    elif name == "write_file":
        path = inp["path"]
        content = inp["content"]
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print(f"  📝 wrote: {path} ({len(content)} chars)")
        return f"Written: {path}"

    elif name == "read_file":
        path = inp["path"]
        try:
            with open(path) as f:
                content = f.read(10000)
            return content
        except FileNotFoundError:
            return f"File not found: {path}"

    elif name == "greptile_audit":
        if not GREPTILE_KEY:
            return "GREPTILE_API_KEY not set — skipping audit"
        query = inp["query"]
        try:
            r = requests.post(
                "https://api.greptile.com/v2/query",
                headers={"Authorization": f"Bearer {GREPTILE_KEY}",
                         "X-Github-Token": GH_TOKEN},
                json={
                    "messages": [{"id": "1", "content": query, "role": "user"}],
                    "repositories": [{"remote": "github", "repository": GITHUB_REPO, "branch": "main"}]
                },
                timeout=60
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("message", str(data))[:2000]
            return f"Greptile error {r.status_code}: {r.text[:500]}"
        except Exception as e:
            return f"Greptile failed: {e}"

    elif name == "report_progress":
        phase = inp["phase"]
        msg = inp["message"]
        phase_icons = {
            "ANALYZE": "🔍", "PLAN": "📋",
            "IMPLEMENT": "⚙️", "VERIFY": "✅", "REPORT": "📊"
        }
        icon = phase_icons.get(phase, "▶️")
        tg(f"{icon} *{phase}*\n{msg}\n\n[View run]({RUN_URL})")
        print(f"  📱 [{phase}] {msg[:100]}")
        return "Progress sent"

    return f"Unknown tool: {name}"

# ── Main agentic loop ─────────────────────────────────────────
def execute():
    print(f"\n{'═'*55}")
    print(f"  AgentRemote Cloud Executor v4.0")
    print(f"  Task: {TASK[:100]}")
    print(f"  Model: {MODEL}")
    print(f"  Started: {datetime.utcnow().isoformat()} UTC")
    print(f"{'═'*55}\n")

    # Notify start
    tg(
        f"🚀 *AgentRemote Cloud Started*\n\n"
        f"📋 Task: `{TASK[:200]}`\n"
        f"🤖 Model: Claude Sonnet 4.5\n"
        f"⏱️ Timeout: 30 min\n\n"
        f"[Monitor]({RUN_URL})"
    )

    # Get repo file list
    _, file_list, _ = run("find . -type f -not -path './.git/*' -not -path './node_modules/*' | head -80")

    system = f"""You are AgentRemote v4.0 — an autonomous agent running in GitHub Actions.

TASK: {TASK}

ENVIRONMENT:
- GitHub Actions, Ubuntu latest, Python 3.11
- Repo: {GITHUB_REPO}
- Tools: git, pip, bash, all standard Unix tools
- All secrets available via environment

REPOSITORY FILES:
{file_list}

EXECUTION PROTOCOL:
1. Call report_progress(phase=ANALYZE) first with your analysis
2. Call report_progress(phase=PLAN) with step-by-step plan
3. Use bash/write_file/read_file to implement
4. Call report_progress(phase=IMPLEMENT) after each major step
5. Run tests/verification with bash
6. Call greptile_audit if code quality check needed
7. Call report_progress(phase=VERIFY) with test results
8. Git commit and push changes
9. Call report_progress(phase=REPORT) with final summary

RULES:
- Make real changes — read existing files before modifying
- Run git diff before committing
- Never echo placeholder code — write actual working implementation
- If a step fails, diagnose and retry (up to 3 times)
- Send progress updates so the user knows what's happening
"""

    messages = [{"role": "user", "content": f"Execute this task completely: {TASK}"}]
    has_changes = False
    result_summary = "No result"
    iterations = 0
    MAX_ITER = 25

    while iterations < MAX_ITER:
        iterations += 1
        print(f"\n[Iteration {iterations}/{MAX_ITER}]")

        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=system,
            tools=TOOLS,
            messages=messages
        )

        # Accumulate assistant message
        messages.append({"role": "assistant", "content": response.content})

        # Check stop condition
        if response.stop_reason == "end_turn":
            # Extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    result_summary = block.text
                    print(f"\n✅ Agent completed:\n{result_summary[:500]}")
            break

        if response.stop_reason != "tool_use":
            print(f"Unexpected stop_reason: {response.stop_reason}")
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            tool_input = block.input
            print(f"\n  🔧 Tool: {tool_name}")

            tool_output = handle_tool(tool_name, tool_input)

            # Track if files were changed
            if tool_name in ("bash", "write_file") and "git" not in str(tool_input):
                has_changes = True

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(tool_output)
            })

        messages.append({"role": "user", "content": tool_results})

    # Git commit if changes made
    rc, diff, _ = run("git diff --stat HEAD")
    if diff.strip():
        has_changes = True
        run("git config user.name 'AgentRemote Bot'")
        run("git config user.email 'agent@biddeed.ai'")
        run("git add -A")
        rc, commit_out, _ = run(f"git commit -m 'AgentRemote: {TASK[:60]}'")
        print(f"Git commit: {commit_out}")

        rc, push_out, push_err = run("git push origin HEAD")
        if rc == 0:
            print(f"✅ Pushed: {push_out}")
        else:
            print(f"⚠️  Push failed: {push_err}")

    # Write GitHub outputs
    with open(GITHUB_OUTPUT, "a") as f:
        safe_summary = result_summary.replace("\n", "\\n").replace('"', '\\"')[:2000]
        f.write(f"result<<EOF\n{result_summary[:3000]}\nEOF\n")
        f.write(f"has_changes={'true' if has_changes else 'false'}\n")
        f.write(f"iterations={iterations}\n")

    # Final Telegram notification
    status_icon = "✅" if iterations < MAX_ITER else "⚠️"
    tg(
        f"{status_icon} *AgentRemote Complete*\n\n"
        f"📋 Task: `{TASK[:150]}`\n"
        f"🔄 Iterations: {iterations}\n"
        f"💾 Changes: {'Yes — committed & pushed' if has_changes else 'None'}\n\n"
        f"*Summary:*\n{result_summary[:800]}\n\n"
        f"[View run]({RUN_URL})"
    )

    print(f"\n{'═'*55}")
    print(f"  DONE — {iterations} iterations, changes={has_changes}")
    print(f"{'═'*55}")
    return 0


if __name__ == "__main__":
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)
    sys.exit(execute())
