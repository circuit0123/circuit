// F4 screenshots: each Discover screen at 375px (dark and light) and 1280px, plus the reference next to the app (side-*.png).
// Needs the mock app on :3200 (`pnpm --filter @circuit/app exec playwright test -c playwright.mock.config.ts` starts it, or run
// `NEXT_DIST_DIR=.next-mock-e2e NEXT_PUBLIC_MOCK=1 NEXT_PUBLIC_ENV=dev ... next dev -p 3200` as in that config).
// Usage: node screenshots/f4/shots.mjs   (CHROME=/path/to/chrome to use a browser other than Playwright's own)
import { createRequire } from "node:module";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "../..");
const { chromium } = createRequire(join(root, "apps/app/package.json"))("@playwright/test");
const APP = process.env.APP ?? "http://localhost:3200";
const launch = () => chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});

/** Renders a reference file with a small stand-in for the support.js it expects (as screenshots/f3/ref-render.mjs does). */
async function reference(b, name, out, state) {
  let html = readFileSync(join(root, "docs/design-reference", `${name}.dc.html`), "utf8").replace('<script src="./support.js"></script>', "");
  const engine = `(function(){const get=(s,p)=>p.trim().split(".").reduce((o,k)=>o==null?o:o[k],s);const fill=(t,s)=>t.replace(/\\{\\{([^}]+)\\}\\}/g,(_,p)=>{const v=get(s,p);return typeof v==="function"||v==null?"":v;});
  function walk(n,s){if(n.nodeType===3){n.nodeValue=fill(n.nodeValue,s);return;}if(n.nodeType!==1)return;const t=n.tagName.toLowerCase();
  if(t==="sc-if"){const v=get(s,n.getAttribute("value").replace(/[{}]/g,""));[...n.childNodes].forEach(k=>{if(v){n.parentNode.insertBefore(k,n);walk(k,s);}});n.remove();return;}
  if(t==="sc-for"){const l=get(s,n.getAttribute("list").replace(/[{}]/g,""))||[];const as=n.getAttribute("as");const tpl=[...n.childNodes];l.forEach(i=>tpl.forEach(x=>{const c=x.cloneNode(true);n.parentNode.insertBefore(c,n);walk(c,{...s,[as]:i});}));n.remove();return;}
  if(t==="dc-import"){n.remove();return;}
  for(const a of [...n.attributes]){if(a.name.startsWith("on"))n.removeAttribute(a.name);else a.value=fill(a.value,s);}[...n.childNodes].forEach(c=>walk(c,s));}
  window.__render=v=>walk(document.querySelector("x-dc"),v);window.DCLogic=class{constructor(p){this.props=p||{};this.state={};}setState(x){Object.assign(this.state,x);}};})();`;
  html = html.replace('<script type="text/x-dc"', `<script>${engine}</script><script type="text/x-dc"`);
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.route("**/fonts.googleapis.com/**", (r) => r.abort());
  await p.setContent(html, { waitUntil: "load" });
  await p.evaluate((st) => {
    const C = new Function(`${document.querySelector("script[data-dc-script]").textContent}; return Component;`)();
    const c = new C({});
    if (st) Object.assign(c.state, st);
    window.__render(c.renderVals());
  }, state ?? null);
  await p.screenshot({ path: out });
  await p.close();
}

async function app(b, path, out, { width = 375, theme = "dark", then } = {}) {
  const p = await b.newPage({ viewport: { width, height: width > 900 ? 800 : 812 }, colorScheme: theme, reducedMotion: "reduce" });
  await p.route(/tile\.openstreetmap\.org/, (r) => r.abort());
  await p.goto(APP + path, { waitUntil: "networkidle" });
  await p.waitForTimeout(800);
  if (then) await then(p);
  await p.waitForTimeout(500);
  await p.screenshot({ path: out });
  await p.close();
}

async function side(b, a, c, out) {
  const uri = (f) => `data:image/png;base64,${readFileSync(f).toString("base64")}`;
  const p = await b.newPage({ viewport: { width: 860, height: 900 } });
  await p.setContent(`<body style="margin:0;background:#333;display:flex;gap:20px;align-items:flex-start;font:14px sans-serif;color:#fff"><div><div style="padding:4px">reference</div><img src="${uri(a)}" width="390"></div><div><div style="padding:4px">app</div><img src="${uri(c)}" width="375"></div></body>`);
  await (await p.$("body")).screenshot({ path: out });
  await p.close();
}

const pickMap = async (p) => { await p.getByRole("radio", { name: "Map" }).first().click(); await p.waitForTimeout(1500); await p.getByRole("button", { name: "Aravind Pathology, hiring" }).dispatchEvent("click"); };
const SCREENS = [
  { id: "discover-jobs", path: "/discover?s=jobs", ref: "Discover" },
  { id: "discover-people", path: "/discover?s=people", ref: "People" },
  { id: "discover-startups", path: "/discover?s=startups" },
  { id: "map", path: "/discover", ref: "Map", then: pickMap },
  { id: "job", path: "/discover/jobs/301", ref: "Job" },
  { id: "startup", path: "/startups/42" },
  { id: "startup-unclaimed-founder", path: "/startups/44?scenario=founder" },
  { id: "applications", path: "/discover/applications" },
  { id: "applicants", path: "/discover/jobs/301/applicants?scenario=founder" },
  { id: "filters", path: "/discover?s=jobs", then: (p) => p.getByRole("button", { name: "Filters", exact: true }).click() },
];

const b = await launch();
for (const s of SCREENS) {
  const dir = join(here, s.id);
  mkdirSync(dir, { recursive: true });
  for (const theme of ["dark", "light"]) await app(b, s.path, join(dir, `app-375-${theme}.png`), { theme, then: s.then });
  await app(b, s.path, join(dir, "app-1280-dark.png"), { width: 1280, then: s.then });
  if (s.ref) {
    await reference(b, s.ref, join(dir, "ref.png"));
    await side(b, join(dir, "ref.png"), join(dir, "app-375-dark.png"), join(dir, "side-375-dark.png"));
  }
  console.log("done", s.id);
}
await b.close();
