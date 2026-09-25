#!/bin/bash
set -uo pipefail

PROJECT="/var/www/wordcloud-app-v2/server/aerocloud-engine"
cd "$PROJECT"

TOPICS_FILE="scripts/nightly-topics.txt"
DONE_DIR="wiki/research/nightly"
TODO_LIST="/tmp/topics-todo-$$.txt"

> "$TODO_LIST"
while IFS= read -r topic; do
  [ -z "$topic" ] && continue
  slug=$(echo "$topic" | tr "[:upper:]" "[:lower:]" | sed "s/[^a-z0-9]/-/g" | sed "s/-\+/-/g" | sed "s/^-//;s/-$//")
  if ! ls "$DONE_DIR" 2>/dev/null | grep -q "$slug"; then
    echo "$topic" >> "$TODO_LIST"
  fi
done < "$TOPICS_FILE"

TOTAL=$(wc -l < "$TODO_LIST")
echo "=== INTENSIVE RESEARCH START ==="
echo "Topics offen: $TOTAL"
bash scripts/telegram-send.sh "Intensive Research gestartet: $TOTAL Topics."

COUNTER=0
SUCCESS=0
FAIL=0

while IFS= read -r topic; do
  COUNTER=$((COUNTER + 1))
  slug=$(echo "$topic" | tr "[:upper:]" "[:lower:]" | sed "s/[^a-z0-9]/-/g" | sed "s/-\+/-/g" | sed "s/^-//;s/-$//")
  DATE=$(date +%Y-%m-%d)
  OUTFILE="$DONE_DIR/${DATE}-${slug}.md"
  echo "[$COUNTER/$TOTAL] $topic"
  
  PROMPT="Du bist Researcher fuer AeroCloud Engine. Word-Cloud-Engine mit Quality-Diversity: PyTorch Diff-Rendering, MAP-Elites, BOP-Elites, CQD, BERT, Sinkhorn-Knopp, SDF, MAT, Seam Carving, Bezier. Stack: Python 3.11 + PyTorch 2.7 CUDA + Rust/WASM + Next.js + FastAPI + Celery + PostgreSQL pgvector.

TOPIC: $topic

Recherche INTENSIV Stand April 2026: 1) State of the Art mit verifizierten Versionen 2) Papers mit URLs 3) Code Python/Rust/TS 4) Known Issues, CVEs 5) Best Practices 6) AeroCloud Integration 7) Alternativen 8) Benchmarks 9) v1 Empfehlung. Markdown, 300-800 Zeilen, keine Floskeln."

  if timeout 240 gemini -p "$PROMPT" > /tmp/research-raw-$$.txt 2>&1; then
    {
      echo "---"
      echo "title: $topic"
      echo "slug: $slug"
      echo "source: nightly-research"
      echo "researched_by: Gemini CLI"
      echo "researched_on: $DATE"
      echo "tags: [research, nightly, intensive]"
      echo "---"
      echo ""
      echo "# $topic"
      echo ""
      cat /tmp/research-raw-$$.txt
    } > "$OUTFILE"
    SUCCESS=$((SUCCESS + 1))
    echo "  OK"
  else
    FAIL=$((FAIL + 1))
    echo "  FAIL"
  fi
  
  if [ $((COUNTER % 5)) -eq 0 ]; then
    bash scripts/telegram-send.sh "Progress: $COUNTER/$TOTAL ($SUCCESS ok, $FAIL fail)"
  fi
  sleep 2
done < "$TODO_LIST"

rm -f "$TODO_LIST" /tmp/research-raw-$$.txt
git add wiki/research/nightly/ 2>/dev/null || true
git commit -m "docs(wiki): intensive research $DATE ($SUCCESS topics)" 2>/dev/null || true

TOTAL_WIKI=$(find wiki -type f -name "*.md" 2>/dev/null | wc -l)
bash scripts/telegram-send.sh "INTENSIVE RESEARCH FERTIG: $SUCCESS/$TOTAL ok. Wiki total: $TOTAL_WIKI files."
echo "=== DONE: $SUCCESS/$TOTAL ==="
