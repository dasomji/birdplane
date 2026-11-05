import { accessSync, constants, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve, delimiter } from "node:path";

// Reuse the frozen workspace's YAML parser (Vite's locked optional peer), offline.
const require = createRequire(import.meta.url);
const viteRequire = createRequire(
  require.resolve("vite/package.json", { paths: [resolve(import.meta.dirname, "../../../apps/web")] })
);
const { parse, stringify } = viteRequire("yaml");

const nullFile = (value) => {
  if (typeof value === "string") return "/dev/null";
  if (value && typeof value.path === "string") return { ...value, path: "/dev/null" };
  return value; // Invalid declarations must still fail Compose schema validation.
};

export async function checkCompose(root, file, run) {
  const source = readFileSync(join(root, file), "utf8");
  const document = parse(source, { merge: true });
  if (
    document.include !== undefined ||
    Object.values(document.services ?? {}).some((service) => service?.extends?.file !== undefined)
  )
    throw new Error(`External Compose includes/extends require an explicit isolated contract: ${file}`);
  // Compose's --env-file controls interpolation only. Replace service env_file
  // declarations too, so no checkout or external env file can ever be read.
  for (const service of Object.values(document.services ?? {})) {
    if (Array.isArray(service.env_file)) service.env_file = service.env_file.map(nullFile);
    else if (typeof service.env_file === "string") service.env_file = "/dev/null";
  }
  const env = { PATH: process.env.PATH };
  for (const [, key] of source.matchAll(/\$\{([A-Za-z_][A-Za-z_0-9]*)/g)) {
    env[key] = key.endsWith("PORT")
      ? "8080"
      : /^(VERIFY_ROOT|VERIFY_RUNTIME|PGDATA)$/.test(key)
        ? "/tmp/kitchen-config-only"
        : "kitchen-config-only";
  }
  const temporary = mkdtempSync(join(tmpdir(), "kitchen-compose-"));
  try {
    const config = join(temporary, "compose.yml");
    writeFileSync(config, stringify(document));
    await run(
      "docker",
      [
        "compose",
        "--env-file",
        "/dev/null",
        "--project-directory",
        dirname(join(root, file)),
        "-f",
        config,
        "config",
        "--quiet",
      ],
      { env, inheritEnv: false }
    );
    console.log(`Compose config validated without real env or daemon access: ${file}`);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

export async function checkWorkflows(root, files, run) {
  for (const file of files) {
    parse(readFileSync(join(root, file), "utf8"));
    console.log(`Workflow YAML parsed: ${file}`);
  }
  const actionlint = (process.env.PATH ?? "")
    .split(delimiter)
    .filter(Boolean)
    .map((dir) => join(dir, "actionlint"))
    .find((file) => {
      try {
        accessSync(file, constants.X_OK);
        return true;
      } catch {
        return false;
      }
    });
  if (actionlint && files.length) await run(actionlint, files);
  else console.log("Optional actionlint unavailable on PATH; mandatory YAML parsing completed (no tool download).");
}
