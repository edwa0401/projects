import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const PORT = 8791;
const dataFile = path.join(os.tmpdir(), `leadrescue-e2e-${process.pid}.json`);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "off" },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 900 } } },
  ],
  webServer: {
    command: `npm run build && python3 ../backend/local_server.py --port ${PORT} --reset`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { LOCAL_DATA_FILE: dataFile, AI_PROVIDER: "demo", STORE: "local" },
  },
});
