import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

function guardedEntries(root, entries, check) {
  if (!Array.isArray(entries)) throw new Error("Invalid upstream exemption register: expected array");
  const seen = new Set();
  for (const entry of entries) {
    if (
      !entry ||
      typeof entry.path !== "string" ||
      !/^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[\w./-]+$/.test(entry.path) ||
      entry.upstreamRef !== "v1.4.3" ||
      !/^[a-f0-9]{40}$/.test(entry.upstreamBlob ?? "") ||
      typeof entry.justification !== "string" ||
      !entry.justification.trim() ||
      !["api-ruff", "docs-format"].includes(entry.check) ||
      (entry.check === "docs-format" && entry.rule !== "oxfmt") ||
      (entry.check === "api-ruff" &&
        (entry.rule !== "F401" ||
          typeof entry.symbol !== "string" ||
          !entry.symbol ||
          ![entry.line, entry.column, entry.endLine, entry.endColumn].every(
            (value) => Number.isInteger(value) && value > 0
          )))
    )
      throw new Error(`Invalid upstream exemption: ${JSON.stringify(entry)}`);
    const key = JSON.stringify([
      entry.check,
      entry.path,
      entry.rule,
      entry.symbol,
      entry.line,
      entry.column,
      entry.endLine,
      entry.endColumn,
    ]);
    if (seen.has(key)) throw new Error(`Duplicate upstream exemption: ${entry.path}`);
    seen.add(key);
  }
  const selected = entries.filter((entry) => entry.check === check);
  for (const entry of selected) {
    const blob = execFileSync("git", ["hash-object", "--", entry.path], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    if (blob !== entry.upstreamBlob)
      throw new Error(`Upstream exemption blob changed: ${entry.path}; fix the file and remove its exemption`);
  }
  return selected;
}

export function verifyRuffExemptions(root, entries, diagnostics) {
  const remaining = new Set(guardedEntries(root, entries, "api-ruff"));
  const applied = [];
  for (const diagnostic of diagnostics) {
    const entry = [...remaining].find(
      (candidate) =>
        resolve(root, candidate.path) === diagnostic.filename &&
        candidate.rule === diagnostic.code &&
        diagnostic.message === `\`${candidate.symbol}\` imported but unused` &&
        candidate.line === diagnostic.location.row &&
        candidate.column === diagnostic.location.column &&
        candidate.endLine === diagnostic.end_location.row &&
        candidate.endColumn === diagnostic.end_location.column
    );
    if (!entry) throw new Error(`Unexempted Ruff diagnostic: ${JSON.stringify(diagnostic)}`);
    remaining.delete(entry);
    applied.push(entry);
  }
  if (remaining.size) throw new Error(`Stale Ruff exemption: ${[...remaining].map((entry) => entry.path).join(", ")}`);
  return applied;
}

export function docsFormatPaths(root, entries, paths, different) {
  const selected = guardedEntries(root, entries, "docs-format");
  for (const entry of selected) {
    if (!paths.includes(entry.path) || !different.includes(entry.path))
      throw new Error(`Stale docs-format exemption: ${entry.path}`);
  }
  return paths.filter((path) => !selected.some((entry) => entry.path === path));
}
