# CLAUDE.md - AgentRemote v4.1

## Overview
AgentRemote is BidDeed.AI's Telegram bot for remote Claude Code control. Dual-mode: LOCAL (Claude Code on desktop) + CLOUD (GitHub Actions serverless).

## MCP Server: AgentRemote Telegram Tools

When this MCP server is active, you have 4 Telegram tools. **USE THEM** during autonomous sessions.

### Required Behavior During Autonomous Sessions

1. **Session Start**: Call `telegram_notify` with level="info" to announce session start
2. **Every 30 minutes**: Call `telegram_send` with progress summary
3. **Decisions needed**: Call `telegram_ask` with options instead of blocking
4. **Files completed**: Call `telegram_send_file` for deliverables
5. **Session End**: Call `telegram_notify` with level="success" summarizing work done
6. **Errors**: Call `telegram_notify` with level="error" immediately, don't wait

### Tool Reference

```
telegram_send(message)           → Send progress update (Markdown OK)
telegram_ask(question, options)  → Ask user with buttons, returns selection
telegram_notify(title, body, level) → Styled alert: success/error/warning/info
telegram_send_file(file_path, caption) → Send a file to Telegram
```

### Example Autonomous Session Flow

```
[Session starts]
→ telegram_notify("🚀 Session Started", "Working on: Fix BECA scraper timeout\nEst: 2 hours", "info")

[30 min checkpoint]
→ telegram_send("📊 *Progress:* Identified 3 timeout sources in beca_scraper.py. Fixing connection pooling now.")

[Decision point]
→ telegram_ask("Connection pool size?", ["10 connections", "25 connections", "50 connections"])
→ User taps "25 connections" → continues

[File ready]
→ telegram_send_file("/path/to/report.pdf", "Audit report for BECA scraper fixes")

[Session complete]
→ telegram_notify("✅ Session Complete", "Fixed 3 timeout issues\nTests: 14/14 passing\nDeployed to main", "success")
```

### Shabbat Rules
- Do NOT send notifications between Friday sunset and Saturday night (havdalah)
- Queue non-urgent messages for after Shabbat
- Emergency errors (data loss, security): send immediately regardless

## Webhook Notifications

The `webhook_notify.yml` workflow sends Telegram alerts for:
- Issues: opened, closed, labeled
- PRs: opened, merged, review requested
- CI: workflow pass/fail
- Pushes: to main branch

These are automatic. No Claude Code action needed.

## File Structure
```
├── bot_v3.py                          # Original dual-mode bot
├── bot_v4.py                          # Enhanced: auth, rate limiting, smart router
├── mcp_server.py                      # MCP server (4 Telegram tools)
├── setup_mcp.sh                       # Bootstrap: syncs mcp_server.py to local
├── .github/workflows/
│   ├── agent-executor.yml             # Cloud execution workflow
│   └── webhook_notify.yml             # GitHub event → Telegram notifications
├── .github/scripts/
│   ├── cloud_executor.py              # Claude API task executor
│   └── send_notification.py           # Telegram notification sender
└── .claude/settings.local.json        # Claude Code config (MCP + permissions)
```

## Zero Human-in-the-Loop Rules
- All Bash, Read, Write, WebFetch pre-approved
- MCP server handles Telegram communication
- Use `telegram_ask` instead of blocking for decisions
- Auto-approve all file operations
- Commit frequently, push to branches
