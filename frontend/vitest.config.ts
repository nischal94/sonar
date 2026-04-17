/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Kept separate from vite.config.ts so the dev/build pipeline stays minimal
// and the test config can evolve independently (add coverage, separate setup
// for integration vs unit, etc.).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: false, // don't try to parse CSS imports in tests
  },
});
