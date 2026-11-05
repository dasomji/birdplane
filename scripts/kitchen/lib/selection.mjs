export function selectChecks(paths, { scriptsOnly = false } = {}) {
  const tests = new Set();
  let apiAtL2 = false;
  const packages = new Set();
  for (const path of paths) {
    if (/(?:metadata\.ts|manifest|favicon|locales\/)/.test(path)) tests.add("branding");
    if (path.startsWith("apps/mcp/")) {
      tests.add("mcp");
      continue;
    }
    if (path.endsWith(".md")) continue;
    if (
      [".gitignore", ".husky/pre-commit", ".github/workflows/birdplane-checks.yml"].includes(path) ||
      (path === "package.json" && scriptsOnly)
    )
      tests.add("kitchen");
    else if (
      [
        "package.json",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "turbo.json",
        ".npmrc",
        ".mise.toml",
        ".oxfmtrc.json",
        ".oxlintrc.json",
      ].includes(path)
    ) {
      packages.add("*");
      for (const suite of ["workspace", "branding", "filters"]) tests.add(suite);
    } else if (path.startsWith("scripts/kitchen/")) tests.add("kitchen");
    else if (path === "tests/branding.test.mjs") tests.add("branding");
    else if (/^deployments\/birdplane\/(backup-postgres|test_backup_postgres)\.py$/.test(path)) tests.add("backups");
    else if (path.startsWith("apps/api/")) apiAtL2 = true;
    else if (/^(packages|apps)\/[^/]+\//.test(path)) {
      const [, kind, name] = path.match(/^(packages|apps)\/([^/]+)\//);
      packages.add(kind === "packages" ? `@plane/${name}` : name);
      tests.add("workspace");
      if (kind === "packages") tests.add("filters");
    } else throw new Error(`No fast-check contract for ${path}; run check:full and add an explicit mapping`);
  }
  return { tests: [...tests].toSorted(), packages: [...packages].toSorted(), apiAtL2 };
}
