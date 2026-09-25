#!/bin/bash
# AeroCloud Engine — Nightly Research
#
# Runs nightly at 02:00 Berlin time via cron.
# Picks 3 random topics, queries Gemini CLI, saves results to wiki/research/nightly/
# Auto-commits the new files and sends a Telegram summary.
#
# Usage:
#   bash scripts/nightly-research.sh          # run now
#   bash scripts/nightly-research.sh --dry    # test mode (1 topic only, no commit)

set -uo pipefail

PROJECT_ROOT="/var/www/wordcloud-app-v2/server/aerocloud-engine"
cd "$PROJECT_ROOT"

DRY_RUN="false"
if [[ "${1:-}" == "--dry" ]]; then
    DRY_RUN="true"
fi

DATE=$(date +%Y-%m-%d)
TOPICS_FILE="$PROJECT_ROOT/scripts/nightly-topics.txt"
NIGHTLY_DIR="$PROJECT_ROOT/wiki/research/nightly"
LOG_FILE="$PROJECT_ROOT/wiki/log.md"

mkdir -p "$NIGHTLY_DIR"

# Helper: send Telegram (idempotent, uses existing script)
send_telegram() {
    local msg="$1"
    bash "$PROJECT_ROOT/scripts/telegram-send.sh" "$msg" || echo "Telegram send failed"
}

# Helper: error escalation
escalate_error() {
    local stage="$1"
    local detail="$2"
    send_telegram "=== NIGHTLY RESEARCH ERROR ===

Datum: $DATE
Stage: $stage
Detail: $detail

Manueller Check noetig."
}

# Helper: slugify topic
slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g' | sed 's/^-\+//;s/-\+$//' | cut -c1-60
}

# Sanity check: topics file
if [[ ! -f "$TOPICS_FILE" ]]; then
    escalate_error "init" "topics file missing: $TOPICS_FILE"
    exit 1
fi

# Pick topics (3 for normal run, 1 for dry run)
NUM_TOPICS=5
if [[ "$DRY_RUN" == "true" ]]; then
    NUM_TOPICS=1
fi

mapfile -t ALL_TOPICS < <(grep -v '^[[:space:]]*$' "$TOPICS_FILE")
if [[ "${#ALL_TOPICS[@]}" -lt "$NUM_TOPICS" ]]; then
    escalate_error "init" "not enough topics in $TOPICS_FILE"
    exit 1
fi

mapfile -t SELECTED < <(printf '%s\n' "${ALL_TOPICS[@]}" | shuf -n "$NUM_TOPICS")

echo "Selected topics for $DATE:"
printf '  - %s\n' "${SELECTED[@]}"

# Run research per topic
CREATED_FILES=()
SUMMARY_LINES=()
FAILED_TOPICS=()

