import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@/helpers": fileURLToPath(new URL("./helpers", import.meta.url)),
      "@": fileURLToPath(new URL("./core", import.meta.url)),
    },
  },
  test: { environment: "node", include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"] },
});
