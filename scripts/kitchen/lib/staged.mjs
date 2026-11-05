import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { join, resolve, sep } from "node:path";

export function stagedSnapshot(repo) {
  const git = (...args) => execFileSync("git", args, { cwd: repo, encoding: "utf8" });
  // --no-renames reports both sides of a rename (including cross-component moves).
  const paths = git("diff", "--cached", "--name-only", "--no-renames", "-z").split("\0").filter(Boolean);
  const tracked = git("ls-files", "-z").split("\0").filter(Boolean);
  const temporary = join(repo, ".kitchen/tmp");
  mkdirSync(temporary, { recursive: true });
  const directory = mkdtempSync(join(temporary, "staged-"));
  const cleanup = () => rmSync(directory, { recursive: true, force: true });
  try {
    git("checkout-index", "--all", `--prefix=${directory}${sep}`);
    const mergeHead = git("rev-parse", "--git-path", "MERGE_HEAD").trim();
    const merging = existsSync(resolve(repo, mergeHead));
    return { paths, tracked, directory, cleanup, merging };
  } catch (error) {
    cleanup();
    throw error;
  }
}
