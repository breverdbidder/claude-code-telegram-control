# AgentRemote v4.1 - MCP Server + GitHub Webhooks

## New in v4.1

### 🔌 MCP Server (`mcp_server.py`)
Gives Claude Code 4 Telegram tools during autonomous sessions:

| Tool | Description |
|------|-------------|
| `telegram_send` | Send progress updates to your phone |
| `telegram_ask` | Ask questions with inline keyboard buttons, waits for tap |
| `telegram_notify` | Styled alerts (success/error/warning/info) |
| `telegram_send_file` | Send files directly to Telegram |

#### Setup in `.claude/CLAUDE.md`:
```json
{
  "mcpServers": {
    "agentremote": {
      "command": "python3",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "your-bot-token",
        "TELEGRAM_CHAT_ID": "your-chat-id"
      }
    }
  }
}
```

### 📡 GitHub Webhook Notifications (`.github/workflows/webhook_notify.yml`)
Sends Telegram alerts for repo events:

| Event | Notification |
|-------|-------------|
| New Issue | 🆕 Title, author, labels |
| Issue Closed | ✅ Title, author |
| New PR | 🔀 Title, author |
| PR Merged | 🎉 Title, author |
| Review Requested | 👀 PR title, reviewer |
| CI Failed | 🔴 Workflow name, link |
| CI Passed | ✅ Workflow name, link |
| Push to main | 📦 Commit message, author |

#### Required Secret:
Add `TELEGRAM_CHAT_ID` to GitHub Secrets (your Telegram user/chat ID).

Already configured: `TELEGRAM_BOT_TOKEN`

#### Test:
Go to Actions → "AgentRemote Webhook → Telegram" → Run workflow → Enter test message.

---

## Existing Features (v3.0/v4.0)
- `/task` - Execute dev tasks via cloud (GitHub Actions) or local (Claude Code)
- `/cloud` `/local` `/auto` - Mode switching
- `/status` `/queue` `/history` `/stats` - Monitoring
- Smart Router integration
- Auth + rate limiting
- Dual-mode: LOCAL + CLOUD execution

## Secrets Required (5 total)
| Secret | Purpose |
|--------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot API token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (NEW) |
| `GH_TOKEN` | GitHub PAT for repo dispatch |
| `ANTHROPIC_API_KEY` | Claude API for cloud execution |
| `GREPTILE_API_KEY` | Code quality audits |
