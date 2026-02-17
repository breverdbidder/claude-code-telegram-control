#!/usr/bin/env python3
"""
AgentRemote MCP Server v1.0
Gives Claude Code tools to interact with Telegram via AgentRemote.

Tools provided:
  - telegram_send: Send a message to the user's Telegram
  - telegram_ask: Ask user a question with inline keyboard buttons
  - telegram_send_file: Send a file to Telegram
  - telegram_notify: Send a styled notification (success/error/warning)

Usage in CLAUDE.md:
  Add to MCP servers config:
    {
      "mcpServers": {
        "agentremote": {
          "command": "python3",
          "args": ["path/to/mcp_server.py"],
          "env": {
            "TELEGRAM_BOT_TOKEN": "your-bot-token",
            "TELEGRAM_CHAT_ID": "your-chat-id"
          }
        }
      }
    }
"""

import os
import sys
import json
import time
import logging
import asyncio
from typing import Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Telegram config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
POLL_TIMEOUT = int(os.getenv("MCP_POLL_TIMEOUT", "120"))  # seconds to wait for user response

# Track callback responses
pending_callbacks = {}  # {callback_id: asyncio.Event}
callback_responses = {}  # {callback_id: selected_option}


async def telegram_api(method: str, payload: dict) -> dict:
    """Call Telegram Bot API"""
    import urllib.request
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Telegram API error: {e}")
        return {"ok": False, "description": str(e)}


async def send_message(text: str, parse_mode: str = "Markdown") -> dict:
    """Send a plain text message"""
    return await telegram_api("sendMessage", {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    })


async def send_with_keyboard(text: str, options: list[str], callback_prefix: str = "mcp") -> dict:
    """Send message with inline keyboard buttons"""
    callback_id = f"{callback_prefix}_{int(time.time())}"
    keyboard = []
    row = []
    for i, option in enumerate(options):
        row.append({
            "text": option,
            "callback_data": f"{callback_id}:{i}:{option[:60]}"
        })
        if len(row) >= 2:  # 2 buttons per row
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    result = await telegram_api("sendMessage", {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard}
    })
    return {**result, "callback_id": callback_id}


async def poll_for_callback(callback_id: str, timeout: int = POLL_TIMEOUT) -> str | None:
    """
    Poll Telegram getUpdates for callback_query matching our callback_id.
    Returns the selected option text, or None if timeout.
    """
    import urllib.request
    start = time.time()
    last_update_id = 0

    while time.time() - start < timeout:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"timeout": 5, "allowed_updates": '["callback_query"]'}
        if last_update_id:
            params["offset"] = last_update_id + 1

        try:
            param_str = "&".join(f"{k}={v}" for k, v in params.items())
            req_url = f"{url}?{param_str}"
            with urllib.request.urlopen(req_url, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    cb = update.get("callback_query", {})
                    cb_data = cb.get("data", "")
                    if cb_data.startswith(callback_id):
                        # Parse: callback_id:index:option_text
                        parts = cb_data.split(":", 2)
                        selected = parts[2] if len(parts) > 2 else "unknown"

                        # Answer callback to remove loading indicator
                        await telegram_api("answerCallbackQuery", {
                            "callback_query_id": cb["id"],
                            "text": f"Selected: {selected}"
                        })

                        return selected
        except Exception as e:
            logger.debug(f"Poll error (retrying): {e}")

        await asyncio.sleep(1)

    return None


# ============================================================
# MCP Protocol Implementation (JSON-RPC over stdio)
# ============================================================

TOOLS = [
    {
        "name": "telegram_send",
        "description": "Send a message to the user via Telegram. Use for progress updates, results, or any communication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message text (Markdown supported)"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "telegram_ask",
        "description": "Ask the user a question with clickable button options in Telegram. Returns the selected option. Use when you need the user to make a choice.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to ask the user"
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of options (2-8 choices). Will appear as tappable buttons.",
                    "minItems": 2,
                    "maxItems": 8
                },
                "timeout": {
                    "type": "integer",
                    "description": "Seconds to wait for response (default: 120)",
                    "default": 120
                }
            },
            "required": ["question", "options"]
        }
    },
    {
        "name": "telegram_notify",
        "description": "Send a styled notification to Telegram. Use for task completion alerts, errors, or warnings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Notification title"
                },
                "body": {
                    "type": "string",
                    "description": "Notification body text"
                },
                "level": {
                    "type": "string",
                    "enum": ["success", "error", "warning", "info"],
                    "description": "Notification level",
                    "default": "info"
                }
            },
            "required": ["title", "body"]
        }
    },
    {
        "name": "telegram_send_file",
        "description": "Send a file to the user via Telegram.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to send"
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption for the file",
                    "default": ""
                }
            },
            "required": ["file_path"]
        }
    }
]