for topic in "${SELECTED[@]}"; do
    slug=$(slugify "$topic")
    outfile="$NIGHTLY_DIR/${DATE}-${slug}.md"
    relpath="research/nightly/${DATE}-${slug}.md"

    echo ""
    echo ">>> Researching: $topic"
    echo ">>> Output: $relpath"

    query="AeroCloud Engine Thema: $topic. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich."

    # Call Gemini with timeout
    if response=$(timeout 180 gemini -p "$query" 2>&1); then
        # Success path
        {
            echo "---"
            echo "title: \"Nightly Research: $topic\""
            echo "slug: ${DATE}-${slug}"
            echo "created: $DATE"
            echo "tags: [nightly, research, gemini, automated]"
            echo "source: automated-nightly-cron"
            echo "topic: \"$topic\""
            echo "---"
            echo ""
            echo "# Nightly Research: $topic"
            echo ""
            echo "**Datum:** $DATE"
            echo "**Automatisch erzeugt von:** scripts/nightly-research.sh"
            echo "**Modell:** Gemini CLI"
            echo ""
            echo "## Query"
            echo ""
            echo "\`\`\`"
            echo "$query"
            echo "\`\`\`"
            echo ""
            echo "## Gemini Response"
            echo ""
            echo "$response"
            echo ""
            echo "## Siehe auch"
            echo ""
            echo "- [research/summary.md](research/summary.md) — Research Synthesis"
            echo "- [research/stack.md](research/stack.md) — Stack Research"
            echo "- [log.md](log.md) — Wiki Activity Log"
        } > "$outfile"

        CREATED_FILES+=("$outfile")
        SUMMARY_LINES+=("OK: $topic")
        echo ">>> Saved: $outfile"
    else
        # Failure path — still create a stub file documenting the failure
        err_excerpt=$(echo "$response" | head -c 400)
        {
            echo "---"
            echo "title: \"Nightly Research FAILED: $topic\""
            echo "slug: ${DATE}-${slug}"
            echo "created: $DATE"
            echo "tags: [nightly, research, failure, automated]"
            echo "source: automated-nightly-cron"
            echo "topic: \"$topic\""
            echo "status: failed"
            echo "---"
            echo ""
            echo "# Nightly Research FAILED: $topic"
            echo ""
            echo "**Datum:** $DATE"
            echo "**Status:** Gemini call failed or timed out"
            echo ""
            echo "## Error Output"
            echo ""
            echo "\`\`\`"
            echo "$err_excerpt"
            echo "\`\`\`"
            echo ""
            echo "## Siehe auch"
            echo ""
            echo "- [log.md](log.md) — Wiki Activity Log"
        } > "$outfile"

        CREATED_FILES+=("$outfile")
        SUMMARY_LINES+=("FAIL: $topic")
        FAILED_TOPICS+=("$topic")
        echo ">>> FAILED: $topic (stub written)"
    fi
done

# Append to wiki/log.md
{
    echo ""
    echo "## [$DATE] nightly-research | ${#SELECTED[@]} topics"
    for topic in "${SELECTED[@]}"; do
        echo "- $topic"
    done
    if [[ "${#FAILED_TOPICS[@]}" -gt 0 ]]; then
        echo "- Failures: ${#FAILED_TOPICS[@]}"
    fi
} >> "$LOG_FILE"

# Git commit (skip on dry run)
COMMIT_HASH=""
if [[ "$DRY_RUN" == "false" ]]; then
    if git -C "$PROJECT_ROOT" add wiki/research/nightly/ wiki/log.md 2>/dev/null; then
        if git -C "$PROJECT_ROOT" -c user.name="AeroCloud Nightly" -c user.email="nightly@aerocloud.engine" commit -m "nightly(research): $DATE — ${#SELECTED[@]} topics" >/dev/null 2>&1; then
            COMMIT_HASH=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
            echo ">>> Committed: $COMMIT_HASH"
        else
            echo ">>> No commit (nothing changed?)"
        fi
    fi
fi

# Telegram summary
DRY_PREFIX=""
if [[ "$DRY_RUN" == "true" ]]; then
    DRY_PREFIX="[DRY RUN] "
fi

SUMMARY_TEXT="=== ${DRY_PREFIX}NIGHTLY RESEARCH $DATE ===

Topics: ${#SELECTED[@]}
Erfolge: $((${#SELECTED[@]} - ${#FAILED_TOPICS[@]}))
Fehler: ${#FAILED_TOPICS[@]}

Details:
$(printf '  %s\n' "${SUMMARY_LINES[@]}")

Gespeichert in: wiki/research/nightly/
Dateien: ${#CREATED_FILES[@]}"

if [[ -n "$COMMIT_HASH" ]]; then
    SUMMARY_TEXT="$SUMMARY_TEXT

Commit: $COMMIT_HASH"
fi

send_telegram "$SUMMARY_TEXT"

# Escalate if any failures
if [[ "${#FAILED_TOPICS[@]}" -gt 0 ]]; then
    for t in "${FAILED_TOPICS[@]}"; do
        escalate_error "gemini-call" "Topic '$t' failed — stub file written, manual check needed"
    done
fi

echo ""
echo ">>> Nightly research complete"
exit 0
