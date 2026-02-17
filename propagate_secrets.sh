#!/bin/bash
# propagate_secrets.sh - Copy Telegram secrets to all BidDeed.AI repos
# Run once: bash propagate_secrets.sh <BOT_TOKEN> <CHAT_ID>
# Or: bash propagate_secrets.sh (will prompt)

set -e

GH_TOKEN="${GH_TOKEN:-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}"
REPOS=(
  "breverdbidder/zonewise-agents"
  "breverdbidder/zonewise-desktop"
  "breverdbidder/zonewise-modal"
  "breverdbidder/brevard-bidder-scraper"
  "breverdbidder/claude-code-telegram-control"
)

BOT_TOKEN="${1}"
CHAT_ID="${2}"

if [ -z "$BOT_TOKEN" ]; then
  read -p "Enter TELEGRAM_BOT_TOKEN: " BOT_TOKEN
fi
if [ -z "$CHAT_ID" ]; then
  read -p "Enter TELEGRAM_CHAT_ID: " CHAT_ID
fi

if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "❌ Both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required"
  exit 1
fi

pip install pynacl -q 2>/dev/null

for REPO in "${REPOS[@]}"; do
  python3 -c "
import json, urllib.request, base64, sys
from nacl import encoding, public

token = '$GH_TOKEN'
repo = '$REPO'
secrets = {'TELEGRAM_BOT_TOKEN': '$BOT_TOKEN', 'TELEGRAM_CHAT_ID': '$CHAT_ID'}

# Get public key
req = urllib.request.Request(
    f'https://api.github.com/repos/{repo}/actions/secrets/public-key',
    headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json'}
)
with urllib.request.urlopen(req) as resp:
    key_data = json.loads(resp.read().decode())

pk = public.PublicKey(key_data['key'].encode(), encoding.Base64Encoder())
box = public.SealedBox(pk)

for name, value in secrets.items():
    encrypted = base64.b64encode(box.encrypt(value.encode())).decode()
    payload = json.dumps({'encrypted_value': encrypted, 'key_id': key_data['key_id']}).encode()
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/actions/secrets/{name}',
        data=payload,
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'},
        method='PUT'
    )
    with urllib.request.urlopen(req) as resp:
        status = '✅' if resp.status in [201, 204] else '❌'
        print(f'{status} {repo}: {name}')
" 2>/dev/null
done

echo ""
echo "🎉 All secrets propagated!"
