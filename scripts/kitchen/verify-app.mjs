#!/usr/bin/env node
/* Sequential startup, bounded readiness retries and ordered cleanup are intentional. */
/* eslint-disable no-await-in-loop */
import { spawn, execFileSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { mkdir, readFile, writeFile, rm, statfs, readdir } from "node:fs/promises";
import { accessSync, constants, openSync, closeSync } from "node:fs";
import { homedir } from "node:os";
import { createRequire } from "node:module";
import path from "node:path";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { assertDisposable } from "./verify-app/safety.mjs";
import { verify } from "./verify-app/lifecycle.mjs";
import { journeys } from "./verify-app/journeys.mjs";
import { observeBrowser, waitForLogin } from "./verify-app/browser.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const support = path.join(root, "scripts/kitchen/verify-app");
const storage = path.join(homedir(), ".local/share/kitchen/verify-app");
const worktreeHash = createHash("sha256").update(root).digest("hex").slice(0, 12);
// Do not inherit DATABASE_URL, cloud credentials, VITE_*, COMPOSE_* or PYTHONPATH.
const env = Object.fromEntries(
  ["PATH", "HOME", "USER", "DOCKER_HOST", "DOCKER_CONTEXT", "XDG_RUNTIME_DIR", "SSH_AUTH_SOCK"]
    .filter((k) => process.env[k])
    .map((k) => [k, process.env[k]])
);
env.CI = "true";
env.PYTHONDONTWRITEBYTECODE = "1";
const secrets = [];
const sanitize = (s) => secrets.reduce((text, secret) => text.replaceAll(secret, "[redacted]"), s);

async function command(bin, args, { cwd = root, extraEnv = {}, log, timeout = 900_000 } = {}) {
  return await new Promise((resolve, reject) => {
    const child = spawn(bin, args, {
      cwd,
      env: { ...env, ...extraEnv },
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    });
    let output = "";
    const collect = (data) => {
      output = (output + data).slice(-4_000_000);
    };
    child.stdout.on("data", collect);
    child.stderr.on("data", collect);
    const timer = setTimeout(() => {
      process.kill(-child.pid, "SIGKILL");
    }, timeout);
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", async (code, signal) => {
      clearTimeout(timer);
      output = sanitize(output);
      try {
        if (log) await writeFile(log, output, { mode: 0o600 });
        if (code !== 0)
          reject(new Error(`${bin} ${args[0]} failed (${signal ?? code}); ${log ?? output.slice(-1000)}`));
        else resolve(output.trim());
      } catch (error) {
        reject(error);
      }
    });
  });
}

async function disk() {
  const s = await statfs("/");
  const freeGiB = (s.bavail * s.bsize) / 1024 ** 3;
  if (freeGiB < 8) throw new Error(`Disk guard: ${freeGiB.toFixed(2)} GiB available; require >=8 GiB`);
  return { freeGiB: Number(freeGiB.toFixed(2)) };
}

function compose(config, args, options) {
  return command(
    "docker",
    [
      "compose",
      "--env-file",
      path.join(config.runtime, "compose.env"),
      "-p",
      config.project,
      "-f",
      path.join(support, "compose.yml"),
      ...args,
    ],
    options
  );
}

async function processStart(pid) {
  try {
    const stat = await readFile(`/proc/${pid}/stat`, "utf8");
    return stat.slice(stat.lastIndexOf(")") + 2).split(" ")[19];
  } catch (error) {
    if (error.code === "ENOENT") return undefined;
    throw error;
  }
}

