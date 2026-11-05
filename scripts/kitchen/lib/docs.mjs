import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

// Offline check: validate local Markdown destinations, including reference links.
// Remote URLs and heading fragments are not fetched by the verification gate.
export function checkLinks(root, paths) {
  const failures = [];
  for (const path of paths) {
    const text = readFileSync(resolve(root, path), "utf8")
      .replace(/```[^]*?```/g, "")
      .replace(/`[^`\n]*`/g, "");
    const destinations = [
      ...text.matchAll(/!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)/g),
      ...text.matchAll(/^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)/gm),
    ];
    for (const match of destinations) {
      const target = match[1].replace(/^<|>$/g, "").split(/[?#]/)[0];
      if (!target || /^(?:[a-z][a-z\d+.-]*:|\/)/i.test(target)) continue;
      if (!existsSync(resolve(root, dirname(path), decodeURIComponent(target)))) failures.push(`${path}: ${target}`);
    }
  }
  if (failures.length) throw new Error(`Missing relative links:\n${failures.join("\n")}`);
  console.log(`Relative links: ${paths.length} Markdown files checked (destinations only)`);
}
