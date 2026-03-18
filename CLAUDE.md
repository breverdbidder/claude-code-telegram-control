# AgentRemote V5.0 — Unified Phone-to-Cloud Agent

## Architecture
Phone (Telegram/Co-work/PWA) → Cloudflare Worker → Hetzner Executor → Claude CLI (Max plan, $0)

## CRITICAL RULES
1. **ZERO PAID API** — All Claude execution via `claude` CLI on Max plan. NEVER use `anthropic.Client()` or `ANTHROPIC_API_KEY`.
2. **Hetzner is the execution layer** — GitHub Actions is for CI/CD only, NOT compute.
3. **Telegram auth** — Only Ariel's chat_id is allowed. Reject all others.
4. **Supabase is the state store** — All tasks logged to `agent_tasks` table.
5. **Cost: $0 incremental** — All infrastructure already paid for.

## Components
| Component | Location | Purpose |
|-----------|----------|---------|
| Cloudflare Worker | `worker/index.js` | Telegram webhook → route to Hetzner |
| Hetzner Executor | `executor/executor.py` | HTTP server + Claude CLI bridge |
| Supabase Migration | `migrations/001_agent_tasks.sql` | Unified task tracking |
| Co-work Skills | `skills/` | Desktop skills for Claude Co-work |
| GHA Deploy | `.github/workflows/deploy-executor.yml` | Auto-deploy executor |

## Endpoints (Hetzner :8318)
- `POST /task` — Execute natural language task via Claude CLI
- `POST /brief` — Morning briefing (Gmail + Calendar + GitHub)
- `GET /status` — Current task + queue depth
- `GET /health` — Container health
- `GET /history?n=10` — Recent task history

## Telegram Commands
`/start` `/help` `/ping` — Quick replies (no Hetzner)
`/brief` `/status` `/repos` `/swim` `/expenses` `/history` — Routed to Hetzner
Free text — Natural language → `/task` endpoint

## Secrets Required
| Secret | Where | Purpose |
|--------|-------|---------|
| `AGENT_SECRET` | Worker + Hetzner .env | Shared auth key |
| `SUPABASE_SERVICE_KEY` | Hetzner .env | DB writes |
| `TELEGRAM_BOT_TOKEN` | Worker + Hetzner .env | Send messages |
| `TELEGRAM_CHAT_ID` | GHA secrets | Deploy notifications |
| `HETZNER_SSH_KEY` | GHA secrets | SSH deploy |
| `ALLOWED_CHAT_ID` | Worker secret | Ariel's Telegram ID |

## Brand
Navy #1E3A5F | Orange #F59E0B | Font: Inter/Arial
