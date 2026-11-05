import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, sep } from "node:path";

export function stagedSnapshot(repo) {
  const git = (...args) => execFileSync("git", args, { cwd: repo, encoding: "utf8" });
  // --no-renames reports both sides of a rename (including cross-component moves).
  const paths = git("diff", "--cached", "--name-only", "--no-renames", "-z").split("\0").filter(Boolean);
  const tracked = git("ls-files", "-z").split("\0").filter(Boolean);
  const directory = mkdtempSync(join(tmpdir(), "birdplane-staged-"));
  const cleanup = () => rmSync(directory, { recursive: true, force: true });
  try {
    git("checkout-index", "--all", `--prefix=${directory}${sep}`);
    return { paths, tracked, directory, cleanup };
  } catch (error) {
    cleanup();
    throw error;
  }
}
