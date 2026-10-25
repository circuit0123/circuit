// A stand-in for GET /api/config, started by Playwright so the two test builds can read feature flags at build time.
// Usage: node mock-config.mjs <port> <on|off>   (on = every feature on, off = every feature off)
import http from "node:http";

const [port, mode] = [Number(process.argv[2]), process.argv[3]];
const on = mode === "on";
const features = Object.fromEntries(["pulse", "daily_drop", "circuits", "investor_mode", "partner_mode", "promotions", "payments"].map((f) => [f, on]));

http
  .createServer((req, res) => {
    if (req.url?.startsWith("/api/config")) {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ env: "test", beta_mode: true, beta_access: false, features }));
    }
    res.writeHead(404).end();
  })
  .listen(port, "127.0.0.1", () => console.log(`mock config (${mode}) on ${port}`));
