#!/bin/bash
# Auto-Telegram Hook: Sendet jede Tool-Nutzung an Jens
# Wird von Claude Code nach jedem Bash/Edit/Write/Task aufgerufen

PROJECT_DIR="/var/www/wordcloud-app-v2/server/aerocloud-engine"
ENV_FILE="$PROJECT_DIR/.env.telegram"

if [ ! -f "$ENV_FILE" ]; then exit 0; fi
source "$ENV_FILE"

# Hook input ist JSON via stdin
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get(\"tool_name\",\"unknown\"))" 2>/dev/null)
TOOL_INPUT=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); ti=d.get(\"tool_input\",{}); print(json.dumps(ti)[:500])" 2>/dev/null)
TOOL_OUTPUT=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); to=d.get(\"tool_response\",{}); print(json.dumps(to)[:1500])" 2>/dev/null)

# Filter: Nur wichtige Tools
case "$TOOL_NAME" in
  Bash|Edit|Write|MultiEdit|Task)
    MSG="[$TOOL_NAME]
Input: $TOOL_INPUT
Output: $TOOL_OUTPUT"
    
    # Auf 3800 Zeichen kuerzen
    MSG_SHORT="${MSG:0:3800}"
    
    # An Telegram senden (silently fail)
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -H "Content-Type: application/json" \
      -d "$(python3 -c "import json,sys; print(json.dumps({\"chat_id\": int(\"${TELEGRAM_CHAT_ID}\"), \"text\": sys.stdin.read()}))" <<< "$MSG_SHORT")" > /dev/null 2>&1
    ;;
esac

exit 0
