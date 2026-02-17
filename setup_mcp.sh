#!/usr/bin/env bash
# AgentRemote MCP Bootstrap v1.0
# Syncs latest mcp_server.py from GitHub and verifies Claude Code config
# Run once, or after any mcp_server.py update on GitHub
#
# Usage: bash setup_mcp.sh
# Zero human-in-the-loop: safe to run from Claude Code sessions

set -e

REPO="breverdbidder/claude-code-telegram-control"
MCP_LOCAL_DIR="$HOME/claude-telegram"
MCP_FILE="mcp_server.py"
MCP_PATH="$MCP_LOCAL_DIR/$MCP_FILE"
GITHUB_RAW="https://raw.githubusercontent.com/$REPO/main/$MCP_FILE"

echo "🚀 AgentRemote MCP Bootstrap v1.0"
echo "================================="

# Step 1: Create directory
mkdir -p "$MCP_LOCAL_DIR"
echo "✅ Directory: $MCP_LOCAL_DIR"

# Step 2: Download latest mcp_server.py from GitHub
echo "📥 Downloading latest mcp_server.py..."
if command -v curl &> /dev/null; then
    curl -sL "$GITHUB_RAW" -o "$MCP_PATH"
elif command -v wget &> /dev/null; then
    wget -q "$GITHUB_RAW" -O "$MCP_PATH"
else
    echo "❌ Neither curl nor wget found"
    exit 1
fi
echo "✅ Downloaded: $MCP_PATH"

# Step 3: Verify it's valid Python
python3 -c "import ast; ast.parse(open('$MCP_PATH').read())" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Python syntax valid"
else
    echo "❌ Python syntax error in mcp_server.py"
    exit 1
fi

# Step 4: Check environment variables
echo ""
echo "📋 Environment Check:"
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "  ✅ TELEGRAM_BOT_TOKEN is set"
else
    echo "  ⚠️  TELEGRAM_BOT_TOKEN not set in shell (OK if set in settings.local.json)"
fi
if [ -n "$TELEGRAM_CHAT_ID" ]; then
    echo "  ✅ TELEGRAM_CHAT_ID is set"
else
    echo "  ⚠️  TELEGRAM_CHAT_ID not set in shell (OK if set in settings.local.json)"
fi

# Step 5: Verify settings.local.json references in nearby repos
echo ""
echo "📋 Claude Code Config Check:"
REPOS_TO_CHECK=(
    "$HOME/zonewise-agents"
    "$HOME/zonewise-desktop"
    "$HOME/zonewise-modal"
    "$HOME/claude-code-telegram-control"
    "$HOME/brevard-bidder-scraper"
)

for REPO_DIR in "${REPOS_TO_CHECK[@]}"; do
    SETTINGS="$REPO_DIR/.claude/settings.local.json"
    if [ -f "$SETTINGS" ]; then
        if grep -q "agentremote" "$SETTINGS" 2>/dev/null; then
            echo "  ✅ $REPO_DIR → MCP configured"
        else
            echo "  ⚠️  $REPO_DIR → MCP not in settings.local.json"
        fi
    else
        DIRNAME=$(basename "$REPO_DIR")
        echo "  ⏭️  $DIRNAME → not cloned locally"
    fi
done

# Step 6: Show MCP tools available
echo ""
echo "🔧 MCP Tools Available:"
echo "  • telegram_send    - Send messages to Telegram"
echo "  • telegram_ask     - Ask with inline keyboard (waits for tap)"
echo "  • telegram_notify  - Styled alerts (success/error/warning/info)"
echo "  • telegram_send_file - Send files to Telegram"

echo ""
echo "✅ AgentRemote MCP Bootstrap complete!"
echo ""
echo "💡 To test: claude --mcp-server agentremote"
echo "   Then ask Claude Code to send you a Telegram message."
