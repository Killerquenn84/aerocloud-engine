/**
 * Wiki Query Script
 *
 * Searches wiki pages by keyword, reads matched pages,
 * and outputs combined content for LLM synthesis.
 *
 * Usage: tsx scripts/query.ts "signed distance field geometry"
 */

import { readFile, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const WIKI_DIR = path.join(ROOT, "wiki");
const INDEX_PATH = path.join(WIKI_DIR, "index.md");

interface IndexEntry {
  filename: string;
  title: string;
  summary: string;
}

/**
 * Parse wiki/index.md into structured entries.
 * Each line like: - [slug.md](slug.md) -- Summary text
 */
function parseIndex(content: string): IndexEntry[] {
  const entries: IndexEntry[] = [];
  const linkPattern = /^-\s+\[([^\]]+)\]\(([^)]+)\)\s*(?:--|—|—)\s*(.+)$/;

  for (const line of content.split("\n")) {
    const match = line.trim().match(linkPattern);
    if (match) {
      entries.push({
        filename: match[2],
        title: match[1],
        summary: match[3].trim(),
      });
    }
  }
  return entries;
}

/**
 * Parse YAML frontmatter from a wiki page (simple key: value extraction).
 */
function parseFrontmatter(content: string): Record<string, string> {
  const meta: Record<string, string> = {};
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) return meta;

  for (const line of fmMatch[1].split("\n")) {
    const kvMatch = line.match(/^(\w[\w_]*)\s*:\s*"?([^"]*)"?\s*$/);
    if (kvMatch) {
      meta[kvMatch[1]] = kvMatch[2];
    }
  }
  return meta;
}

/**
 * Score an entry against the query keywords.
 * Returns a relevance score (0 = no match).
 */
function scoreEntry(entry: IndexEntry, keywords: string[]): number {
  let score = 0;
  const haystack = `${entry.filename} ${entry.title} ${entry.summary}`.toLowerCase();

  for (const kw of keywords) {
    if (haystack.includes(kw)) {
      score += 1;
      // Boost exact title matches
      if (entry.title.toLowerCase().includes(kw)) {
        score += 2;
      }
      // Boost filename matches
      if (entry.filename.toLowerCase().includes(kw)) {
        score += 1;
      }
    }
  }
  return score;
}

async function query(searchQuery: string): Promise<void> {
  if (!existsSync(INDEX_PATH)) {
    console.error("Error: wiki/index.md not found. Run wiki:ingest first.");
    process.exit(1);
  }

  const keywords = searchQuery
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => w.length > 1);

  if (keywords.length === 0) {
    console.error("Error: Please provide at least one search keyword.");
    process.exit(1);
  }

  console.log(`Searching wiki for: ${keywords.join(", ")}\n`);

  // Parse index
  const indexContent = await readFile(INDEX_PATH, "utf-8");
  const entries = parseIndex(indexContent);

  // Score and rank entries
  const scored = entries
    .map((entry) => ({ entry, score: scoreEntry(entry, keywords) }))
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score);

  if (scored.length === 0) {
    // Fallback: scan all .md files for keyword matches in content
    console.log("No matches in index. Scanning wiki pages directly...\n");
    const files = await readdir(WIKI_DIR);
    const mdFiles = files.filter((f) => f.endsWith(".md") && f !== "index.md" && f !== "log.md");

    const fallbackMatches: { filename: string; score: number }[] = [];

    for (const file of mdFiles) {
      const content = await readFile(path.join(WIKI_DIR, file), "utf-8");
      const lower = content.toLowerCase();
      let fileScore = 0;
      for (const kw of keywords) {
        if (lower.includes(kw)) fileScore += 1;
      }
      if (fileScore > 0) {
        fallbackMatches.push({ filename: file, score: fileScore });
      }
    }

    if (fallbackMatches.length === 0) {
      console.log("No results found for the given query.");
      return;
    }

    fallbackMatches.sort((a, b) => b.score - a.score);
    const topFallback = fallbackMatches.slice(0, 5);

    console.log(`Found ${topFallback.length} page(s) via content search:\n`);
    for (const match of topFallback) {
      const content = await readFile(path.join(WIKI_DIR, match.filename), "utf-8");
      console.log(`${"=".repeat(60)}`);
      console.log(`FILE: wiki/${match.filename} (relevance: ${match.score})`);
      console.log(`${"=".repeat(60)}`);
      console.log(content);
      console.log();
    }
    return;
  }

  // Take top 5 results
  const topResults = scored.slice(0, 5);

  console.log(`Found ${scored.length} match(es). Showing top ${topResults.length}:\n`);

  for (const { entry, score } of topResults) {
    const filePath = path.join(WIKI_DIR, entry.filename);

    if (!existsSync(filePath)) {
      console.log(`${"=".repeat(60)}`);
      console.log(`FILE: wiki/${entry.filename} (relevance: ${score}) [FILE NOT FOUND]`);
      console.log(`Summary: ${entry.summary}`);
      console.log(`${"=".repeat(60)}\n`);
      continue;
    }

    const content = await readFile(filePath, "utf-8");
    const meta = parseFrontmatter(content);

    console.log(`${"=".repeat(60)}`);
    console.log(`FILE: wiki/${entry.filename} (relevance: ${score})`);
    if (meta.section) console.log(`SECTION: ${meta.section}`);
    if (meta.summary) console.log(`SUMMARY: ${meta.summary}`);
    console.log(`${"=".repeat(60)}`);
    console.log(content);
    console.log();
  }

  // Output synthesis prompt
  console.log(`${"=".repeat(60)}`);
  console.log("SYNTHESIS PROMPT");
  console.log(`${"=".repeat(60)}`);
  console.log(
    `Based on the ${topResults.length} wiki page(s) above, synthesize an answer for: "${searchQuery}"`,
  );
  console.log(
    "Reference specific pages and cross-references where appropriate.",
  );
}

// --- CLI entry point ---
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('Usage: tsx scripts/query.ts "<search query>"');
  console.error('Example: tsx scripts/query.ts "collision detection hierarchy"');
  process.exit(1);
}

await query(args.join(" "));
