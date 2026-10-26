// Puts the reference render and the app screenshot next to each other. Usage: node side.mjs <ref.png> <app.png> <out.png>
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import { readFileSync } from "node:fs";
const [a, b, out] = process.argv.slice(2);
const uri = (f) => `data:image/png;base64,${readFileSync(f).toString("base64")}`;
const br = await chromium.launch();
const p = await br.newPage({ viewport: { width: 2000, height: 1200 } });
await p.setContent(`<body style="margin:0;background:#333;display:flex;gap:20px;align-items:flex-start;padding:0"><div><div style="color:#fff;font:14px sans-serif;padding:4px">reference</div><img src="${uri(a)}"></div><div><div style="color:#fff;font:14px sans-serif;padding:4px">app</div><img src="${uri(b)}"></div></body>`);
const el = await p.$("body");
await el.screenshot({ path: out });
await br.close();
