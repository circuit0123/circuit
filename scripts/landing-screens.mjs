// Renders the phone screens used on the landing site from docs/design-reference/*.dc.html.
// Usage: node scripts/landing-screens.mjs [screen-id ...]      (or: make landing-screens)
// Output: apps/landing/public/screens/<id>.{avif,webp,png}  (780x1688 px = 390x844 CSS px at 2x, each <= 150 KB)
//
// The reference files are a mock's template language (`{{x}}`, <sc-for>, <sc-if>, <dc-import>) and need a support.js that is not in the repo,
// so this script expands that small syntax itself, runs each file's own `renderVals()`, and screenshots the phone element in Chromium.
// REFERENCE ONLY: nothing from docs/design-reference is copied into the product; only the rendered pictures are.
// Reference copy that could be mistaken for a real startup, person or number is replaced first (REPLACE below), and every picture carries a
// small "Sample data" label. Needs: pnpm install (Playwright, Geist font), python3 with Pillow (AVIF + WebP support).
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ref = path.join(root, "docs/design-reference");
const out = path.join(root, "apps/landing/public/screens");
const landing = createRequire(path.join(root, "apps/landing/package.json"));
const { chromium } = landing("@playwright/test");
const fonts = path.join(root, "apps/landing/node_modules/geist/dist/fonts");

const MAX_BYTES = 150 * 1024;

/** Which reference file becomes which picture. `state` sets the mock's starting state (e.g. which Daily Drop card is on top). */
const SCREENS = {
  "home-main": { file: "Main" },
  "home-match": { file: "Main", state: { i: 1 } }, // the Bridge-match card
  "discover-jobs": { file: "Discover" },
  map: { file: "Map" },
  circuits: { file: "Circuits" },
  job: { file: "Job" },
  people: { file: "People" },
  inbox: { file: "Inbox" },
  chat: { file: "Chat" },
  "investor-picks": { file: "InvestorHome" },
  "partner-home": { file: "PartnerHome" },
};

/** Names in the reference that could belong to a real startup or person. Startups become "Sample <sector> Co."; people keep a first name only. Longest first. */
const REPLACE = [
  ["Tatvagrid · Agritech", "Sample Agritech Co."], ["Sutragrid · Logistics", "Sample Logistics Co."], ["Zetapulse · Deeptech", "Sample Deeptech Co."],
  ["Tatvagrid", "Sample Agritech Co."], ["Sutragrid", "Sample Logistics Co."], ["Zetapulse", "Sample Deeptech Co."],
  ["Medisetu", "Sample Healthtech Co."], ["Kalam Labs", "Sample Edtech Co."], ["Neerflow", "Sample Climate Co."], ["Kaveri Tech", "Sample Incubator"], ["RSVPs 90% full", "RSVPs open"],
  ["Sakthi Vel", "Sakthi"], ["Kavya Raman", "Kavya"], ["Harini Prasad", "Harini"], ["Yamini Iyer", "Yamini"], ["Meera Krishnan", "Meera"],
  ["Farhan Ali", "Farhan"], ["Divya Subramanian", "Divya"], ["Arun Prakash", "Arun"], ["Ishaan Reddy", "Ishaan"],
];

const read = (name) => fs.readFileSync(path.join(ref, `${name}.dc.html`), "utf8");
const redact = (s) => REPLACE.reduce((acc, [from, to]) => acc.split(from).join(to), s);

/** Runs the file's `class Component extends DCLogic` and returns what renderVals() gives (functions are dropped: the picture is a still). */
function valsOf(source, props, state) {
  const code = source.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/)[1];
  class DCLogic { constructor(p) { this.props = p ?? {}; this.state = {}; } setState() {} }
  const Component = new Function("DCLogic", `${code}; return Component;`)(DCLogic);
  const c = new Component(props);
  Object.assign(c.state, state);
  return JSON.parse(JSON.stringify(c.renderVals()));
}

/** The template of a file: what sits between <x-dc> and </x-dc>. */
const templateOf = (source) => source.match(/<x-dc>([\s\S]*?)<\/x-dc>/)[1];

/** `<dc-import name="TabBar" active="x" partner="{{ true }}">` becomes the tab bar's own template and values. */
function importsOf(source) {
  const found = {};
  for (const m of source.matchAll(/<dc-import name="(\w+)"([^>]*)>/g)) {
    const props = {};
    for (const a of m[2].matchAll(/(\w+)="([^"]*)"/g)) if (!a[1].startsWith("hint")) props[a[1]] = a[2].replace(/\{\{\s*|\s*\}\}/g, "") === "true" ? true : a[2];
    const s = redact(read(m[1]));
    found[m[1]] = { html: templateOf(s).replace(/<helmet>[\s\S]*?<\/helmet>/, ""), vals: valsOf(s, props) };
  }
  return found;
}

