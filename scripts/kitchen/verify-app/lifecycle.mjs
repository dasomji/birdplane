/* Journeys depend on earlier product data; run them in order. */
/* eslint-disable no-await-in-loop */
export async function verify({ journeys, cleanup, report = () => {} }) {
  const results = [];
  const run = async (name, action) => {
    const start = Date.now();
    try {
      const detail = await action();
      results.push({ name, result: "pass", seconds: (Date.now() - start) / 1000, detail });
    } catch (error) {
      results.push({ name, result: "fail", seconds: (Date.now() - start) / 1000, error: error.message });
    }
    report(results.at(-1));
  };
  try {
    for (const [index, [name, action]] of journeys.entries()) {
      await run(name, action);
      // Later journeys may depend on resources created by earlier journeys.
      if (results.at(-1).result === "fail") {
        for (const [blockedName] of journeys.slice(index + 1)) {
          const blocked = {
            name: blockedName,
            result: "blocked",
            seconds: 0,
            error: `Depends on failed journey: ${name}`,
          };
          results.push(blocked);
          report(blocked);
        }
        break;
      }
    }
  } finally {
    await run("cleanup", cleanup);
  }
  return { exitCode: results.some((r) => r.result === "fail") ? 1 : 0, results };
}
