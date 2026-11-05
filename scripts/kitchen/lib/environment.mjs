import { execFileSync } from "node:child_process";

// Git exports repository/index overrides to hooks. Child checks in a snapshot or
// temporary repository must not reuse those overrides (especially in a worktree).
const localGitVariables = new Set(
  execFileSync("git", ["rev-parse", "--local-env-vars"], { encoding: "utf8" }).trim().split("\n")
);
export function isolatedEnvironment(environment = process.env) {
  return Object.fromEntries(Object.entries(environment).filter(([key]) => !localGitVariables.has(key)));
}
