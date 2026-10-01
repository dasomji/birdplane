import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@/app": fileURLToPath(new URL("./app", import.meta.url)),
      "@/styles": fileURLToPath(new URL("./styles", import.meta.url)),
      "next/navigation": fileURLToPath(new URL("./app/compat/next/navigation.ts", import.meta.url)),
      "next/link": fileURLToPath(new URL("./app/compat/next/link.tsx", import.meta.url)),
      "next/script": fileURLToPath(new URL("./app/compat/next/script.tsx", import.meta.url)),
      "@/helpers": fileURLToPath(new URL("./helpers", import.meta.url)),
      "@": fileURLToPath(new URL("./core", import.meta.url)),
    },
  },
  test: { environment: "node", include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"] },
});