async def handle_tool_call(name: str, arguments: dict) -> dict:
    """Execute a tool call and return the result"""

    if name == "telegram_send":
        result = await send_message(arguments["message"])
        if result.get("ok"):
            return {"content": [{"type": "text", "text": "✅ Message sent to Telegram"}]}
        return {"content": [{"type": "text", "text": f"❌ Failed: {result.get('description')}"}], "isError": True}

    elif name == "telegram_ask":
        question = arguments["question"]
        options = arguments["options"]
        timeout = arguments.get("timeout", POLL_TIMEOUT)

        result = await send_with_keyboard(f"❓ *{question}*", options)
        if not result.get("ok"):
            return {"content": [{"type": "text", "text": f"❌ Failed to send: {result.get('description')}"}], "isError": True}

        callback_id = result["callback_id"]
        selected = await poll_for_callback(callback_id, timeout)

        if selected:
            return {"content": [{"type": "text", "text": f"User selected: {selected}"}]}
        return {"content": [{"type": "text", "text": f"⏰ No response within {timeout} seconds"}]}

    elif name == "telegram_notify":
        level = arguments.get("level", "info")
        icons = {"success": "✅", "error": "🔴", "warning": "⚠️", "info": "ℹ️"}
        icon = icons.get(level, "ℹ️")
        msg = f"{icon} *{arguments['title']}*\n\n{arguments['body']}"
        result = await send_message(msg)
        if result.get("ok"):
            return {"content": [{"type": "text", "text": f"✅ {level.title()} notification sent"}]}
        return {"content": [{"type": "text", "text": f"❌ Failed: {result.get('description')}"}], "isError": True}

    elif name == "telegram_send_file":
        file_path = arguments["file_path"]
        caption = arguments.get("caption", "")
        if not os.path.exists(file_path):
            return {"content": [{"type": "text", "text": f"❌ File not found: {file_path}"}], "isError": True}

        import urllib.request
        import mimetypes
        boundary = "----AgentRemoteMCP"
        filename = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        with open(file_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n{CHAT_ID}\r\n"
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n"
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
            if result.get("ok"):
                return {"content": [{"type": "text", "text": f"✅ File sent: {filename}"}]}
            return {"content": [{"type": "text", "text": f"❌ Failed: {result.get('description')}"}], "isError": True}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"❌ Upload error: {e}"}], "isError": True}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}


async def run_mcp_server():
    """Run MCP server over stdio (JSON-RPC)"""
    logger.info("🚀 AgentRemote MCP Server v1.0 starting...")

    if not BOT_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
        sys.exit(1)

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    async def write_response(response: dict):
        line = json.dumps(response) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()

    while True:
        try:
            line = await reader.readline()
            if not line:
                break

            request = json.loads(line.decode().strip())
            method = request.get("method", "")
            req_id = request.get("id")

            if method == "initialize":
                await write_response({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "agentremote-mcp",
                            "version": "1.0.0"
                        }
                    }
                })

            elif method == "notifications/initialized":
                pass  # No response needed

            elif method == "tools/list":
                await write_response({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"tools": TOOLS}
                })

            elif method == "tools/call":
                tool_name = request["params"]["name"]
                tool_args = request["params"].get("arguments", {})
                result = await handle_tool_call(tool_name, tool_args)
                await write_response({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": result
                })

            else:
                await write_response({
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })

        except json.JSONDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error: {e}")
            if req_id:
                await write_response({
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                })


if __name__ == "__main__":
    asyncio.run(run_mcp_server())
