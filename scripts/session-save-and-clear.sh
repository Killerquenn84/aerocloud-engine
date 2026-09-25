#!/bin/bash
# Session-Reset Script - MUSS als root ausgefuehrt werden (vom Bot)
# Claude selbst kann tmux als aerocloud nicht steuern
set -e

PROJECT_DIR="/var/www/wordcloud-app-v2/server/aerocloud-engine"
cd "$PROJECT_DIR"

REASON="${1:-Session-Ende}"
TIMESTAMP=$(date +"%Y-%m-%d-%H%M")

# 1. Git commit (alles was Claude geschrieben hat)
git add -A 2>/dev/null || true
git commit -m "chore: session handover $TIMESTAMP - $REASON" --allow-empty 2>/dev/null || true

# 2. Telegram Info
bash scripts/telegram-send.sh "Session-Reset: $REASON. Commit gespeichert. Starte /clear in tmux..."

# 3. /clear in tmux senden (Bot laeuft als root, tmux gehoert root)
tmux send-keys -t aerocloud:claude "/clear" Enter
sleep 3

# 4. Neue Boot-Sequenz an Claude
tmux send-keys -t aerocloud:claude "Session wurde resetted wegen: $REASON. Lies JETZT in dieser Reihenfolge und arbeite autonom weiter: 1) wiki/log.md 2) wiki/index.md 3) CLAUDE.md (alle 13 Regeln, besonders Regel 5 Session-Lifecycle und Regel 11 Wiki) 4) .planning/STATE.md 5) .planning/ROADMAP.md 6) Letzte wiki/discussions/*-session-handover.md. Dann weiter mit der naechsten offenen Aufgabe. Per bash scripts/telegram-send.sh melden wenn Stand erfasst ist." Enter

echo "Session restarted successfully"
