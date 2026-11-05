import { execFileSync } from "node:child_process";
import { cpSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { checkLinks } from "./lib/docs.mjs";
import { trackedContext } from "./lib/context.mjs";
import { Gate } from "./lib/process.mjs";

const root = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
process.chdir(root);
const gate = new Gate(root, "check-full");
const id = `kitchen-${randomUUID().slice(0, 12)}`;
const apiImage = `birdplane-api-${id}:test`;
const mcpImage = `birdplane-mcp-${id}:test`;
const compose = ["compose", "--env-file", "/dev/null", "-p", id, "-f", "scripts/kitchen/compose/api-tests.yml"];
const composeEnv = { KITCHEN_API_IMAGE: apiImage };
const phases = [
  "kitchen-tests",
  "workspace-check",
  "workspace-build",
  "workspace-tests",
  "branding",
  "shared-state-filters",
  "api-ruff",
  "api-image",
  "api-services",
  "api-pytest",
  "api-migration-boot",
  "mcp-sync",
  "mcp-pytest",
  "mcp-ruff",
  "mcp-wheel-guidance",
  "mcp-docker-guidance",
  "backup-tests-ruff",
  "root-docs-format",
  "root-docs-links",
  "cleanup",
];
let builderCreated = false;
let composeStarted = false;
let apiContext;
let mcpContext;
const images = new Set();
try {
  const tracked = execFileSync("git", ["ls-files", "-z"], { encoding: "utf8" }).split("\0").filter(Boolean);
  await gate.phase("kitchen-tests", async (run) => {
    await run("pnpm", ["exec", "oxfmt", "--check", "scripts/kitchen", ".github/workflows/birdplane-checks.yml"]);
    await run("pnpm", ["exec", "oxlint", "--deny-warnings", "scripts/kitchen"]);
    await run("node", ["--test", ...tracked.filter((path) => /^scripts\/kitchen\/.*\.test\.mjs$/.test(path))]);
  });
  // Limit concurrency to bound peak memory; all upstream tasks still run.
  await gate.phase("workspace-check", (run) => run("pnpm", ["check", "--concurrency=2"]));
  await gate.phase("workspace-build", (run) => run("pnpm", ["build", "--concurrency=2"]));
  await gate.phase("workspace-tests", (run) => run("pnpm", ["turbo", "run", "test", "--concurrency=2"]));
  await gate.phase("branding", (run) => run("pnpm", ["test:branding"]));
  await gate.phase("shared-state-filters", async (run) => {
    await run("pnpm", ["turbo", "run", "build", "--filter=@plane/shared-state", "--concurrency=2"]);
    await run("node", ["--test", "packages/shared-state/filters.test.mjs"]);
  });
  await gate.phase("api-ruff", (run) => run("uvx", ["--from", "ruff==0.9.7", "ruff", "check", "apps/api"]));
  await gate.phase("api-image", async (run) => {
    // Own builder: its cache/container/volume can be removed without pruning anyone else's cache.
    await run("docker", ["buildx", "create", "--name", id, "--driver", "docker-container"]);
    builderCreated = true;
    apiContext = trackedContext(root, "apps/api/");
    cpSync(join(root, "scripts/kitchen/lib/api-smoke.py"), join(apiContext.directory, "kitchen-smoke.py"));
    images.add(apiImage);
    await run("docker", [
      "buildx",
      "build",
      "--builder",
      id,
      "--load",
      "--progress=plain",
      "-t",
      apiImage,
      "-f",
      "scripts/kitchen/compose/Dockerfile.api-tests",
      apiContext.directory,
    ]);
  });
  await gate.phase(
    "api-services",
    async (run) => {
      composeStarted = true;
      await run(
        "docker",
        [...compose, "up", "-d", "--wait", "--wait-timeout", "180", "db", "redis", "mq", "object-store"],
        { env: composeEnv, timeout: 240_000 }
      );
    },
    { requires: ["api-image"] }
  );
  await gate.phase(
    "api-pytest",
    (run) =>
      run(
        "docker",
        [
          ...compose,
          "run",
          "--rm",
          "--no-deps",
          "api-tests",
          "pytest",
          "-o",
          "python_files=test_*.py tests.py",
          "--migrations",
          "--create-db",
          "-q",
        ],
        { env: composeEnv }
      ),
    { requires: ["api-services"] }
  );
  await gate.phase(
    "api-migration-boot",
    (run) =>
      run("docker", [...compose, "run", "--rm", "--no-deps", "api-tests", "python", "kitchen-smoke.py"], {
        env: composeEnv,
        timeout: 300_000,
      }),
    { requires: ["api-services"] }
  );
  const mcp = { cwd: join(root, "apps/mcp") };
  await gate.phase("mcp-sync", (run) => run("uv", ["sync", "--frozen", "--python", "3.12"], mcp));
  await gate.phase("mcp-pytest", (run) => run("uv", ["run", "--no-sync", "pytest", "-q"], mcp), {
    requires: ["mcp-sync"],
  });
  await gate.phase(
    "mcp-ruff",
    (run) => run("uv", ["run", "--no-sync", "ruff", "check", "sikku", "tests", "scripts/smoke_relations.py"], mcp),
    { requires: ["mcp-sync"] }
  );
  await gate.phase(
    "mcp-wheel-guidance",
    async (run) => {
      await run("uv", ["build", "--wheel", "--out-dir", join(gate.directory, "wheels")], mcp);
      await run(
        "python3",
        [
          "-c",
          'from pathlib import Path; from zipfile import ZipFile; import sys; p="sikku/skills/plane-project-management/SKILL.md"; w=list(Path(sys.argv[1]).glob("*.whl")); assert len(w)==1; z=ZipFile(w[0]); assert z.read(p)==Path(p).read_bytes(); print("Wheel guidance equals source")',
          join(gate.directory, "wheels"),
        ],
        mcp
      );
    },
    { requires: ["mcp-sync"] }
  );
  await gate.phase("mcp-docker-guidance", async (run) => {
    if (!builderCreated) throw new Error("Owned Docker builder unavailable");
    mcpContext = trackedContext(root, "apps/mcp/");
    images.add(mcpImage);
    await run("docker", [
      "buildx",
      "build",
      "--builder",
      id,
      "--load",
      "--progress=plain",
      "-t",
      mcpImage,
      mcpContext.directory,
    ]);
    await run("docker", [
      "run",
      "--rm",
      "--network",
      "none",
      "--entrypoint",
      "python",
      mcpImage,
      "-c",
      'from sikku.server import GUIDE; assert "Workspace slug:" in GUIDE and "AGENTS.md" in GUIDE; print("Docker bundled guidance present")',
    ]);
  });
  await gate.phase("backup-tests-ruff", async (run) => {
    await run("python3", [
      "-m",
      "unittest",
      "discover",
      "-s",
      "deployments/birdplane",
      "-p",
      "test_backup_postgres.py",
    ]);
    const files = ["deployments/birdplane/backup-postgres.py", "deployments/birdplane/test_backup_postgres.py"];
    await run("uvx", ["--from", "ruff==0.16.10", "ruff", "check", ...files]);
    await run("uvx", ["--from", "ruff==0.16.10", "ruff", "format", "--check", ...files]);
    await run("uvx", ["--from", "ruff==0.16.10", "ruff", "check", "scripts/kitchen/lib/api-smoke.py"]);
  });
  const docs = tracked.filter(
    (path) => path.endsWith(".md") && (!path.includes("/") || path.startsWith("docs/agents/"))
  );
  await gate.phase("root-docs-format", (run) => run("pnpm", ["exec", "oxfmt", "--check", ...docs]));
  await gate.phase("root-docs-links", async () => checkLinks(root, docs));
} finally {
  await gate.phase("cleanup", async (run) => {
    const failures = [];
    const cleanup = async (command, args, options) => {
      try {
        await run(command, args, { ...options, checkDisk: false });
      } catch (error) {
        failures.push(error.message);
      }
    };
    if (composeStarted) {
      await cleanup("docker", [...compose, "logs", "--no-color", "--tail", "100"], { env: composeEnv });
      await cleanup("docker", [...compose, "down", "--volumes", "--remove-orphans", "--timeout", "10"], {
        env: composeEnv,
      });
    }
    for (const image of images) {
      try {
        execFileSync("docker", ["image", "inspect", image], {
          encoding: "utf8",
          timeout: 30_000,
          stdio: ["ignore", "pipe", "pipe"],
        });
      } catch (error) {
        // A failed build may never have created its output tag; daemon errors still fail cleanup.
        if (!/No such (?:image|object)/i.test(String(error.stderr))) failures.push(error.message);
        continue;
      }
      // oxlint-disable-next-line no-await-in-loop -- Finish owned-image cleanup before removing the builder.
      await cleanup("docker", ["image", "rm", image]);
    }
    if (builderCreated) await cleanup("docker", ["buildx", "rm", "--force", id]);
    apiContext?.cleanup();
    mcpContext?.cleanup();
    if (failures.length) throw new Error(failures.join("\n"));
  });
  const report = gate.finish(phases);
  process.exitCode = report.result === "pass" ? 0 : 1;
}
