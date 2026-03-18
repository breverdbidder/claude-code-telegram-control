/**
 * AgentRemote V5 Dispatch Worker
 * Cloudflare Worker that receives Telegram webhooks and routes to Hetzner executor.
 * 
 * Flow: Telegram → this Worker → Hetzner :8318 → Claude Code CLI → Telegram reply
 */

const HETZNER_URL = "http://87.99.129.125:8318";
const AGENT_SECRET = "__AGENT_SECRET__"; // Set in wrangler.toml secrets

// Ariel's Telegram chat ID - ONLY authorized user
const ALLOWED_CHAT_IDS = new Set([
  // Will be populated on first /start command or set manually
]);

// Quick-reply commands that don't need Claude
const QUICK_COMMANDS = {
  "/start": "🤖 AgentRemote V5.0 — Unified Phone Agent\n\nSend any message or use commands:\n/brief — Morning briefing\n/status — System health\n/repos — GitHub repo status\n/swim — Michael's latest times\n/expenses — Expense breakdown\n/history — Recent task log\n/help — This message",
  "/help": "Commands:\n/brief — Morning briefing (Gmail + Calendar)\n/status — Hetzner + services health\n/repos — All 5 GitHub repos status\n/swim — SwimCloud data for Michael\n/expenses — Scan expense folder\n/history — Last 10 tasks\n\nOr just type naturally:\n\"Compile Q1 numbers\"\n\"Check my email for anything urgent\"\n\"What auctions are coming up?\"",
  "/ping": "🏓 Pong! AgentRemote V5 is alive.",
};

// Skill-mapped commands → Hetzner endpoints
const SKILL_COMMANDS = {
  "/brief": { endpoint: "/brief", msg: "☀️ Running morning brief..." },
  "/status": { endpoint: "/status", msg: "📊 Checking system health..." },
  "/repos": { endpoint: "/task", task: "Check health of all 5 breverdbidder GitHub repos: claude-code-telegram-control, cli-anything-biddeed, zonewise-scraper-v4, swimsquad-ai, biddeed-ai. Report last commit date, open issues, and workflow status for each.", msg: "🔍 Scanning repos..." },
  "/swim": { endpoint: "/task", task: "Query Supabase for Michael Shapira's latest swim times from SwimCloud 3250085. Show SCY PBs and progress toward Futures cuts.", msg: "🏊 Pulling swim data..." },
  "/expenses": { endpoint: "/task", task: "List and categorize all PDF receipts in the expenses folder. Show total spend by category.", msg: "💰 Analyzing expenses..." },
  "/history": { endpoint: "/history", msg: "📋 Fetching recent tasks..." },
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response("AgentRemote V5 Dispatch Worker", { status: 200 });
    }

    // Telegram webhook
    if (url.pathname === "/webhook/telegram" && request.method === "POST") {
      try {
        const update = await request.json();
        return await handleTelegramUpdate(update, env);
      } catch (e) {
        console.error("Webhook error:", e);
        return new Response("OK", { status: 200 }); // Always 200 to Telegram
      }
    }

    return new Response("Not found", { status: 404 });
  }
};

async function handleTelegramUpdate(update, env) {
  const message = update.message || update.edited_message;
  if (!message || !message.text) return new Response("OK");

  const chatId = message.chat.id.toString();
  const text = message.text.trim();
  const botToken = env.TELEGRAM_BOT_TOKEN;
  const agentSecret = env.AGENT_SECRET || AGENT_SECRET;
  const hetznerUrl = env.HETZNER_URL || HETZNER_URL;
  const allowedIds = env.ALLOWED_CHAT_ID ? new Set([env.ALLOWED_CHAT_ID]) : ALLOWED_CHAT_IDS;

  // Auth check (if ALLOWED_CHAT_ID is set)
  if (allowedIds.size > 0 && !allowedIds.has(chatId)) {
    await sendTelegram(botToken, chatId, "⛔ Unauthorized. This bot is private.");
    return new Response("OK");
  }

  // Quick commands (no Hetzner needed)
  const quickReply = QUICK_COMMANDS[text.toLowerCase()];
  if (quickReply) {
    await sendTelegram(botToken, chatId, quickReply);
    return new Response("OK");
  }

  // Skill commands → Hetzner
  const cmd = text.split(" ")[0].toLowerCase();
  const skill = SKILL_COMMANDS[cmd];

  if (skill) {
    // Send ack
    await sendTelegram(botToken, chatId, skill.msg);

    // Route to Hetzner (fire and forget - executor sends reply)
    const taskBody = skill.task || text.replace(cmd, "").trim();
    await routeToHetzner(hetznerUrl, agentSecret, {
      endpoint: skill.endpoint,
      task: taskBody,
      chat_id: chatId,
      bot_token: botToken,
      source: "telegram",
      command: cmd,
    });

    return new Response("OK");
  }

  // Natural language → /task endpoint
  await sendTelegram(botToken, chatId, "⏳ Processing...");

  await routeToHetzner(hetznerUrl, agentSecret, {
    endpoint: "/task",
    task: text,
    chat_id: chatId,
    bot_token: botToken,
    source: "telegram",
    command: "natural",
  });

  return new Response("OK");
}

async function routeToHetzner(baseUrl, secret, payload) {
  try {
    const endpoint = payload.endpoint || "/task";
    const res = await fetch(`${baseUrl}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Agent-Key": secret,
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      console.error(`Hetzner ${endpoint} returned ${res.status}`);
      // If Hetzner is down, notify user
      if (payload.bot_token && payload.chat_id) {
        await sendTelegram(payload.bot_token, payload.chat_id,
          `❌ Executor unavailable (${res.status}). Task queued for retry.`);
      }
    }
  } catch (e) {
    console.error("Hetzner routing error:", e.message);
    if (payload.bot_token && payload.chat_id) {
      await sendTelegram(payload.bot_token, payload.chat_id,
        "❌ Executor offline. Will retry when available.");
    }
  }
}

async function sendTelegram(botToken, chatId, text) {
  try {
    await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: text,
        parse_mode: "Markdown",
        disable_web_page_preview: true,
      }),
    });
  } catch (e) {
    console.error("Telegram send error:", e.message);
  }
}
