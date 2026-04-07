#!/bin/bash
# Telegram Nachricht senden - fuer Claude Code Orchestrator
# Usage: bash scripts/telegram-send.sh "Deine Nachricht"
source "$(dirname "$0")/../.env.telegram"
MSG="$1"
if [ -z "$MSG" ]; then echo "Usage: bash scripts/telegram-send.sh \"message\""; exit 1; fi
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\": ${TELEGRAM_CHAT_ID}, \"text\": $(echo "$MSG" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))")}" > /dev/null
echo "Telegram: sent"
