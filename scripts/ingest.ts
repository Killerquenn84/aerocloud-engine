/**
 * Wiki Ingest Script
 *
 * Reads a source file, creates a summary wiki page with YAML frontmatter,
 * updates wiki/index.md and appends to wiki/log.md.
 *
 * Usage: tsx scripts/ingest.ts raw/sources/paper.md
 */

import { readFile, writeFile, appendFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const WIKI_DIR = path.join(ROOT, "wiki");

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function timestamp(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Extract a one-line summary from the first meaningful paragraph of the source.
 */
function extractSummary(content: string): string {
  const lines = content.split("\n").filter((l) => l.trim().length > 0);
  // Skip headings, find the first paragraph-like line
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("#") || trimmed.startsWith("---") || trimmed.startsWith(">")) {
      continue;
    }
    // Return the first ~150 chars of the first real paragraph
    return trimmed.length > 150 ? trimmed.slice(0, 147) + "..." : trimmed;
  }
  return "No summary available.";
}

/**
 * Extract the title from the first heading, or derive it from the filename.
 */
function extractTitle(content: string, filename: string): string {
  const match = content.match(/^#\s+(.+)$/m);
  if (match) {
    return match[1].trim();
  }
  return filename.replace(/\.md$/, "").replace(/[-_]/g, " ");
}

/**
 * Determine a wiki section based on keywords in the content.
 */
function detectSection(content: string, title: string): string {
  const text = (content + " " + title).toLowerCase();

  const sectionKeywords: [string, string[]][] = [
    ["Mathematische Grundlagen", ["math", "zipf", "tf-idf", "np-hard", "packing", "normalisierung"]],
    ["Semantik (The Brain)", ["bert", "embedding", "semantic", "transport", "sinkhorn", "nlp", "t-sne", "umap"]],
    ["Geometrie (The Skeleton)", ["sdf", "geometry", "medial", "collision", "skeleton", "distance field"]],
    ["Inner Loop (The Muscles)", ["differentiable", "render", "adam", "optimizer", "pytorch", "loss"]],
    ["Outer Loop (The Evolution)", ["cqd", "map-elites", "quality-diversity", "evolution", "archive"]],
    ["Post-Processing", ["seam", "bezier", "export", "svg", "pdf", "compression"]],
    ["Qualitaetsmetriken", ["metric", "quality", "readability", "coverage"]],
  ];

  for (const [section, keywords] of sectionKeywords) {
    if (keywords.some((kw) => text.includes(kw))) {
      return section;
    }
  }
  return "Quellen";
}

async function ingest(sourcePath: string): Promise<void> {
  const absSource = path.resolve(ROOT, sourcePath);

  if (!existsSync(absSource)) {
    console.error(`Error: Source file not found: ${absSource}`);
    process.exit(1);
  }

  const content = await readFile(absSource, "utf-8");
  const filename = path.basename(absSource);
  const title = extractTitle(content, filename);
  const slug = slugify(path.basename(filename, path.extname(filename)));
  const summary = extractSummary(content);
  const section = detectSection(content, title);
  const date = timestamp();
  const wikiFilename = `${slug}.md`;
  const wikiPath = path.join(WIKI_DIR, wikiFilename);

  // Ensure wiki directory exists
  await mkdir(WIKI_DIR, { recursive: true });

  // Build the wiki page with YAML frontmatter
  const wikiPage = `---
title: "${title}"
slug: "${slug}"
source: "${sourcePath}"
created: "${date}"
section: "${section}"
summary: "${summary}"
cross_refs:
  - index.md
  - source-blueprint.md
---

# ${title}

> ${summary}

## Quelle

Ingested from \`${sourcePath}\` on ${date}.

## Inhalt

${content}

## Siehe auch

- [Index](index.md)
- [Source Blueprint](source-blueprint.md)
`;

  await writeFile(wikiPath, wikiPage, "utf-8");
  console.log(`Created wiki page: wiki/${wikiFilename}`);

  // Update wiki/index.md - append to the detected section or at the end
  const indexPath = path.join(WIKI_DIR, "index.md");
  const indexContent = await readFile(indexPath, "utf-8");

  const indexEntry = `- [${slug}.md](${slug}.md) — ${summary}`;

  // Try to find the section header and insert after the last entry in that section
  const sectionHeader = `## ${section}`;
  const sectionIdx = indexContent.indexOf(sectionHeader);

  let updatedIndex: string;
  if (sectionIdx !== -1) {
    // Find the end of this section (next ## or EOF)
    const afterSection = indexContent.indexOf("\n## ", sectionIdx + sectionHeader.length);
    const insertPos = afterSection !== -1 ? afterSection : indexContent.length;
    updatedIndex =
      indexContent.slice(0, insertPos).trimEnd() +
      "\n" +
      indexEntry +
      "\n" +
      (afterSection !== -1 ? "\n" + indexContent.slice(insertPos + 1) : "\n");
  } else {
    // Section doesn't exist - add it at the end
    updatedIndex = indexContent.trimEnd() + `\n\n${sectionHeader}\n${indexEntry}\n`;
  }

  await writeFile(indexPath, updatedIndex, "utf-8");
  console.log(`Updated wiki/index.md (section: ${section})`);

  // Append to wiki/log.md
  const logPath = path.join(WIKI_DIR, "log.md");
  const logEntry = `\n## [${date}] ingest | ${filename}\n- Neue Seite: ${slug}\n- Sektion: ${section}\n- Zusammenfassung: ${summary}\n`;

  await appendFile(logPath, logEntry, "utf-8");
  console.log(`Appended to wiki/log.md`);

  console.log(`\nIngest complete: ${sourcePath} -> wiki/${wikiFilename}`);
}

// --- CLI entry point ---
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error("Usage: tsx scripts/ingest.ts <source-file-path>");
  console.error("Example: tsx scripts/ingest.ts raw/sources/paper.md");
  process.exit(1);
}

await ingest(args[0]);
