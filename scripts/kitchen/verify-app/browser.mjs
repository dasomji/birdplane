/* Startup retries are sequential and share one deadline. */
/* eslint-disable no-await-in-loop */
const emailSelector = 'input[type="email"]';

export async function waitForLogin(page, url, { timeout = 60_000, attemptTimeout = 10_000 } = {}) {
  const start = Date.now();
  let invalidations = 0;
  let attempts = 0;
  const outdated = (response) => {
    if (
      response.status() === 504 &&
      response.statusText() === "Outdated Optimize Dep" &&
      new URL(response.url()).origin === new URL(url).origin
    )
      invalidations++;
  };
  page.on("response", outdated);
  const remaining = () => Math.max(1, timeout - (Date.now() - start));
  try {
    while (true) {
      const before = invalidations;
      attempts++;
      try {
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: remaining() });
        while (true) {
          try {
            await page
              .locator(emailSelector)
              .waitFor({ state: "visible", timeout: Math.min(attemptTimeout, remaining()) });
            // Let startup requests/optimizer reloads finish before the first form interaction.
            await page.waitForLoadState("networkidle", { timeout: remaining() });
            await page.locator(emailSelector).waitFor({ state: "visible", timeout: remaining() });
            return { attempts, optimizerInvalidations: invalidations, seconds: (Date.now() - start) / 1000 };
          } catch (error) {
            if (invalidations > before || error.name !== "TimeoutError" || Date.now() - start >= timeout) throw error;
            // Keep waiting on this document if compilation is still in progress.
          }
        }
      } catch (error) {
        // A rejected startup module can prevent Vite's HMR client itself loading.
        // Waiting longer cannot repair that document; only retry this known dev-server failure.
        if (invalidations === before || Date.now() - start >= timeout) throw error;
      }
    }
  } finally {
    page.off("response", outdated);
  }
}

const diagnosticURL = (value) => {
  try {
    const url = new URL(value);
    return `${url.origin}${url.pathname}`;
  } catch {
    return "[invalid URL]";
  }
};

const record = (target, value) => {
  target.push(`${new Date().toISOString()} ${value.slice(0, 2000)}`);
  if (target.length > 500) target.shift();
};

export function observeBrowser(page) {
  const events = [];
  const pageErrors = [];
  page.on("console", (message) => record(events, `console ${message.type()} ${message.text()}`));
  page.on("pageerror", (error) => record(pageErrors, error?.stack || String(error)));
  page.on("requestfailed", (request) =>
    record(events, `requestfailed ${request.method()} ${diagnosticURL(request.url())} ${request.failure()?.errorText}`)
  );
  page.on("response", (response) => {
    if (response.status() >= 400)
      record(events, `response ${response.status()} ${response.statusText()} ${diagnosticURL(response.url())}`);
  });
  return { events, pageErrors };
}
