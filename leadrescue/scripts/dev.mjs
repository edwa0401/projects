// Starts the local API (demo mode) and the Vite dev server together. Ctrl+C stops both.
import { spawn } from "node:child_process";

const procs = [
  spawn("python3", ["backend/local_server.py"], { stdio: "inherit", env: process.env }),
  spawn("npm", ["--prefix", "frontend", "run", "dev"], { stdio: "inherit", env: process.env }),
];
const stop = () => procs.forEach((p) => p.kill("SIGTERM"));
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
procs.forEach((p) => p.on("exit", (code) => { if (code) { console.error(`[dev] process exited with ${code}`); stop(); process.exit(code); } }));
console.log("[dev] API: http://127.0.0.1:8787  App: http://localhost:5173");
