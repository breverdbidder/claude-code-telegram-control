# AgentRemote v3.0

🚀 Dual-mode cloud execution system for mobile AI development automation.

## Features

- ☁️ **Cloud execution** via GitHub Actions
- 📱 **Mobile-first** Telegram interface  
- 🖥️ **Desktop compatible** - use from anywhere
- 🔄 **Auto-detection** of execution mode
- 24/7 **Always available**
- ⚡ **Serverless** architecture

## Quick Start

### 1. Deploy to Render.com (Recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

**Environment Variables Required:**
- `TELEGRAM_BOT_TOKEN` - Get from @BotFather
- `GH_TOKEN` - GitHub Personal Access Token

### 2. Configure GitHub Secrets

Go to repository Settings → Secrets → Actions:

Required secrets:
- `ANTHROPIC_API_KEY` - Claude API key
- `GREPTILE_API_KEY` - Greptile API key  
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `GH_TOKEN` - GitHub PAT with repo + workflow scopes

### 3. Test in Telegram

Send to your bot:
```
/start
/cloud
/task Create a test file named hello.txt
```

## Commands

- `/start` - Initialize bot
- `/task [description]` - Execute development task
- `/cloud` - Force cloud execution mode
- `/local` - Force local execution mode
- `/auto` - Auto-detect mode
- `/status` - Check system status

## Architecture

**Telegram Bot** → **GitHub Actions** → **Claude Sonnet 4** → **Results**

- Bot runs 24/7 on Render.com (free tier)
- Tasks execute via GitHub Actions (serverless)
- Claude Sonnet 4 performs actual work
- Results committed to repository
- Notifications sent back to Telegram

## Cost

- Render.com: **FREE** (750 hours/month)
- GitHub Actions: **FREE** (2,000 minutes/month)
- Anthropic API: **$6-20/month** (pay as you go)

**Total: $6-20/month vs $450/month alternatives**

## Example Tasks

```
/task Fix the bug in bot_v3.py line 45
/task Create a comprehensive README for the repository
/task Add error handling to cloud_executor.py
/task Refactor the notification system for better UX
/task Create unit tests for all core functions
```

## Security

- All secrets stored in GitHub Secrets (encrypted)
- No credentials in code or configuration
- Environment variables injected at runtime
- Tokens should be rotated regularly

## Support

Built with Claude AI - Zero human in the loop deployment ✅

Repository: https://github.com/breverdbidder/claude-code-telegram-control
