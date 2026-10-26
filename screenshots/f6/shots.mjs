// F6 screenshots: profiles, the build log composer and post view, and Settings at 375px (dark and light) and 1280px, plus the reference next to the app (side-*.png).
// Needs the mock app on :3200 (`pnpm --filter @circuit/app exec playwright test -c playwright.mock.config.ts` starts it, or run
// `NEXT_DIST_DIR=.next-mock-e2e NEXT_PUBLIC_MOCK=1 NEXT_PUBLIC_ENV=dev ... next dev -p 3200` as in that config).
// Usage: node screenshots/f6/shots.mjs   (CHROME=/path/to/chrome to use a browser other than Playwright's own)
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

/** Adds two photos (made in the page, so no files are needed) and describes the first. */
const photos = async (p) => {
  const files = await p.evaluate(async () => {
    const out = [];
    for (const [w, h, a, b] of [[1600, 1200, "#1e5a46", "#c8b478"], [1200, 1200, "#2b2350", "#8e8cff"]]) {
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const g = c.getContext("2d"); g.fillStyle = a; g.fillRect(0, 0, w, h); g.fillStyle = b; g.fillRect(w / 8, h / 6, (w * 3) / 4, (h * 2) / 3);
      const blob = await new Promise((r) => c.toBlob(r, "image/png"));
      let bin = ""; for (const x of new Uint8Array(await blob.arrayBuffer())) bin += String.fromCharCode(x);
      out.push({ name: `p${w}.png`, data: btoa(bin) });
    }
    return out;
  });
  await p.getByTestId("photo-input").setInputFiles(files.map((f) => ({ name: f.name, mimeType: "image/png", buffer: Buffer.from(f.data, "base64") })));
  await p.getByRole("textbox", { name: "What did you build?" }).fill("Farm map now works offline. Loads from one GeoJSON file.");
  await p.waitForTimeout(1500);
};
const SCREENS = [
  { id: "profile", path: "/profile", ref: "Profile" },
  { id: "profile-to-fill-in", path: "/profile?scenario=profile_empty" },
  { id: "profile-under18", path: "/profile?scenario=under18" },
  { id: "person", path: "/members/2", ref: "Person" },
  { id: "person-private", path: "/members/11" },
  { id: "compose", path: "/compose", ref: "Composer" },
  { id: "compose-photos", path: "/compose", then: photos },
  { id: "post", path: "/posts/101" },
  { id: "post-own", path: "/posts/201" },
  { id: "settings", path: "/settings", ref: "Settings" },
  { id: "appearance", path: "/settings/appearance", ref: "Appearance" },
  { id: "privacy", path: "/settings/privacy" },
  { id: "privacy-under18", path: "/settings/privacy?scenario=under18" },
  { id: "notifications", path: "/settings/notifications" },
  { id: "edit-profile", path: "/settings/profile" },
  { id: "export", path: "/settings/export?scenario=export_ready" },
  { id: "delete", path: "/settings/delete" },
  { id: "help", path: "/settings/help" },
];

const b = await launch();
for (const s of SCREENS) {
  const dir = join(here, s.id);
  mkdirSync(dir, { recursive: true });
  for (const theme of ["dark", "light"]) await app(b, s.path, join(dir, `app-375-${theme}.png`), { theme, then: s.then });
  await app(b, s.path, join(dir, "app-1280-dark.png"), { width: 1280, then: s.then });
  if (s.ref) {
    await reference(b, s.ref, join(dir, "ref.png"), s.refState);
    await side(b, join(dir, "ref.png"), join(dir, "app-375-dark.png"), join(dir, "side-375-dark.png"));
  }
  console.log("done", s.id);
}
await b.close();
