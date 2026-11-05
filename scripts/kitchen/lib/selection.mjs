// Only independent, cheap diagnostics; a focused run never completes check:full.
export function selectFullPhases(args) {
  if (args.length === 0) return null;
  const allowed = ["kitchen-tests", "api-ruff", "root-docs-format", "root-docs-links"];
  const selected = new Set();
  for (let index = 0; index < args.length; index += 2) {
    if (args[index] !== "--phase" || !allowed.includes(args[index + 1]))
      throw new Error(`Expected --phase ${allowed.join("|")}`);
    selected.add(args[index + 1]);
  }
  return [...selected];
}

export function selectChecks(paths, { scriptsOnly = false, merging = false } = {}) {
  const infrastructure = new Set();
  const deferred = new Set();
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
    if (isInfrastructure(path)) {
      infrastructure.add(path);
      if (path === ".github/workflows/birdplane-checks.yml") tests.add("kitchen");
      continue;
    }
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
    else if (/^deployments\/birdplane\/[^/]+\.(?:mjs|py)$/.test(path)) continue;
    else if (path.startsWith("apps/api/")) apiAtL2 = true;
    else if (/^(packages|apps)\/[^/]+\//.test(path)) {
      const [, kind, name] = path.match(/^(packages|apps)\/([^/]+)\//);
      packages.add(kind === "packages" ? `@plane/${name}` : name);
      tests.add("workspace");
      if (kind === "packages") tests.add("filters");
    } else if (merging && !path.startsWith("scripts/kitchen/") && !path.startsWith("deployments/birdplane/"))
      deferred.add(path);
    else throw new Error(`No fast-check contract for ${path}; run check:full and add an explicit mapping`);
  }
  return {
    infrastructure: [...infrastructure].toSorted(),
    deferred: [...deferred].toSorted(),
    tests: [...tests].toSorted(),
    packages: [...packages].toSorted(),
    apiAtL2,
  };
}

export function isInfrastructure(path) {
  return (
    /^docker-compose[^/]*\.ya?ml$/.test(path) ||
    /^deployments\/birdplane\/compose[^/]*\.ya?ml$/.test(path) ||
    /^\.github\/workflows\/[^/]+\.ya?ml$/.test(path) ||
    /^deployments\/birdplane\/Dockerfile(?:\.[^/]+)?$/.test(path)
  );
}
