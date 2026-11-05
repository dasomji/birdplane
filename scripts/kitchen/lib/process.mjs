import { spawn, execFileSync } from "node:child_process";
import { appendFileSync, mkdirSync, readFileSync, statfsSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { isolatedEnvironment } from "./environment.mjs";

const GiB = 1024 ** 3;
export function freeDisk() {
  const s = statfsSync("/");
  return s.bavail * s.bsize;
}
export function assertDisk() {
  const free = freeDisk();
  if (free < 8 * GiB) throw new Error(`Disk reserve: ${(free / GiB).toFixed(2)} GiB free; need >=8 GiB`);
}
export function execute(
  command,
  args = [],
  { cwd = process.cwd(), env = {}, log, timeout = 30 * 60_000, checkDisk = true } = {}
) {
  console.log(`$ ${command} ${args.map((arg) => JSON.stringify(arg)).join(" ")}`);
  return new Promise((resolve, reject) => {
    if (checkDisk) assertDisk();
    const child = spawn(command, args, {
      cwd,
      env: { ...isolatedEnvironment(), ...env },
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let reason;
    let killTimer;
    const stop = (message) => {
      if (reason) return;
      reason = message;
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch (error) {
        if (error.code !== "ESRCH") throw error;
      }
      killTimer = setTimeout(() => {
        try {
          process.kill(-child.pid, "SIGKILL");
        } catch (error) {
          if (error.code !== "ESRCH") throw error;
        }
      }, 5000);
    };
    const interrupt = () => stop("Interrupted");
    process.once("SIGINT", interrupt);
    process.once("SIGTERM", interrupt);
    const diskTimer = setInterval(() => {
      if (checkDisk && freeDisk() < 8 * GiB) stop("Disk reserve fell below 8 GiB");
    }, 1000);
    const timer = setTimeout(() => stop(`Timeout after ${timeout / 1000}s`), timeout);
    for (const stream of [child.stdout, child.stderr])
      stream.on("data", (data) => {
        process.stdout.write(data);
        if (log) appendFileSync(log, data);
      });
    const finish = (error) => {
      clearInterval(diskTimer);
      clearTimeout(timer);
      clearTimeout(killTimer);
      process.removeListener("SIGINT", interrupt);
      process.removeListener("SIGTERM", interrupt);
      if (error) return reject(error);
      resolve();
    };
    child.once("error", finish);
    child.once("close", (code, signal) =>
      finish(code === 0 && !reason ? undefined : new Error(reason ?? `Exit ${code ?? signal}: ${command}`))
    );
  });
}

export class Gate {
  constructor(root, name) {
    this.root = root;
    this.sha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
    this.dirty = execFileSync("git", ["status", "--porcelain"], { cwd: root, encoding: "utf8" }).trim().length > 0;
    this.started = Date.now();
    this.initialFree = freeDisk();
    this.minimumFree = this.initialFree;
    this.peakRssKiB = 0;
    this.peakHostUsedKiB = 0;
    this.results = [];
    this.directory = join(
      root,
      ".kitchen/evidence",
      `${name}-${new Date().toISOString().replaceAll(":", "-")}-${process.pid}`
    );
    mkdirSync(this.directory, { recursive: true });
    this.sample = setInterval(() => {
      this.minimumFree = Math.min(this.minimumFree, freeDisk());
      const rows = execFileSync("ps", ["-eo", "pid=,ppid=,rss="], { encoding: "utf8" })
        .trim()
        .split("\n")
        .map((line) => line.trim().split(/\s+/).map(Number));
      const descendants = new Set([process.pid]);
      let previous;
      do {
        previous = descendants.size;
        for (const [pid, parent] of rows) if (descendants.has(parent)) descendants.add(pid);
      } while (previous !== descendants.size);
      this.peakRssKiB = Math.max(
        this.peakRssKiB,
        rows.filter(([pid]) => descendants.has(pid)).reduce((sum, row) => sum + row[2], 0)
      );
      const mem = readFileSync("/proc/meminfo", "utf8");
      this.peakHostUsedKiB = Math.max(
        this.peakHostUsedKiB,
        Number(mem.match(/^MemTotal:\s+(\d+)/m)[1]) - Number(mem.match(/^MemAvailable:\s+(\d+)/m)[1])
      );
    }, 1000);
  }
  async phase(name, work, { requires = [] } = {}) {
    const start = Date.now();
    const log = join(this.directory, `${String(this.results.length + 1).padStart(2, "0")}-${name}.log`);
    console.log(`\n=== ${name} ===`);
    let result = "pass";
    let detail;
    try {
      if (
        requires.some(
          (dependency) => !this.results.some((phase) => phase.name === dependency && phase.result === "pass")
        )
      ) {
        result = "blocked";
        throw new Error(`Required phases did not pass: ${requires.join(", ")}`);
      }
      await work((command, args, options = {}) => execute(command, args, { cwd: this.root, ...options, log }));
    } catch (error) {
      if (result !== "blocked") result = "fail";
      detail = error.message;
      appendFileSync(log, `${detail}\n`);
    }
    this.results.push({ name, result, seconds: +((Date.now() - start) / 1000).toFixed(2), detail });
    console.log(JSON.stringify(this.results.at(-1)));
    return result === "pass";
  }
  finish(expectedNames) {
    clearInterval(this.sample);
    const complete =
      expectedNames.length === this.results.length &&
      expectedNames.every((name) => this.results.some((phase) => phase.name === name));
    const report = {
      sha: this.sha,
      dirty: this.dirty,
      time: new Date().toISOString(),
      seconds: +((Date.now() - this.started) / 1000).toFixed(2),
      result: complete && this.results.every((phase) => phase.result === "pass") ? "pass" : "blocked",
      peakProcessTreeRssMiB: +(this.peakRssKiB / 1024).toFixed(1),
      peakHostUsedMiB: +(this.peakHostUsedKiB / 1024).toFixed(1),
      peakDiskGrowthGiB: +((this.initialFree - this.minimumFree) / GiB).toFixed(2),
      minimumFreeGiB: +(this.minimumFree / GiB).toFixed(2),
      phases: this.results,
    };
    writeFileSync(join(this.directory, "results.json"), `${JSON.stringify(report, null, 2)}\n`);
    console.table(this.results);
    console.log(`Report: ${this.directory}/results.json\nAggregate: ${report.result}`);
    return report;
  }
}