/** Runs in the browser: expands {{x}}, <sc-for>, <sc-if> and <dc-import> in the loaded template. */
function expand({ vals, imports }) {
  const get = (expr, scope) => {
    const e = expr.trim();
    if (e === "true") return true;
    if (e === "false") return false;
    return e.split(".").reduce((v, k) => (v == null ? v : v[k]), scope);
  };
  const text = (s, scope) => s.replace(/\{\{([^}]*)\}\}/g, (_, e) => String(get(e, scope) ?? ""));
  const walk = (parent, scope) => {
    for (const el of Array.from(parent.children)) {
      const tag = el.tagName.toLowerCase();
      if (tag === "sc-for") {
        const items = get(el.getAttribute("list").replace(/[{}]/g, ""), scope) ?? [];
        const frag = document.createDocumentFragment();
        for (const item of items) {
          const clone = el.cloneNode(true);
          walk(clone, { ...scope, [el.getAttribute("as")]: item });
          frag.append(...clone.childNodes);
        }
        el.replaceWith(frag);
      } else if (tag === "sc-if") {
        const on = get(el.getAttribute("value").replace(/[{}]/g, ""), scope);
        if (on) { walk(el, scope); el.replaceWith(...el.childNodes); } else el.remove();
      } else if (tag === "dc-import") {
        const imp = imports[el.getAttribute("name")];
        const box = document.createElement("div");
        box.innerHTML = imp.html;
        walk(box, imp.vals);
        el.replaceWith(...box.childNodes);
      } else {
        for (const a of Array.from(el.attributes)) {
          if (/^on/i.test(a.name)) el.removeAttribute(a.name);
          else if (a.value.includes("{{")) el.setAttribute(a.name, text(a.value, scope));
        }
        const direct = Array.from(el.childNodes).filter((n) => n.nodeType === 3);
        for (const n of direct) if (n.data.includes("{{")) n.data = text(n.data, scope);
        walk(el, scope);
      }
    }
  };
  const app = document.querySelector("x-dc");
  for (const n of Array.from(app.childNodes)) if (n.nodeType === 3 && n.data.includes("{{")) n.data = text(n.data, vals);
  walk(app, vals);
  app.querySelector("helmet")?.remove();
}

const fontCss = [
  ["Geist", 400, "Geist-Regular"], ["Geist", 500, "Geist-Medium"], ["Geist", 600, "Geist-SemiBold"],
  ["Geist Mono", 400, "GeistMono-Regular"], ["Geist Mono", 500, "GeistMono-Medium"],
].map(([family, weight, file]) => `@font-face{font-family:'${family}';font-weight:${weight};src:url('file://${fonts}/${family === "Geist" ? "geist-sans" : "geist-mono"}/${file}.woff2') format('woff2')}`).join("\n");

/** A small label in the empty strip above the header: the pictures show sample data, never real people or numbers. */
const LABEL = `<div style="position:absolute;left:0;right:0;top:6px;text-align:center;font:500 11px/1 Geist,system-ui,sans-serif;letter-spacing:.04em;color:#8A8390;z-index:9">Sample data</div>`;

/** PNG from the screenshot, AVIF and WebP at the best quality that fits in MAX_BYTES (PNG goes to a palette if it must). */
const ENCODE = `
import sys
from PIL import Image
src, base, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
im = Image.open(src).convert("RGB")
def fit(path, save, qualities):
    for q in qualities:
        save(q)
        import os
        if os.path.getsize(path) <= limit: return q
    raise SystemExit(f"{path}: over {limit} bytes even at the lowest setting")
print("avif", fit(base + ".avif", lambda q: im.save(base + ".avif", quality=q, speed=2), [85, 75, 65, 50]))
print("webp", fit(base + ".webp", lambda q: im.save(base + ".webp", quality=q, method=6), [95, 90, 82, 72]))
print("png", fit(base + ".png", lambda c: (im if c == 0 else im.quantize(colors=c, dither=Image.Dither.NONE)).save(base + ".png", optimize=True), [0, 256, 128, 64]))
`;

const wanted = process.argv.slice(2);
const ids = wanted.length ? wanted : Object.keys(SCREENS);
for (const id of ids) if (!SCREENS[id]) throw new Error(`unknown screen "${id}" (known: ${Object.keys(SCREENS).join(", ")})`);

fs.mkdirSync(out, { recursive: true });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "landing-screens-"));
const browser = await chromium.launch();
try {
  for (const id of ids) {
    const { file, state } = SCREENS[id];
    const source = redact(read(file));
    const html = `<!doctype html><meta charset="utf-8"><style>${fontCss}</style><body style="margin:0;background:#000"><x-dc>${templateOf(source).replace(/<helmet>[\s\S]*?<\/helmet>/, "")}</x-dc>`;
    const htmlPath = path.join(tmp, `${id}.html`);
    fs.writeFileSync(htmlPath, html);
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, reducedMotion: "reduce" });
    await page.goto(`file://${htmlPath}`);
    await page.evaluate(expand, { vals: valsOf(source, {}, state), imports: importsOf(source) });
    await page.addStyleTag({ content: "a{color:#F3EEF5;text-decoration:none}button{font-family:inherit}" });
    const phone = page.locator("x-dc > div").first();
    await phone.evaluate((el, label) => el.insertAdjacentHTML("afterbegin", label), LABEL);
    await page.evaluate(() => document.fonts.ready);
    const png = path.join(tmp, `${id}.png`);
    await phone.screenshot({ path: png });
    const left = await page.evaluate(() => document.body.innerText.match(/\{\{|\}\}/g));
    if (left) throw new Error(`${id}: template syntax left in the page`);
    await page.close();
    const report = execFileSync("python3", ["-I", "-c", ENCODE, png, path.join(out, id), String(MAX_BYTES)], { encoding: "utf8" });
    const sizes = ["avif", "webp", "png"].map((ext) => `${ext} ${(fs.statSync(path.join(out, `${id}.${ext}`)).size / 1024).toFixed(0)} KB`).join(", ");
    console.log(`${id}: ${sizes}  (${report.trim().replace(/\n/g, ", ")})`);
  }
} finally {
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}
