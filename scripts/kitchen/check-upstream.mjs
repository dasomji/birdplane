import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { docsFormatPaths, verifyRuffExemptions } from "./lib/upstream-exemptions.mjs";

const root = process.cwd();
const entries = JSON.parse(readFileSync(new URL("./upstream-exemptions.json", import.meta.url), "utf8"));

// Exit 1 means diagnostics for these tools. Crashes, signals and setup failures
// still propagate. The outer Gate monitors this entire process group and disk.
function diagnosticRun(command, args) {
  try {
    return {
      status: 0,
      stdout: execFileSync(command, args, { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] }),
    };
  } catch (error) {
    if (error.status !== 1 || error.signal) throw error;
    return { status: 1, stdout: String(error.stdout) };
  }
}

function report(entry) {
  console.log(
    `Applied upstream exemption: ${entry.check} ${entry.path}${entry.line ? `:${entry.line}:${entry.column}` : ""} ${entry.rule}${entry.symbol ? ` ${entry.symbol}` : ""} (${entry.upstreamRef}, blob ${entry.upstreamBlob}): ${entry.justification}`
  );
}

if (process.argv[2] === "api-ruff") {
  const result = diagnosticRun("uvx", [
    "--from",
    "ruff==0.9.7",
    "ruff",
    "check",
    "--output-format",
    "json",
    "apps/api",
  ]);
  console.log(result.stdout);
  const diagnostics = JSON.parse(result.stdout);
  if (!Array.isArray(diagnostics) || result.status !== (diagnostics.length ? 1 : 0))
    throw new Error("Ruff exit status does not match its JSON diagnostics");
  for (const entry of verifyRuffExemptions(root, entries, diagnostics)) report(entry);
} else if (process.argv[2] === "docs-format") {
  const paths = process.argv.slice(3);
  const exempted = entries.filter((entry) => entry.check === "docs-format");
  const different = [];
  if (exempted.length) {
    const result = diagnosticRun("pnpm", ["exec", "oxfmt", "--list-different", ...exempted.map((entry) => entry.path)]);
    different.push(...result.stdout.trim().split("\n").filter(Boolean));
    if (
      result.status !== (different.length ? 1 : 0) ||
      different.some((path) => !exempted.some((entry) => entry.path === path))
    )
      throw new Error(`Unexpected formatter diagnostics: ${result.stdout}`);
  }
  const checked = docsFormatPaths(root, entries, paths, different);
  for (const entry of exempted) report(entry);
  if (checked.length) execFileSync("pnpm", ["exec", "oxfmt", "--check", ...checked], { stdio: "inherit" });
} else {
  throw new Error("Expected api-ruff or docs-format");
}
