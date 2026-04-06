/**
 * Wiki Lint / Health-Check Script
 *
 * Scans all .md files in wiki/ and checks for:
 * - Valid YAML frontmatter
 * - No broken internal links
 * - All pages listed in index.md
 * - All pages have at least one cross-reference
 *
 * Usage: tsx scripts/lint-wiki.ts
 */

import { readFile, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const WIKI_DIR = path.join(ROOT, "wiki");

interface LintIssue {
  file: string;
  severity: "error" | "warning";
  message: string;
}

/**
 * Recursively collect all .md files from a directory (flat for wiki/).
 */
async function collectMarkdownFiles(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    if (entry.isFile() && entry.name.endsWith(".md")) {
      files.push(entry.name);
    } else if (entry.isDirectory()) {
      // Support nested wiki directories if they exist
      const subDir = path.join(dir, entry.name);
      const subFiles = await readdir(subDir, { withFileTypes: true });
      for (const sub of subFiles) {
        if (sub.isFile() && sub.name.endsWith(".md")) {
          files.push(path.join(entry.name, sub.name));
        }
      }
    }
  }
  return files;
}

/**
 * Check if a file has valid YAML frontmatter (--- delimited block).
 */
function checkFrontmatter(content: string, filename: string): LintIssue[] {
  const issues: LintIssue[] = [];

  // index.md and log.md are exempt from frontmatter requirement
  if (filename === "index.md" || filename === "log.md") {
    return issues;
  }

  if (!content.startsWith("---\n")) {
    issues.push({
      file: filename,
      severity: "error",
      message: "Missing YAML frontmatter (must start with ---)",
    });
    return issues;
  }

  const endIdx = content.indexOf("\n---", 4);
  if (endIdx === -1) {
    issues.push({
      file: filename,
      severity: "error",
      message: "Malformed YAML frontmatter (missing closing ---)",
    });
    return issues;
  }

  const frontmatter = content.slice(4, endIdx);

  // Check for required fields
  const requiredFields = ["title", "slug", "created"];
  for (const field of requiredFields) {
    if (!frontmatter.includes(`${field}:`)) {
      issues.push({
        file: filename,
        severity: "warning",
        message: `Frontmatter missing recommended field: ${field}`,
      });
    }
  }

  return issues;
}

/**
 * Extract all internal markdown links from content.
 * Matches [text](target.md) style links.
 */
function extractInternalLinks(content: string): string[] {
  const linkPattern = /\[([^\]]*)\]\(([^)]+\.md)\)/g;
  const links: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = linkPattern.exec(content)) !== null) {
    const target = match[2];
    // Skip external links
    if (!target.startsWith("http://") && !target.startsWith("https://")) {
      links.push(target);
    }
  }
  return links;
}

/**
 * Parse index.md to extract all listed page filenames.
 */
function parseIndexPages(indexContent: string): string[] {
  const linkPattern = /\[([^\]]+)\]\(([^)]+\.md)\)/g;
  const pages: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = linkPattern.exec(indexContent)) !== null) {
    pages.push(match[2]);
  }
  return pages;
}

async function lint(): Promise<void> {
  console.log("Wiki Lint - Health Check\n");
  console.log(`Scanning: ${WIKI_DIR}\n`);

  if (!existsSync(WIKI_DIR)) {
    console.error("Error: wiki/ directory not found.");
    process.exit(1);
  }

  const allFiles = await collectMarkdownFiles(WIKI_DIR);
  const issues: LintIssue[] = [];

  console.log(`Found ${allFiles.length} markdown file(s)\n`);

  // Read all files into memory
  const fileContents = new Map<string, string>();
  for (const file of allFiles) {
    const content = await readFile(path.join(WIKI_DIR, file), "utf-8");
    fileContents.set(file, content);
  }

  // --- Check 1: Valid YAML frontmatter ---
  console.log("Check 1: YAML Frontmatter");
  for (const [filename, content] of fileContents) {
    const fmIssues = checkFrontmatter(content, filename);
    issues.push(...fmIssues);
  }

  // --- Check 2: No broken internal links ---
  console.log("Check 2: Internal Links");
  for (const [filename, content] of fileContents) {
    const links = extractInternalLinks(content);
    for (const link of links) {
      if (!allFiles.includes(link)) {
        issues.push({
          file: filename,
          severity: "error",
          message: `Broken internal link: [${link}] (file does not exist)`,
        });
      }
    }
  }

  // --- Check 3: All pages listed in index.md ---
  console.log("Check 3: Index Coverage");
  const indexContent = fileContents.get("index.md");
  if (!indexContent) {
    issues.push({
      file: "index.md",
      severity: "error",
      message: "wiki/index.md is missing!",
    });
  } else {
    const indexedPages = parseIndexPages(indexContent);
    const contentPages = allFiles.filter((f) => f !== "index.md" && f !== "log.md");

    for (const page of contentPages) {
      if (!indexedPages.includes(page)) {
        issues.push({
          file: page,
          severity: "warning",
          message: "Page not listed in wiki/index.md (orphaned)",
        });
      }
    }

    // Check for index entries pointing to nonexistent pages
    for (const indexed of indexedPages) {
      if (!allFiles.includes(indexed)) {
        issues.push({
          file: "index.md",
          severity: "error",
          message: `Index references nonexistent page: ${indexed}`,
        });
      }
    }
  }

  // --- Check 4: Cross-references ---
  console.log("Check 4: Cross-References\n");
  const contentPages = allFiles.filter((f) => f !== "index.md" && f !== "log.md");

  for (const page of contentPages) {
    const content = fileContents.get(page)!;
    const links = extractInternalLinks(content);
    // Filter out self-links
    const crossRefs = links.filter((l) => l !== page);

    if (crossRefs.length === 0) {
      issues.push({
        file: page,
        severity: "warning",
        message: "No cross-references to other wiki pages",
      });
    }
  }

  // --- Report ---
  console.log("=".repeat(60));
  console.log("RESULTS");
  console.log("=".repeat(60));

  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  if (issues.length === 0) {
    console.log("\nAll checks passed! Wiki is healthy.\n");
  } else {
    if (errors.length > 0) {
      console.log(`\nErrors (${errors.length}):`);
      for (const issue of errors) {
        console.log(`  [ERROR] ${issue.file}: ${issue.message}`);
      }
    }

    if (warnings.length > 0) {
      console.log(`\nWarnings (${warnings.length}):`);
      for (const issue of warnings) {
        console.log(`  [WARN]  ${issue.file}: ${issue.message}`);
      }
    }

    console.log(`\nTotal: ${errors.length} error(s), ${warnings.length} warning(s)`);
  }

  // Summary stats
  console.log(`\n--- Stats ---`);
  console.log(`Total pages: ${allFiles.length}`);
  console.log(`Content pages: ${contentPages.length}`);
  console.log(
    `Indexed pages: ${indexContent ? parseIndexPages(indexContent).length : 0}`,
  );
  console.log(`Issues found: ${issues.length}`);

  // Exit with error code if there are errors
  if (errors.length > 0) {
    process.exit(1);
  }
}

// --- CLI entry point ---
await lint();