async function cleanup(config) {
  if (
    !config.project.startsWith(`kitchen-verify-${worktreeHash}-`) ||
    path.dirname(config.runtime) !== storage ||
    path.basename(config.runtime) !== config.project
  )
    throw new Error("Refusing unknown runtime ownership");
  assertDisposable(config);
  if (config.webPid && config.webStart && (await processStart(config.webPid)) === config.webStart) {
    try {
      process.kill(-config.webPid, "SIGTERM");
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
    for (let i = 0; i < 50; i++) {
      try {
        process.kill(-config.webPid, 0);
      } catch (error) {
        if (error.code === "ESRCH") break;
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
      if (i === 49) {
        process.kill(-config.webPid, "SIGKILL");
      }
    }
  }
  await compose(config, ["down", "--volumes", "--remove-orphans", "--timeout", "15"]);
  for (const [kind, args] of [
    ["container", ["ps", "-aq"]],
    ["volume", ["volume", "ls", "-q"]],
    ["network", ["network", "ls", "-q"]],
  ]) {
    const ids = await command("docker", [...args, "--filter", `label=com.docker.compose.project=${config.project}`]);
    if (ids) throw new Error(`Cleanup left owned ${kind}: ${ids}`);
  }
  // Only the unique tag and builder made by this run are removable.
  const image = await command("docker", ["image", "ls", "-q", config.image]);
  if (image) await command("docker", ["image", "rm", config.image]);
  if (config.builderCreated) await command("docker", ["buildx", "rm", "--force", config.project]);
  await rm(config.runtime, { recursive: true });
  return {
    ownedContainers: 0,
    ownedVolumes: 0,
    ownedNetworks: 0,
    runtimeRemoved: true,
    imageRemoved: true,
    builderRemoved: true,
    ...(await disk()),
  };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help")) {
    console.log(
      "verify-app [--keep] [--upload --ticket <ID> [--pr <url>]] | --cleanup <run-name>\nRuns disposable browser/API/MCP journeys; requires pnpm install, Docker, uv and Node >=22.18."
    );
    return;
  }
  if (args[0] === "--cleanup" && args.length === 2 && /^kitchen-verify-[a-f0-9]{12}-[a-f0-9]{12}$/.test(args[1])) {
    const config = JSON.parse(await readFile(path.join(storage, args[1], "run.json"), "utf8"));
    console.log(JSON.stringify(await cleanup(config)));
    return;
  }
  const { values } = parseArgs({
    args,
    options: {
      keep: { type: "boolean" },
      upload: { type: "boolean" },
      ticket: { type: "string" },
      pr: { type: "string" },
    },
  });
  if (!values.upload && (values.ticket !== undefined || values.pr !== undefined))
    throw new Error("--ticket and --pr require --upload");
  let evidenceCommand;
  if (values.upload) {
    if (!/^[A-Z][A-Z0-9]*-[1-9][0-9]*$/.test(values.ticket ?? "")) throw new Error("--upload requires --ticket <ID>");
    if (values.pr && !/^https:\/\/github\.com\/[^/]+\/[^/]+\/pull\/[1-9][0-9]*$/.test(values.pr))
      throw new Error("--pr requires a GitHub PR URL");
    evidenceCommand = (env.PATH ?? "")
      .split(path.delimiter)
      .filter(Boolean)
      .map((dir) => path.join(dir, "evidence"))
      .find((file) => {
        try {
          accessSync(file, constants.X_OK);
          return true;
        } catch {
          return false;
        }
      });
    if (!evidenceCommand) throw new Error("evidence executable is required on PATH for --upload");
  }
  const sha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
  console.log(`Tested git SHA: ${sha}`);
  // Vite and some upstream Django startup paths load .env implicitly. Refuse them.
  for (const dir of [root, ...["api", "web", "mcp"].map((app) => path.join(root, "apps", app))]) {
    if (
      (await readdir(dir)).some((name) => name === ".env" || (name.startsWith(".env.") && !name.endsWith(".example")))
    )
      throw new Error(`Refusing checkout environment files in ${dir}; use a clean worktree`);
  }
  const start = Date.now();
  const before = await disk();
  const project = `kitchen-verify-${worktreeHash}-${randomBytes(6).toString("hex")}`;
  const runtime = path.join(storage, project);
  const evidence = path.join(root, ".kitchen/evidence/verify-app", sha, project);
  await mkdir(runtime, { recursive: true, mode: 0o700 });
  await mkdir(evidence, { recursive: true, mode: 0o700 });
  await mkdir(path.join(runtime, "static"), { mode: 0o700 });
  const password = randomBytes(24).toString("hex");
  const secret = randomBytes(32).toString("hex");
  secrets.push(password, secret);
  const config = {
    project,
    runtime,
    evidence,
    image: `${project}:test`,
    databaseUrl: `postgresql://verify:${password}@verify-db:5432/verify`,
    redisUrl: "redis://verify-redis:6379/0",
  };
  assertDisposable(config);
  await writeFile(
    path.join(runtime, "compose.env"),
    `VERIFY_DB_PASSWORD=${password}\nVERIFY_RUNTIME=${runtime}\nVERIFY_ROOT=${root}\nVERIFY_IMAGE=${config.image}\n`,
    { mode: 0o600 }
  );
  const save = () => writeFile(path.join(runtime, "run.json"), JSON.stringify(config), { mode: 0o600 });
  await save();
  const apiEnv = (origin) =>
    `VERIFY_PROJECT=${project}\nDJANGO_SETTINGS_MODULE=plane.settings.kitchen_verify\nPYTHONPATH=/verification:/code\nDATABASE_URL=${config.databaseUrl}\nREDIS_URL=${config.redisUrl}\nSECRET_KEY=${secret}\nWEB_URL=${origin}\nAPP_BASE_URL=${origin}\nAPP_BASE_PATH=\nCORS_ALLOWED_ORIGINS=${origin}\nENABLE_EMAIL_PASSWORD=1\nDISABLE_SIGNUP=1\nINSTANCE_CHANGELOG_URL=\n`;
  await writeFile(path.join(runtime, "api.env"), apiEnv("http://127.0.0.1"), { mode: 0o600 });
  const ctx = {
    ...config,
    command,
    compose: (composeArgs, opts) => compose(config, composeArgs, opts),
    env,
    secrets,
    disk,
    browserErrors: [],
    browserDiagnostics: [],
  };
  let interrupted = false;
  const interrupt = () => {
    interrupted = true;
  };
  process.once("SIGINT", interrupt);
  process.once("SIGTERM", interrupt);
  const result = await verify({
    journeys: [
      [
        "isolated build, empty database migrations and D12 seed",
        async () => {
          await command("docker", ["buildx", "create", "--name", project, "--driver", "docker-container"]);
          config.builderCreated = true;
          await save();
          await command(
            "docker",
            [
              "buildx",
              "build",
              "--builder",
              project,
              "--load",
              "-t",
              config.image,
              "-f",
              path.join(support, "Dockerfile"),
              root,
            ],
            { log: path.join(evidence, "build.log") }
          );
          await disk();
          await compose(config, ["up", "-d", "--wait", "verify-db", "verify-redis"], {
            log: path.join(evidence, "dependencies.log"),
          });
          await compose(config, ["run", "--rm", "--no-deps", "api", "python", "manage.py", "migrate", "--noinput"], {
            log: path.join(evidence, "migrations.log"),
          });
          await compose(
            config,
            ["run", "--rm", "--no-deps", "api", "sh", "-c", "python manage.py shell < /verification/seed.py"],
            { log: path.join(evidence, "seed.log") }
          );
          const seed = JSON.parse(await readFile(path.join(runtime, "seed.json"), "utf8"));
          secrets.push(seed.admin, seed.user);
          ctx.seed = seed;
          return "migrations applied to empty unique DB; D12 accounts seeded";
        },
      ],
      [
        "web and MCP prerequisites",
        async () => {
          await command("pnpm", ["turbo", "run", "build", "--filter=web^..."], {
            log: path.join(evidence, "web-dependencies.log"),
          });
          await disk();
          // Use an allocated ephemeral loopback port; strictPort makes a race fail closed.
          const { createServer } = await import("node:net");
          const server = createServer();
          await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
          const port = server.address().port;
          await new Promise((resolve) => server.close(resolve));
          ctx.web = `http://127.0.0.1:${port}`;
          await writeFile(path.join(runtime, "api.env"), apiEnv(ctx.web), { mode: 0o600 });
          await compose(config, ["up", "-d", "api", "worker"]);
          const apiPort = (await compose(config, ["port", "api", "8000"])).split(":").at(-1);
          ctx.api = `http://127.0.0.1:${apiPort}`;
          const webLog = openSync(path.join(evidence, "web.log"), "a", 0o600);
          const web = spawn(
            "pnpm",
            [
              "--filter=web",
              "exec",
              "react-router",
              "dev",
              "--host",
              "127.0.0.1",
              "--port",
              String(port),
              "--strictPort",
            ],
            {
              cwd: root,
              env: {
                ...env,
                VITE_API_BASE_URL: ctx.api,
                VITE_WEB_BASE_URL: ctx.web,
                VITE_ADMIN_BASE_URL: ctx.web,
                VITE_SPACE_BASE_URL: ctx.web,
                VITE_LIVE_BASE_URL: ctx.web,
                VITE_ADMIN_BASE_PATH: "/god-mode",
                VITE_SPACE_BASE_PATH: "/spaces",
                VITE_LIVE_BASE_PATH: "/live",
              },
              detached: true,
              stdio: ["ignore", webLog, webLog],
            }
          );
          closeSync(webLog);
          web.on("error", (error) => {
            ctx.webError = error;
          });
          config.webPid = web.pid;
          config.webStart = await processStart(web.pid);
          await save();
          web.unref();

          await command(
            "npm",
            [
              "install",
              "--prefix",
              path.join(runtime, "browser"),
              "--no-package-lock",
              "--ignore-scripts",
              "playwright@1.58.2",
            ],
            { log: path.join(evidence, "browser-install.log") }
          );
          await command("node", [path.join(runtime, "browser/node_modules/playwright/cli.js"), "install", "chromium"], {
            log: path.join(evidence, "browser-download.log"),
          });
          await command("uv", ["sync", "--project", path.join(root, "apps/mcp"), "--locked", "--no-dev"], {
            extraEnv: { UV_PROJECT_ENVIRONMENT: path.join(runtime, "mcp-venv") },
            log: path.join(evidence, "mcp-install.log"),
          });
          for (const url of [ctx.api + "/api/instances/", ctx.web]) {
            let ready = false;
            for (let i = 0; i < 120; i++) {
              if (ctx.webError) throw ctx.webError;
              if (interrupted) throw new Error("Interrupted");
              try {
                if ((await fetch(url, { signal: AbortSignal.timeout(5000) })).ok) {
                  ready = true;
                  break;
                }
              } catch {
                /* bounded startup retry */
              }
              await new Promise((resolve) => setTimeout(resolve, 1000));
            }
            if (!ready) throw new Error(`Readiness timed out: ${url}`);
          }
          const require = createRequire(path.join(ctx.runtime, "browser/package.json"));
          const { chromium } = require("playwright");
          ctx.browser = await chromium.launch({ headless: true });
          ctx.page = await ctx.browser.newPage({ viewport: { width: 1440, height: 1000 } });
          ctx.page.setDefaultTimeout(60_000);
          const diagnostics = observeBrowser(ctx.page);
          ctx.browserErrors = diagnostics.pageErrors;
          ctx.browserDiagnostics = diagnostics.events;
          const login = await waitForLogin(ctx.page, ctx.web);
          return { web: ctx.web, api: ctx.api, login };
        },
      ],
      [
        "browser startup regression tests",
        async () => {
          await command("node", ["scripts/kitchen/run-tests.mjs", "scripts/kitchen/verify-app/browser.test.mjs"], {
            extraEnv: { VERIFY_BROWSER_PACKAGE: path.join(runtime, "browser/package.json") },
            log: path.join(evidence, "browser-tests.log"),
          });
          return "real Chromium regression fixtures passed with zero skips/todos";
        },
      ],
      ...journeys(ctx).map(([name, action]) => [
        name,
        async () => {
          if (interrupted) throw new Error("Interrupted");
          return await action();
        },
      ]),
    ],
    cleanup: async () => {
      try {
        await compose(config, ["logs", "--no-color", "--tail", "200"], { log: path.join(evidence, "services.log") });
        const owned = (await compose(config, ["ps", "-q"])).split(/\s+/).filter(Boolean);
        if (owned.length)
          await command(
            "docker",
            ["stats", "--no-stream", "--format", "{{.Name}} CPU={{.CPUPerc}} memory={{.MemUsage}}", ...owned],
            { log: path.join(evidence, "resources.log") }
          );
      } finally {
        try {
          if (ctx.browser) {
            try {
              await ctx.page.screenshot({ path: path.join(evidence, "last-page.png") });
              await writeFile(path.join(evidence, "last-page.html"), sanitize(await ctx.page.content()), {
                mode: 0o600,
              });
            } finally {
              try {
                await Promise.all([
                  writeFile(path.join(evidence, "browser-errors.log"), sanitize(ctx.browserErrors.join("\n")), {
                    mode: 0o600,
                  }),
                  writeFile(
                    path.join(evidence, "browser-diagnostics.log"),
                    sanitize(ctx.browserDiagnostics.join("\n")),
                    {
                      mode: 0o600,
                    }
                  ),
                ]);
              } finally {
                await ctx.browser.close();
              }
            }
          }
        } finally {
          if (!args.includes("--keep")) ctx.cleanup = await cleanup(config);
          else console.log(`Retained stack. Cleanup: node scripts/kitchen/verify-app.mjs --cleanup ${project}`);
        }
      }
      return args.includes("--keep") ? { retained: project } : ctx.cleanup;
    },
    report: (r) =>
      console.log(`${r.result.toUpperCase()} ${r.name} (${r.seconds.toFixed(2)}s)${r.error ? `: ${r.error}` : ""}`),
  });
  const summary = {
    sha,
    dirty:
      !execFileSync("git", ["ls-files", "scripts/kitchen/verify-app.mjs"], { cwd: root, encoding: "utf8" }).trim() ||
      Boolean(
        execFileSync("git", ["status", "--porcelain", "--untracked-files=all"], { cwd: root, encoding: "utf8" })
          .split("\n")
          .filter((line) => line && !line.slice(3).startsWith(".kitchen/")).length
      ),
    project,
    browserErrorCount: ctx.browserErrors.length,
    durationSeconds: (Date.now() - start) / 1000,
    diskBefore: before,
    diskAfter: await disk(),
    ...result,
  };
  await writeFile(path.join(evidence, "results.json"), sanitize(JSON.stringify(summary, null, 2)));
  console.log(`Evidence: ${evidence}`);
  if (args.includes("--upload")) {
    // The result schema contains synthetic data and redacted errors. Screenshots
    // need visual review before a separate evidence put; never auto-publish logs.
    // The evidence service accepts LOG/TXT, not JSON extensions.
    const publicLines = [
      `Tested git SHA ${sha}`,
      `Clean tracked tree ${!summary.dirty}`,
      `Duration seconds ${summary.durationSeconds}`,
      ...result.results.map((r) => `${r.result.toUpperCase()} ${r.name} (${r.seconds.toFixed(2)}s)`),
    ];
    // Publish statuses only: structured details/raw errors stay local and can
    // resemble credential assignments to the evidence service's secret scanner.
    await writeFile(path.join(evidence, "results.log"), publicLines.join("\n") + "\n");
    for (const file of ["results.log"]) {
      console.log(
        await command(evidenceCommand, [
          "put",
          path.join(evidence, file),
          "--ticket",
          values.ticket,
          ...(values.pr ? ["--pr", values.pr] : []),
          "--note",
          `Disposable verification ${file} at ${sha}`,
          "--markdown",
        ])
      );
    }
  }
  process.removeListener("SIGINT", interrupt);
  process.removeListener("SIGTERM", interrupt);
  console.log(`Exit code: ${result.exitCode}`);
  process.exitCode = result.exitCode;
}

main().catch((error) => {
  console.error(sanitize(error.message));
  console.error("Exit code: 1");
  process.exitCode = 1;
});
