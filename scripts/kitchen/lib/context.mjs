import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

export function trackedContext(root, prefix) {
  const directory = mkdtempSync(join(tmpdir(), "birdplane-build-"));
  try {
    const paths = execFileSync("git", ["ls-files", "-z", "--", prefix], { cwd: root, encoding: "utf8" })
      .split("\0")
      .filter(Boolean);
    for (const path of paths) {
      // Explicitly exclude environment files even if accidentally tracked upstream.
      if (/(^|\/)\.env(?:\.|$)/.test(path)) continue;
      if (!existsSync(join(root, path))) continue;
      const target = join(directory, path.slice(prefix.length));
      mkdirSync(dirname(target), { recursive: true });
      cpSync(join(root, path), target, { dereference: false });
    }
    return { directory, cleanup: () => rmSync(directory, { recursive: true, force: true }) };
  } catch (error) {
    rmSync(directory, { recursive: true, force: true });
    throw error;
  }
}
