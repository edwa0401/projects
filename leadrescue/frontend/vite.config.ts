/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.LEADRESCUE_API_URL ?? "http://127.0.0.1:8787";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: apiTarget, changeOrigin: false } } },
  build: { sourcemap: false, target: "es2020" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    css: false,
  },
});
