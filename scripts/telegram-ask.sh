#!/bin/bash
# Telegram Approval Request mit Inline-Buttons
# Usage: bash scripts/telegram-ask.sh "Frage" [request_id]
# Wartet auf Antwort von Jens und gibt JA/NEIN/CANCEL zurueck

set -e
source "$(dirname "$0")/../.env.telegram"

QUESTION="$1"
REQ_ID="${2:-req_$(date +%s)_$$}"

if [ -z "$QUESTION" ]; then
  echo "Usage: $0 <frage> [request_id]"
  exit 1
fi

# Inline-Keyboard mit Buttons
KEYBOARD=$(cat << JSONEOF
{
  "inline_keyboard": [
    [
      {"text": "JA - Erlauben", "callback_data": "approve:$REQ_ID"},
      {"text": "NEIN - Ablehnen", "callback_data": "deny:$REQ_ID"}
    ],
    [
      {"text": "Spaeter entscheiden", "callback_data": "later:$REQ_ID"}
    ]
  ]
}
JSONEOF
)

# Nachricht mit Buttons senden
PAYLOAD=$(python3 -c "
import json,sys
print(json.dumps({
  \"chat_id\": int(\"${TELEGRAM_CHAT_ID}\"),
  \"text\": \"FRAGE AN JENS:\n\n\" + \"\"\"${QUESTION}\"\"\" + \"\n\nID: ${REQ_ID}\",
  \"reply_markup\": ${KEYBOARD}
}))
")

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" > /dev/null

# Auf Antwort warten (max 10 Minuten)
ANSWER_FILE="/tmp/telegram-answer-${REQ_ID}.txt"
TIMEOUT=600
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
  if [ -f "$ANSWER_FILE" ]; then
    cat "$ANSWER_FILE"
    rm -f "$ANSWER_FILE"
    exit 0
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

echo "TIMEOUT"
exit 1
